"""
Full training pipeline using DCSASS dataset.

DCSASS structure: each class dir has sub-clips with CSV labels.
CSV format: filename, class_name, is_abnormal (0=normal segment, 1=abnormal segment)

We use:
- label=0 clips from any class → Normal
- label=1 clips from Shoplifting/Stealing/Burglary/Robbery → respective class
"""

import os
import sys
import random
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

# Config
IMG_SIZE = 128
MAX_FRAMES_PER_VIDEO = 15
WINDOW_SIZE = 8  # DCSASS sub-clips are ~2s (10 frames@5fps), need smaller windows
STRIDE = 4
TARGET_FPS = 5
BATCH_SIZE = 32
TARGET_CLASSES = ["Shoplifting", "Stealing", "Burglary", "Robbery"]
ALL_LABELS = ["Normal"] + TARGET_CLASSES
LABEL_TO_IDX = {label: idx for idx, label in enumerate(ALL_LABELS)}

ML_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = ML_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def find_dataset():
    """Find DCSASS dataset in kagglehub cache."""
    cache = Path.home() / ".cache/kagglehub/datasets/mateohervas/dcsass-dataset/versions/1/DCSASS Dataset"
    if cache.exists():
        print(f"Dataset at: {cache}")
        return cache

    # Try downloading
    try:
        import kagglehub
        path = kagglehub.dataset_download("mateohervas/dcsass-dataset")
        return Path(path) / "DCSASS Dataset"
    except Exception as e:
        print(f"Cannot find dataset: {e}")
        sys.exit(1)


def load_labeled_videos(dataset_path: Path, max_per_class: int = 60):
    """Load videos with labels from CSV files."""
    labels_dir = dataset_path / "Labels"
    videos = {"Normal": [], "Shoplifting": [], "Stealing": [], "Burglary": [], "Robbery": []}

    for cls in TARGET_CLASSES:
        csv_path = labels_dir / f"{cls}.csv"
        if not csv_path.exists():
            print(f"  WARNING: {csv_path} not found")
            continue

        df = pd.read_csv(csv_path, header=None, names=["filename", "class", "is_abnormal"])
        cls_dir = dataset_path / cls

        normal_count = 0
        abnormal_count = 0

        for _, row in df.iterrows():
            # Find the video file
            video_name = f"{row['filename']}.mp4"
            # Videos are in subdirectories named after the parent video
            matches = list(cls_dir.rglob(video_name))
            if not matches:
                continue

            video_path = matches[0]
            if row["is_abnormal"] == 1 and abnormal_count < max_per_class:
                videos[cls].append(video_path)
                abnormal_count += 1
            elif row["is_abnormal"] == 0 and normal_count < max_per_class:
                videos["Normal"].append(video_path)
                normal_count += 1

        print(f"  {cls}: {abnormal_count} abnormal, contributed {normal_count} normal clips")

    for label, vids in videos.items():
        print(f"  Total {label}: {len(vids)} videos")

    return videos


# ============================================================
# TIER 1: MobileNet (Binary: Normal vs Suspicious)
# ============================================================

def extract_frames(video_path: str, max_frames: int = MAX_FRAMES_PER_VIDEO):
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        return []

    indices = np.linspace(0, total - 1, min(max_frames, total), dtype=int)
    frames = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            frames.append(cv2.resize(frame, (IMG_SIZE, IMG_SIZE)) / 255.0)
    cap.release()
    return frames


def train_mobilenet(videos: dict):
    import tensorflow as tf

    print("\n" + "=" * 60)
    print("TIER 1: MobileNet Binary Classifier")
    print("=" * 60)

    all_frames, all_labels = [], []

    # Normal → 0
    for vpath in videos["Normal"]:
        for f in extract_frames(str(vpath)):
            all_frames.append(f)
            all_labels.append(0)

    # Suspicious → 1
    for cls in TARGET_CLASSES:
        for vpath in videos[cls]:
            for f in extract_frames(str(vpath)):
                all_frames.append(f)
                all_labels.append(1)

    X = np.array(all_frames, dtype=np.float32)
    y = np.array(all_labels, dtype=np.float32)
    print(f"Frames: {len(X)} (normal={int((y==0).sum())}, suspicious={int((y==1).sum())})")

    from sklearn.model_selection import train_test_split
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(IMG_SIZE, IMG_SIZE, 3)),
        tf.keras.layers.Conv2D(32, 3, activation="relu"),
        tf.keras.layers.MaxPooling2D(),
        tf.keras.layers.Conv2D(64, 3, activation="relu"),
        tf.keras.layers.MaxPooling2D(),
        tf.keras.layers.Conv2D(128, 3, activation="relu"),
        tf.keras.layers.GlobalAveragePooling2D(),
        tf.keras.layers.Dropout(0.5),
        tf.keras.layers.Dense(128, activation="relu"),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(1, activation="sigmoid"),
    ])
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-4), loss="binary_crossentropy", metrics=["accuracy"])

    model.fit(X_train, y_train, validation_data=(X_val, y_val), epochs=15, batch_size=BATCH_SIZE,
              callbacks=[tf.keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True)])

    path = str(MODELS_DIR / "mobilenet_shoplifting.h5")
    model.save(path)
    loss, acc = model.evaluate(X_val, y_val, verbose=0)
    print(f"Saved: {path} — Val accuracy: {acc:.4f}")
    return acc


# ============================================================
# TIER 2: MediaPipe Pose + LSTM (5-class)
# ============================================================

def extract_poses(video_path: str):
    import mediapipe as mp
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    interval = max(1, int(fps / TARGET_FPS))
    landmarks = []
    idx = 0

    with mp.solutions.pose.Pose(static_image_mode=False, min_detection_confidence=0.5) as pose:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if idx % interval == 0:
                result = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if result.pose_landmarks:
                    kp = []
                    for lm in result.pose_landmarks.landmark:
                        kp.extend([lm.x, lm.y, lm.z, lm.visibility])
                    landmarks.append(kp)
                else:
                    landmarks.append([0.0] * 132)
            idx += 1
    cap.release()
    return np.array(landmarks, dtype=np.float32)


def engineer_features(raw):
    features = []
    for i in range(len(raw)):
        frame = raw[i].reshape(33, 4)
        hip = (frame[23, :3] + frame[24, :3]) / 2
        norm = frame[:, :3] - hip
        sd = np.linalg.norm(frame[11, :3] - frame[12, :3])
        if sd > 0.01:
            norm /= sd
        vel = (frame[:, :3] - raw[i-1].reshape(33, 4)[:, :3]) if i > 0 else np.zeros((33, 3))
        features.append(np.concatenate([norm.flatten(), vel.flatten(), frame[:, 3]]))
    return np.array(features, dtype=np.float32)


def train_lstm(videos: dict, max_per_class: int = 30):
    import tensorflow as tf

    print("\n" + "=" * 60)
    print("TIER 2: LSTM Pose Classifier (5-class)")
    print("=" * 60)

    all_X, all_y = [], []
    for label in ALL_LABELS:
        label_idx = LABEL_TO_IDX[label]
        subset = videos[label][:max_per_class]
        ok = 0
        for vpath in subset:
            try:
                raw = extract_poses(str(vpath))
                if len(raw) < WINDOW_SIZE:
                    continue
                feats = engineer_features(raw)
                for s in range(0, len(feats) - WINDOW_SIZE + 1, STRIDE):
                    all_X.append(feats[s:s + WINDOW_SIZE])
                    all_y.append(label_idx)
                ok += 1
            except:
                pass
        print(f"  {label}: {ok}/{len(subset)} videos → {sum(1 for y in all_y if y == label_idx)} windows")

    X = np.array(all_X, dtype=np.float32)
    y = np.array(all_y, dtype=np.int32)
    y_cat = tf.keras.utils.to_categorical(y, len(ALL_LABELS))
    print(f"Total: {len(X)} windows")

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

    model.fit(X_tr, y_tr, validation_data=(X_va, y_va), epochs=30, batch_size=BATCH_SIZE,
              callbacks=[tf.keras.callbacks.EarlyStopping(patience=8, restore_best_weights=True)])

    path = str(MODELS_DIR / "lstm_activity_classifier.keras")
    model.save(path)
    loss, acc = model.evaluate(X_va, y_va, verbose=0)
    print(f"Saved: {path} — Val accuracy: {acc:.4f}")

    # Per-class
    yp = np.argmax(model.predict(X_va, verbose=0), axis=1)
    yt = np.argmax(y_va, axis=1)
    for i, label in enumerate(ALL_LABELS):
        mask = yt == i
        if mask.sum() > 0:
            print(f"  {label}: {(yp[mask]==i).mean():.4f} ({mask.sum()} samples)")

    return acc


def main():
    print("=" * 60)
    print("Video Intelligence Platform — Model Training")
    print("=" * 60)

    dataset = find_dataset()
    videos = load_labeled_videos(dataset, max_per_class=60)

    total = sum(len(v) for v in videos.values())
    if total < 20:
        print(f"Only {total} videos found — need at least 20")
        sys.exit(1)

    # Train both tiers
    mob_acc = train_mobilenet(videos)
    lstm_acc = train_lstm(videos, max_per_class=30)

    print("\n" + "=" * 60)
    print("DONE")
    print(f"  MobileNet: {mob_acc:.1%} val accuracy → ml/models/mobilenet_shoplifting.h5")
    print(f"  LSTM:      {lstm_acc:.1%} val accuracy → ml/models/lstm_activity_classifier.keras")
    print("Restart backend to auto-detect models.")
    print("=" * 60)


if __name__ == "__main__":
    main()
