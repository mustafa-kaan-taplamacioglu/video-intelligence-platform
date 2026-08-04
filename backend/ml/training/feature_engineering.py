"""
Enhanced feature engineering: 343 features per frame.

Base (231): normalized positions (99) + velocities (99) + visibility (33)
New (+112):
  - 8 joint angles (elbow, shoulder, knee, hip × left/right)
  - 2 hand-to-hip distances (concealment indicator)
  - 1 head-body angle (looking around)
  - 99 accelerations (second derivative of positions)
  - 2 bounding box features (aspect ratio, area change)
"""

import numpy as np

NUM_LANDMARKS = 33
BASE_FEATURES = 231
ENHANCED_FEATURES = 343

# Landmark indices (MediaPipe Pose)
NOSE = 0
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28


def _angle_between(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Compute angle at point b between rays ba and bc."""
    ba = a - b
    bc = c - b
    cos_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    return float(np.arccos(np.clip(cos_angle, -1, 1)))


def engineer_features_enhanced(raw_landmarks: np.ndarray) -> np.ndarray:
    """
    Transform raw 132-dim landmarks into 343-dim enhanced features.
    """
    num_frames = len(raw_landmarks)
    features = np.zeros((num_frames, ENHANCED_FEATURES), dtype=np.float32)

    for i in range(num_frames):
        frame = raw_landmarks[i].reshape(33, 4)
        pos = frame[:, :3]
        vis = frame[:, 3]

        # --- Base features (231) ---

        # Hip center normalization
        hip_center = (pos[L_HIP] + pos[R_HIP]) / 2
        normalized = pos - hip_center
        shoulder_dist = np.linalg.norm(pos[L_SHOULDER] - pos[R_SHOULDER])
        if shoulder_dist > 0.01:
            normalized /= shoulder_dist

        # Velocities
        if i > 0:
            prev_pos = raw_landmarks[i - 1].reshape(33, 4)[:, :3]
            velocity = pos - prev_pos
        else:
            velocity = np.zeros((33, 3))

        base = np.concatenate([normalized.flatten(), velocity.flatten(), vis])  # 99+99+33=231

        # --- Enhanced features (+112) ---
        extra = []

        # 8 joint angles
        extra.append(_angle_between(pos[L_SHOULDER], pos[L_ELBOW], pos[L_WRIST]))    # L elbow
        extra.append(_angle_between(pos[R_SHOULDER], pos[R_ELBOW], pos[R_WRIST]))    # R elbow
        extra.append(_angle_between(pos[L_HIP], pos[L_SHOULDER], pos[L_ELBOW]))      # L shoulder
        extra.append(_angle_between(pos[R_HIP], pos[R_SHOULDER], pos[R_ELBOW]))      # R shoulder
        extra.append(_angle_between(pos[L_HIP], pos[L_KNEE], pos[L_ANKLE]))          # L knee
        extra.append(_angle_between(pos[R_HIP], pos[R_KNEE], pos[R_ANKLE]))          # R knee
        extra.append(_angle_between(pos[L_SHOULDER], pos[L_HIP], pos[L_KNEE]))       # L hip
        extra.append(_angle_between(pos[R_SHOULDER], pos[R_HIP], pos[R_KNEE]))       # R hip

        # 2 hand-to-hip distances (concealment)
        extra.append(float(np.linalg.norm(pos[L_WRIST] - pos[L_HIP])))
        extra.append(float(np.linalg.norm(pos[R_WRIST] - pos[R_HIP])))

        # 1 head-body angle (looking around)
        nose_to_hip = pos[NOSE] - hip_center
        vertical = np.array([0, -1, 0], dtype=np.float32)
        cos_head = np.dot(nose_to_hip, vertical) / (np.linalg.norm(nose_to_hip) + 1e-8)
        extra.append(float(np.arccos(np.clip(cos_head, -1, 1))))

        # 99 accelerations (second derivative)
        if i >= 2:
            prev1 = raw_landmarks[i - 1].reshape(33, 4)[:, :3]
            prev2 = raw_landmarks[i - 2].reshape(33, 4)[:, :3]
            accel = pos - 2 * prev1 + prev2
        else:
            accel = np.zeros((33, 3))
        extra.extend(accel.flatten().tolist())  # 99

        # 2 bounding box features
        valid_mask = vis > 0.3
        if valid_mask.sum() >= 2:
            valid_pos = pos[valid_mask]
            bbox_w = valid_pos[:, 0].max() - valid_pos[:, 0].min()
            bbox_h = valid_pos[:, 1].max() - valid_pos[:, 1].min()
            extra.append(float(bbox_h / (bbox_w + 1e-8)))  # aspect ratio
            extra.append(float(bbox_w * bbox_h))             # area
        else:
            extra.extend([0.0, 0.0])

        features[i] = np.concatenate([base, np.array(extra, dtype=np.float32)])

    return features


def engineer_features_base(raw_landmarks: np.ndarray) -> np.ndarray:
    """Original 231-dim features (for backward compat)."""
    features = []
    for i in range(len(raw_landmarks)):
        frame = raw_landmarks[i].reshape(33, 4)
        hip_center = (frame[23, :3] + frame[24, :3]) / 2
        normalized = frame[:, :3] - hip_center
        sd = np.linalg.norm(frame[11, :3] - frame[12, :3])
        if sd > 0.01:
            normalized /= sd
        vel = (frame[:, :3] - raw_landmarks[i - 1].reshape(33, 4)[:, :3]) if i > 0 else np.zeros((33, 3))
        features.append(np.concatenate([normalized.flatten(), vel.flatten(), frame[:, 3]]))
    return np.array(features, dtype=np.float32)
