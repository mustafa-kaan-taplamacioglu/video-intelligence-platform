"""
Tier 2: MediaPipe Pose + LSTM Sequence Classifier — multi-class.

Uses MediaPipe Tasks API (0.10.33+) for pose landmark extraction.
Processes videos one at a time (no intermediate files).
Window size = 8 frames to fit DCSASS 2-second sub-clips.

Usage:
    python train_lstm.py
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

# Config — must match ml/config.json
WINDOW_SIZE = 8
STRIDE = 4
TARGET_FPS = 5
ALL_LABELS = ["Normal", "Shoplifting", "Stealing", "Burglary", "Robbery"]
LABEL_TO_IDX = {label: idx for idx, label in enumerate(ALL_LABELS)}
MAX_PER_CLASS = 40  # max videos per class for training

ML_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = ML_DIR / "models"
POSE_MODEL = MODELS_DIR / "pose_landmarker_lite.task"
DCSASS = Path.home() / ".cache/kagglehub/datasets/mateohervas/dcsass-dataset/versions/1/DCSASS Dataset"


def extract_poses_tasks_api(video_path: str, target_fps: int = TARGET_FPS) -> np.ndarray:
    """Extract 33 landmarks per frame using MediaPipe Tasks API."""
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import PoseLandmarker, PoseLandmarkerOptions, RunningMode

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return np.array([])

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    interval = max(1, int(fps / target_fps))

    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(POSE_MODEL)),
        running_mode=RunningMode.VIDEO,
        num_poses=1,
    )

    landmarks = []
    idx = 0

    with PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % interval == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                ts_ms = int(idx * 1000 / fps)
                result = landmarker.detect_for_video(mp_image, ts_ms)
                if result.pose_landmarks and len(result.pose_landmarks) > 0:
                    kp = []
                    for lm in result.pose_landmarks[0]:
                        kp.extend([lm.x, lm.y, lm.z, lm.visibility])
                    landmarks.append(kp)
                else:
                    landmarks.append([0.0] * 132)
            idx += 1

    cap.release()
    return np.array(landmarks, dtype=np.float32)


def engineer_features(raw: np.ndarray) -> np.ndarray:
    """Normalize + velocities → 231-dim features per frame."""
    features = []
    for i in range(len(raw)):
        f = raw[i].reshape(33, 4)
        hip = (f[23, :3] + f[24, :3]) / 2
        norm = f[:, :3] - hip
        sd = np.linalg.norm(f[11, :3] - f[12, :3])
        if sd > 0.01:
            norm /= sd
        vel = (f[:, :3] - raw[i - 1].reshape(33, 4)[:, :3]) if i > 0 else np.zeros((33, 3))
        features.append(np.concatenate([norm.flatten(), vel.flatten(), f[:, 3]]))
    return np.array(features, dtype=np.float32)


def main():
    if not POSE_MODEL.exists():
        print(f"ERROR: Pose model not found at {POSE_MODEL}")
        print("Download: curl -L -o backend/ml/models/pose_landmarker_lite.task https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task")
        sys.exit(1)

    if not DCSASS.exists():
        print(f"ERROR: DCSASS dataset not found at {DCSASS}")
        sys.exit(1)

    print("=" * 60)
    print("TIER 2: LSTM Pose Classifier Training")
    print(f"Window: {WINDOW_SIZE}, Stride: {STRIDE}, FPS: {TARGET_FPS}")
    print("=" * 60)

    # Collect training windows
    all_X, all_y = [], []

    for cls in ["Shoplifting", "Stealing", "Burglary", "Robbery"]:
        csv_path = DCSASS / "Labels" / f"{cls}.csv"
        if not csv_path.exists():
            print(f"  WARNING: {csv_path} not found, skipping")
            continue

        df = pd.read_csv(csv_path, header=None, names=["fn", "cls", "abn"])
        cls_dir = DCSASS / cls
        label_idx = LABEL_TO_IDX[cls]

        normal_n, abn_n, skipped = 0, 0, 0

        for _, row in df.iterrows():
            if normal_n >= MAX_PER_CLASS and abn_n >= MAX_PER_CLASS:
                break

            y_label = label_idx if row["abn"] == 1 else 0
            if y_label == 0 and normal_n >= MAX_PER_CLASS:
                continue
            if y_label != 0 and abn_n >= MAX_PER_CLASS:
                continue

            matches = list(cls_dir.rglob(f"{row['fn']}.mp4"))
            if not matches or not matches[0].is_file():
                continue

            try:
                raw = extract_poses_tasks_api(str(matches[0]))
                if len(raw) < WINDOW_SIZE:
                    skipped += 1
                    continue

                feats = engineer_features(raw)
                windows_added = 0
                for s in range(0, len(feats) - WINDOW_SIZE + 1, STRIDE):
                    all_X.append(feats[s:s + WINDOW_SIZE])
                    all_y.append(y_label)
                    windows_added += 1

                if y_label == 0:
                    normal_n += 1
                else:
                    abn_n += 1
            except Exception as e:
                skipped += 1

        print(f"  {cls}: {abn_n} abnormal + {normal_n} normal clips (skipped {skipped})")

    if len(all_X) < 10:
        print(f"ERROR: Only {len(all_X)} windows — not enough to train")
        sys.exit(1)

    X = np.array(all_X, dtype=np.float32)
    y = np.array(all_y, dtype=np.int32)
    print(f"\nTotal: {len(X)} windows, shape: {X.shape}")
    for i, label in enumerate(ALL_LABELS):
        count = (y == i).sum()
        if count > 0:
            print(f"  {label}: {count} ({count / len(y) * 100:.1f}%)")

    # Train
    import tensorflow as tf
    y_cat = tf.keras.utils.to_categorical(y, len(ALL_LABELS))

    idx = np.random.permutation(len(X))
    split = int(len(X) * 0.8)
    X_tr, X_va = X[idx[:split]], X[idx[split:]]
    y_tr, y_va = y_cat[idx[:split]], y_cat[idx[split:]]

    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(WINDOW_SIZE, 231)),
        tf.keras.layers.LSTM(64, return_sequences=True, dropout=0.3),
        tf.keras.layers.LSTM(32, dropout=0.3),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(len(ALL_LABELS), activation="softmax"),
    ])
    model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
    model.summary()

    model.fit(
        X_tr, y_tr,
        validation_data=(X_va, y_va),
        epochs=30,
        batch_size=32,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(patience=8, restore_best_weights=True),
            tf.keras.callbacks.ReduceLROnPlateau(patience=4, factor=0.5),
        ],
    )

    save_path = str(MODELS_DIR / "lstm_activity_classifier.keras")
    model.save(save_path)
    loss, acc = model.evaluate(X_va, y_va, verbose=0)
    print(f"\nSaved: {save_path}")
    print(f"Validation accuracy: {acc:.4f}")

    # Per-class
    yp = np.argmax(model.predict(X_va, verbose=0), axis=1)
    yt = np.argmax(y_va, axis=1)
    for i, label in enumerate(ALL_LABELS):
        mask = yt == i
        if mask.sum() > 0:
            print(f"  {label}: {(yp[mask] == i).mean():.4f} ({mask.sum()} samples)")


if __name__ == "__main__":
    main()
