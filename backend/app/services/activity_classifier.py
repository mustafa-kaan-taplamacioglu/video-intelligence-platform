"""
Two-tier activity classifier for suspicious behavior detection.

Modes (graceful degradation):
  1. lstm     — MediaPipe Pose + LSTM sequence classifier (multi-class, best accuracy)
  2. mobilenet — MobileNetV2 frame classifier (binary: normal vs suspicious, simpler)
  3. mock     — Fake detections (no model needed, for development/demo)

If no model weights exist, runs in mock mode so the full pipeline works without training.
"""

import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

ML_DIR = Path(__file__).resolve().parent.parent.parent / "ml"
CONFIG_PATH = ML_DIR / "config.json"
LSTM_MODEL_PATH = ML_DIR / "models" / "lstm_activity_classifier.keras"
MOBILENET_MODEL_PATH = ML_DIR / "models" / "mobilenet_shoplifting.h5"
LABEL_MAP_PATH = ML_DIR / "models" / "label_map.json"
SCALER_PATH = ML_DIR / "models" / "feature_scaler.pkl"


@dataclass
class Detection:
    start_time: float
    end_time: float
    label: str
    confidence: float


class ActivityClassifier:
    """Two-tier classifier: tries LSTM first, then MobileNet, then mock."""

    def __init__(self):
        self.config = self._load_config()
        self.labels = self.config["labels"]
        self.window_size = self.config["window_size"]
        self.stride = self.config["stride"]
        self.threshold = self.config["confidence_threshold"]
        self.lstm_model = None
        self.mobilenet_model = None
        self.scaler = None
        self.mode = "mock"

        # Load scaler if exists
        if SCALER_PATH.exists():
            try:
                import pickle
                with open(SCALER_PATH, "rb") as f:
                    self.scaler = pickle.load(f)
                logger.info("Loaded feature scaler")
            except Exception as e:
                logger.warning("Failed to load scaler: %s", e)

        # Try LSTM (Tier 2 — best)
        if LSTM_MODEL_PATH.exists():
            try:
                import tensorflow as tf
                self.lstm_model = tf.keras.models.load_model(str(LSTM_MODEL_PATH))
                self.mode = "lstm"
                logger.info("Loaded LSTM classifier — mode: lstm")
            except Exception as e:
                logger.warning("Failed to load LSTM model: %s", e)

        # Try MobileNet (Tier 1 — fallback)
        if self.mode == "mock" and MOBILENET_MODEL_PATH.exists():
            try:
                import tensorflow as tf
                self.mobilenet_model = tf.keras.models.load_model(str(MOBILENET_MODEL_PATH))
                self.mode = "mobilenet"
                logger.info("Loaded MobileNet classifier — mode: mobilenet")
            except Exception as e:
                logger.warning("Failed to load MobileNet model: %s", e)

        if self.mode == "mock":
            logger.info("No model weights found — mode: mock (fake detections)")

    def _load_config(self) -> dict:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                return json.load(f)
        return {
            "window_size": 30, "stride": 15, "num_classes": 5,
            "labels": ["Normal", "Shoplifting", "Stealing", "Burglary", "Robbery"],
            "confidence_threshold": 0.6, "features_per_frame": 231, "target_fps": 5,
            "mobilenet_img_size": 128, "mobilenet_target_fps": 2, "mobilenet_threshold": 0.5,
        }

    def analyze_video(self, video_path: str) -> list[Detection]:
        """Analyze a video file and return detections. Dispatches to active mode."""
        result = self.analyze_video_full(video_path)
        return result["detections"]

    def analyze_video_full(self, video_path: str) -> dict:
        """
        Analyze video and return detections + probability curve for visualization.
        Returns: {detections, probability_curve, curve_timestamps}
        """
        if self.mode == "lstm":
            return self._analyze_lstm_full(video_path)
        elif self.mode == "mobilenet":
            return self._analyze_mobilenet_full(video_path)
        return {
            "detections": self._analyze_mock(video_path),
            "probability_curve": [],
            "curve_timestamps": [],
        }

    # --- Tier 2: LSTM on pose sequences ---
    def _analyze_lstm(self, video_path: str) -> list[Detection]:
        return self._analyze_lstm_full(video_path)["detections"]

    def _analyze_lstm_full(self, video_path: str) -> dict:
        from app.services.pose_extractor import extract_poses, engineer_features

        target_fps = self.config["target_fps"]
        landmarks = extract_poses(video_path, target_fps=target_fps)

        feat_dim = self.config.get("features_per_frame", 231)
        if feat_dim > 231:
            try:
                from ml.training.feature_engineering import engineer_features_enhanced
                features = engineer_features_enhanced(landmarks)
            except ImportError:
                features = engineer_features(landmarks)
        else:
            features = engineer_features(landmarks)

        if len(features) < self.window_size:
            return {"detections": [], "probability_curve": [], "curve_timestamps": []}

        if self.scaler is not None:
            features = self.scaler.transform(features)

        windows, window_starts = [], []
        for start in range(0, len(features) - self.window_size + 1, self.stride):
            windows.append(features[start:start + self.window_size])
            window_starts.append(start)

        predictions = self.lstm_model.predict(np.array(windows, dtype=np.float32), verbose=0)

        # Build probability curve (window-center timestamps)
        is_binary = predictions.ndim == 2 and predictions.shape[1] == 1
        if is_binary:
            curve = predictions.flatten().tolist()
        else:
            # Multi-class: use 1 - P(Normal) as suspicious probability
            curve = (1.0 - predictions[:, 0]).tolist()

        # Window center timestamp
        curve_ts = [
            round((s + self.window_size / 2) / target_fps, 2) for s in window_starts
        ]

        detections = self._peaks_to_detections(
            np.array(curve), window_starts, target_fps, is_binary
        )

        return {
            "detections": detections,
            "probability_curve": [round(p, 4) for p in curve],
            "curve_timestamps": curve_ts,
        }

    # --- Tier 1: MobileNet on raw frames ---
    def _analyze_mobilenet(self, video_path: str) -> list[Detection]:
        return self._analyze_mobilenet_full(video_path)["detections"]

    def _analyze_mobilenet_full(self, video_path: str) -> dict:
        img_size = self.config.get("mobilenet_img_size", 128)
        target_fps = self.config.get("mobilenet_target_fps", 2)

        frames, timestamps = self._extract_frames(video_path, target_fps, img_size)
        if not frames:
            return {"detections": [], "probability_curve": [], "curve_timestamps": []}

        batch = np.array(frames, dtype=np.float32)
        preds = self.mobilenet_model.predict(batch, verbose=0).flatten()
        curve = preds.tolist()

        # Use peak detection on per-frame predictions
        detections = self._peaks_to_detections_mobilenet(preds, timestamps, target_fps)

        return {
            "detections": detections,
            "probability_curve": [round(float(p), 4) for p in curve],
            "curve_timestamps": [round(float(t), 2) for t in timestamps],
        }

    def _peaks_to_detections_mobilenet(self, preds, timestamps, target_fps):
        """Peak detection on per-frame mobilenet predictions."""
        from scipy.signal import find_peaks

        if len(preds) < 3:
            return []

        # Smooth with rolling mean
        smoothed = self._smooth(preds, window=3)

        # Adaptive threshold
        height = max(0.65, float(smoothed.mean() + smoothed.std() * 0.5))
        distance_frames = max(1, int(target_fps * 3.0))

        peaks, props = find_peaks(
            smoothed, height=height, distance=distance_frames, prominence=0.1
        )

        detections = []
        for idx in peaks[:10]:
            ts = float(timestamps[idx])
            detections.append(Detection(
                start_time=round(max(0, ts - 1.0), 1),
                end_time=round(ts + 1.0, 1),
                label="Suspicious",
                confidence=round(float(smoothed[idx]), 3),
            ))
        return detections

    def _extract_frames(self, video_path: str, target_fps: float, img_size: int):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return [], []

        original_fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_interval = max(1, int(original_fps / target_fps))

        frames, timestamps = [], []
        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_interval == 0:
                resized = cv2.resize(frame, (img_size, img_size))
                frames.append(resized / 255.0)
                timestamps.append(frame_idx / original_fps)
            frame_idx += 1

        cap.release()
        return frames, timestamps

    # --- Mock mode ---
    def _analyze_mock(self, video_path: str) -> list[Detection]:
        """Return realistic fake detections based on video duration."""
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        duration = total_frames / fps if fps > 0 else 60

        detections = []
        suspicious_labels = ["Shoplifting", "Stealing", "Burglary", "Robbery"]

        # Generate 1-4 fake detections spread across the video
        num_detections = random.randint(1, min(4, max(1, int(duration / 30))))
        used_ranges: list[tuple[float, float]] = []

        for _ in range(num_detections):
            for _attempt in range(20):
                start = round(random.uniform(duration * 0.05, duration * 0.85), 1)
                length = round(random.uniform(2.0, min(8.0, duration * 0.1)), 1)
                end = round(start + length, 1)
                if end > duration:
                    continue
                if any(not (end < us or start > ue) for us, ue in used_ranges):
                    continue
                used_ranges.append((start, end))
                detections.append(Detection(
                    start_time=start,
                    end_time=end,
                    label=random.choice(suspicious_labels),
                    confidence=round(random.uniform(0.65, 0.95), 3),
                ))
                break

        return sorted(detections, key=lambda d: d.start_time)

    # --- Shared helpers ---
    def _smooth(self, arr, window=3):
        """Rolling mean smoothing."""
        if len(arr) < window:
            return np.asarray(arr, dtype=np.float32)
        kernel = np.ones(window, dtype=np.float32) / window
        return np.convolve(arr, kernel, mode="same")

    def _peaks_to_detections(self, curve, window_starts, fps, is_binary):
        """
        Find peaks in probability curve → discrete detections.
        Replaces naive thresholding + merge_detections.
        """
        from scipy.signal import find_peaks

        if len(curve) < 3:
            return []

        smoothed = self._smooth(curve, window=3)
        label = self.labels[1] if (is_binary and len(self.labels) >= 2) else "Suspicious"

        # Adaptive threshold: max(0.7, mean+0.5*std)
        mean = float(smoothed.mean())
        std = float(smoothed.std())
        height = max(0.7, mean + 0.5 * std)

        # Min distance between peaks (in window indices)
        # window_size frames per window, stride between windows
        windows_per_second = fps / max(1, self.stride)
        distance = max(1, int(windows_per_second * 3.0))  # peaks ≥3s apart

        peaks, _ = find_peaks(
            smoothed, height=height, distance=distance, prominence=0.05
        )

        # Fallback: if no peaks but model is generally confident, take top-3
        if len(peaks) == 0 and smoothed.max() > 0.6:
            top_idx = np.argsort(smoothed)[-3:]
            peaks = sorted(top_idx)

        detections = []
        for pidx in peaks[:10]:
            frame_start = window_starts[pidx]
            ts_start = frame_start / fps
            ts_end = (frame_start + self.window_size) / fps
            detections.append(Detection(
                start_time=round(max(0.0, ts_start), 1),
                end_time=round(ts_end, 1),
                label=label,
                confidence=round(float(smoothed[pidx]), 3),
            ))
        return detections


def merge_detections(detections: list[Detection], gap_threshold: float = 2.0) -> list[Detection]:
    """Merge overlapping or adjacent detections of the same class."""
    if not detections:
        return []

    sorted_dets = sorted(detections, key=lambda d: d.start_time)
    merged = [sorted_dets[0]]

    for det in sorted_dets[1:]:
        prev = merged[-1]
        if det.label == prev.label and det.start_time <= prev.end_time + gap_threshold:
            merged[-1] = Detection(
                start_time=prev.start_time,
                end_time=max(prev.end_time, det.end_time),
                label=prev.label,
                confidence=max(prev.confidence, det.confidence),
            )
        else:
            merged.append(det)

    return merged


# Singleton
_classifier: ActivityClassifier | None = None


def get_classifier() -> ActivityClassifier:
    global _classifier
    if _classifier is None:
        _classifier = ActivityClassifier()
    return _classifier
