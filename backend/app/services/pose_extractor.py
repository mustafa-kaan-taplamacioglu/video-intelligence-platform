"""MediaPipe pose extraction and feature engineering for activity detection."""

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Try to import mediapipe; fall back to mock if unavailable
MEDIAPIPE_AVAILABLE = False
try:
    import mediapipe as mp
    # MediaPipe 0.10.33+ removed solutions API, use tasks API
    if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'pose'):
        MEDIAPIPE_AVAILABLE = True
        _USE_LEGACY = True
    elif hasattr(mp, 'tasks'):
        MEDIAPIPE_AVAILABLE = True
        _USE_LEGACY = False
except ImportError:
    pass

if not MEDIAPIPE_AVAILABLE:
    logger.warning("MediaPipe not available — pose extraction will return mock data")

def _get_pose_model_path() -> str:
    """Download and return path to MediaPipe pose landmarker model."""
    import urllib.request
    from pathlib import Path
    model_dir = Path(__file__).resolve().parent.parent.parent / "ml" / "models"
    model_path = model_dir / "pose_landmarker_lite.task"
    if not model_path.exists():
        url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
        logger.info("Downloading MediaPipe pose model...")
        urllib.request.urlretrieve(url, str(model_path))
    return str(model_path)

NUM_LANDMARKS = 33
RAW_FEATURES = NUM_LANDMARKS * 4  # x, y, z, visibility per landmark
ENGINEERED_FEATURES = 231  # 99 (positions) + 99 (velocities) + 33 (visibility)


def extract_poses(video_path: str, target_fps: int = 5) -> np.ndarray:
    """
    Extract pose landmarks from video file.
    Returns array of shape (num_frames, 132).
    Falls back to random data if MediaPipe is unavailable.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    original_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_interval = max(1, int(original_fps / target_fps))

    if not MEDIAPIPE_AVAILABLE:
        cap.release()
        num_extracted = max(1, total_frames // frame_interval)
        logger.info(f"Mock pose extraction: {num_extracted} frames")
        return np.random.rand(num_extracted, RAW_FEATURES).astype(np.float32) * 0.5 + 0.25

    landmarks_sequence = []
    frame_idx = 0

    if _USE_LEGACY:
        # MediaPipe legacy solutions API
        with mp.solutions.pose.Pose(static_image_mode=False, min_detection_confidence=0.5) as pose:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % frame_interval == 0:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    result = pose.process(rgb)
                    if result.pose_landmarks:
                        kp = []
                        for lm in result.pose_landmarks.landmark:
                            kp.extend([lm.x, lm.y, lm.z, lm.visibility])
                        landmarks_sequence.append(kp)
                    else:
                        landmarks_sequence.append([0.0] * RAW_FEATURES)
                frame_idx += 1
    else:
        # MediaPipe Tasks API (0.10.33+)
        from mediapipe.tasks.python import BaseOptions, vision
        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=_get_pose_model_path()),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
        )
        with vision.PoseLandmarker.create_from_options(options) as landmarker:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % frame_interval == 0:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    timestamp_ms = int(frame_idx * 1000 / (original_fps or 30))
                    result = landmarker.detect_for_video(mp_image, timestamp_ms)
                    if result.pose_landmarks and len(result.pose_landmarks) > 0:
                        kp = []
                        for lm in result.pose_landmarks[0]:
                            kp.extend([lm.x, lm.y, lm.z, lm.visibility])
                        landmarks_sequence.append(kp)
                    else:
                        landmarks_sequence.append([0.0] * RAW_FEATURES)
                frame_idx += 1

    cap.release()
    return np.array(landmarks_sequence, dtype=np.float32)


def engineer_features(raw_landmarks: np.ndarray) -> np.ndarray:
    """
    Transform raw 132-dim landmarks into 231-dim engineered features.
    - Torso-normalized positions (99)
    - Frame-to-frame velocities (99)
    - Visibility scores (33)
    """
    features = []
    for i in range(len(raw_landmarks)):
        frame = raw_landmarks[i].reshape(NUM_LANDMARKS, 4)

        # Hip center as origin
        hip_center = (frame[23, :3] + frame[24, :3]) / 2
        normalized = frame[:, :3] - hip_center

        # Scale normalization by shoulder width
        shoulder_dist = np.linalg.norm(frame[11, :3] - frame[12, :3])
        if shoulder_dist > 0.01:
            normalized /= shoulder_dist

        # Velocities
        if i > 0:
            prev = raw_landmarks[i - 1].reshape(NUM_LANDMARKS, 4)[:, :3]
            velocity = frame[:, :3] - prev
        else:
            velocity = np.zeros((NUM_LANDMARKS, 3))

        feat = np.concatenate([
            normalized.flatten(),   # 99
            velocity.flatten(),     # 99
            frame[:, 3],            # 33
        ])
        features.append(feat)

    return np.array(features, dtype=np.float32)
