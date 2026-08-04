"""
Live stream frame processing — captures frames and runs detection pipeline.

Uses MediaPipe Tasks API (0.10.33+) for pose extraction.
Applies StandardScaler (if loaded) and runs LSTM model on sliding windows.
Pushes detection events to a thread-safe queue consumed by the WebSocket.
"""

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from app.services.pose_extractor import engineer_features
from app.services.activity_classifier import get_classifier
from app.config import UPLOADS_DIR

logger = logging.getLogger(__name__)

ML_DIR = Path(__file__).resolve().parent.parent.parent / "ml"
POSE_MODEL = ML_DIR / "models" / "pose_landmarker_lite.task"


def get_stream_source(source: str, source_type: str) -> str:
    """Resolve source to an OpenCV-compatible input."""
    if source_type == "webcam":
        return source if source.strip() else "0"
    elif source_type == "rtsp":
        return source
    elif source_type == "demo":
        demo_files = list(UPLOADS_DIR.glob("*.mp4"))
        if demo_files:
            return str(demo_files[0])
        raise RuntimeError("No demo videos available — upload a video first")
    raise ValueError(f"Unsupported source type: {source_type}")


class StreamProcessor:
    """Processes a live video stream frame-by-frame with activity detection."""

    def __init__(self, session_id: str, source: str, source_type: str):
        self.session_id = session_id
        self.source = source
        self.source_type = source_type
        self.running = False
        self._thread: threading.Thread | None = None
        self._detections: list[dict] = []
        self._lock = threading.Lock()
        self._frame_count = 0
        self._fps_processing = 0.0
        self._pose_buffer: list[list[float]] = []
        self._classifier = get_classifier()
        self._last_prediction: float = 0.0
        self._last_detection_time: float = 0.0  # for cooldown

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)

    def get_new_detections(self) -> list[dict]:
        with self._lock:
            dets = self._detections.copy()
            self._detections.clear()
            return dets

    def get_status(self) -> dict:
        return {
            "type": "heartbeat",
            "fps_processing": round(self._fps_processing, 1),
            "frames_analyzed": self._frame_count,
            "active_detections": 0,
            "last_probability": round(self._last_prediction, 3),
        }

    def _run(self):
        try:
            stream_url = get_stream_source(self.source, self.source_type)
        except Exception as e:
            logger.error("Failed to get stream URL: %s", e)
            self.running = False
            return

        cap = cv2.VideoCapture(int(stream_url) if stream_url.isdigit() else stream_url)
        if not cap.isOpened():
            logger.error("Cannot open stream: %s", stream_url)
            self.running = False
            return

        # Initialize MediaPipe Tasks API PoseLandmarker (VIDEO mode for stream)
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions
            from mediapipe.tasks.python.vision import (
                PoseLandmarker, PoseLandmarkerOptions, RunningMode
            )

            if not POSE_MODEL.exists():
                logger.error("Pose model not found at %s", POSE_MODEL)
                cap.release()
                self.running = False
                return

            pose_options = PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(POSE_MODEL)),
                running_mode=RunningMode.VIDEO,
                num_poses=1,
                min_pose_detection_confidence=0.3,
            )
            landmarker = PoseLandmarker.create_from_options(pose_options)
            self._mp = mp
        except Exception as e:
            logger.error("MediaPipe init failed: %s", e)
            cap.release()
            self.running = False
            return

        window_size = self._classifier.window_size
        target_fps = self._classifier.config.get("target_fps", 8)
        stream_fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_interval = max(1, int(stream_fps / target_fps))

        stride = max(1, self._classifier.stride)
        threshold = max(0.7, self._classifier.threshold)  # High threshold for live
        cooldown_seconds = 3.0  # Min gap between detections

        frame_idx = 0
        last_time = time.time()

        logger.info(
            "Stream started: window=%d, target_fps=%d, stride=%d, threshold=%.2f",
            window_size, target_fps, stride, threshold,
        )

        try:
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % frame_interval == 0:
                    # Extract pose landmarks using Tasks API
                    kp = self._extract_pose_tasks(landmarker, frame, frame_idx, stream_fps)
                    self._pose_buffer.append(kp)
                    self._frame_count += 1

                    # Classify when buffer has enough frames
                    if len(self._pose_buffer) >= window_size:
                        self._classify_window(target_fps, threshold, cooldown_seconds)
                        # Slide buffer
                        self._pose_buffer = self._pose_buffer[stride:]

                    # FPS counter
                    now = time.time()
                    elapsed = now - last_time
                    if elapsed > 0:
                        self._fps_processing = 0.9 * self._fps_processing + 0.1 * (1.0 / elapsed)
                    last_time = now

                frame_idx += 1
        finally:
            try:
                landmarker.close()
            except Exception:
                pass
            cap.release()
            self.running = False

    def _extract_pose_tasks(self, landmarker, frame, frame_idx, stream_fps) -> list[float]:
        """Extract pose landmarks from a single frame using MediaPipe Tasks API."""
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
            timestamp_ms = int(frame_idx * 1000 / (stream_fps or 30))
            result = landmarker.detect_for_video(mp_image, timestamp_ms)

            if result.pose_landmarks and len(result.pose_landmarks) > 0:
                kp = []
                for lm in result.pose_landmarks[0]:
                    kp.extend([lm.x, lm.y, lm.z, lm.visibility])
                return kp
        except Exception as e:
            logger.debug("Pose detection failed on frame %d: %s", frame_idx, e)
        return [0.0] * 132

    def _classify_window(self, target_fps: float, threshold: float, cooldown: float):
        """Run classifier on current pose buffer window."""
        window_size = self._classifier.window_size
        raw = np.array(self._pose_buffer[-window_size:], dtype=np.float32)
        features = engineer_features(raw)

        # Apply scaler if available (v4/v5 models trained with normalization)
        if self._classifier.scaler is not None:
            features = self._classifier.scaler.transform(features)

        # Reshape to (1, window_size, feat_dim) for single-window prediction
        window_input = np.expand_dims(features, axis=0).astype(np.float32)

        try:
            prediction = self._classifier.lstm_model.predict(window_input, verbose=0)
        except Exception as e:
            logger.warning("LSTM predict failed: %s", e)
            return

        # Extract probability — binary sigmoid [[p]] or multi-class softmax [[p0,p1,...]]
        if prediction.ndim == 2 and prediction.shape[1] == 1:
            prob = float(prediction[0, 0])
            label = self._classifier.labels[1] if len(self._classifier.labels) >= 2 else "Suspicious"
        else:
            # Multi-class: use 1 - P(Normal)
            prob = float(1.0 - prediction[0, 0])
            class_idx = int(np.argmax(prediction[0]))
            label = self._classifier.labels[class_idx]
            if label == "Normal":
                label = "Suspicious"  # fallback

        self._last_prediction = prob

        # Only emit detection if above threshold AND cooldown passed
        now = time.time()
        if prob >= threshold and (now - self._last_detection_time) >= cooldown:
            self._last_detection_time = now
            with self._lock:
                self._detections.append({
                    "type": "detection",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "frame_number": self._frame_count,
                    "label": label,
                    "confidence": round(prob, 3),
                })
            logger.info("ALERT: %s (%.1f%%) at frame %d", label, prob * 100, self._frame_count)


# Active sessions registry
_active_sessions: dict[str, StreamProcessor] = {}


def start_session(session_id: str, source: str, source_type: str) -> StreamProcessor:
    processor = StreamProcessor(session_id, source, source_type)
    _active_sessions[session_id] = processor
    processor.start()
    return processor


def stop_session(session_id: str):
    processor = _active_sessions.pop(session_id, None)
    if processor:
        processor.stop()


def get_session(session_id: str) -> StreamProcessor | None:
    return _active_sessions.get(session_id)
