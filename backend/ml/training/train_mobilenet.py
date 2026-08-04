"""
Tier 1: MobileNetV2 Frame Classifier — binary (normal vs suspicious).

Reads raw frames, resizes to 128x128, feeds to MobileNetV2-035.

The general approach (MobileNetV2 frame classifier over DCSASS) was informed by
a publicly circulated Kaggle notebook; this is an independent implementation.
See the NOTICE file at the repository root for the full acknowledgement.

Usage:
    python train_mobilenet.py --dcsass_root /path/to/DCSASS --output_dir ../models

Output:
    mobilenet_shoplifting.h5 — binary classifier (~15MB)
"""

import argparse
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


IMG_SIZE = 128
MAX_FRAMES_PER_VIDEO = 30
EPOCHS = 15
BATCH_SIZE = 32


def load_labels(csv_path: str) -> pd.DataFrame:
    """Load DCSASS labels CSV. Columns: video_path, label (0=normal, 1=shoplifting)."""
    df = pd.read_csv(csv_path)
    df.columns = ["video_path", "label"]
    df["video_path"] = df["video_path"].apply(lambda x: f"{x}.mp4")
    return df


def extract_frames(video_path: str, max_frames: int = MAX_FRAMES_PER_VIDEO):
    """Extract evenly-spaced frames from video, resized to IMG_SIZE."""
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        return []

    indices = np.linspace(0, total - 1, max_frames, dtype=int)
    frames = []

    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            frame = cv2.resize(frame, (IMG_SIZE, IMG_SIZE))
            frames.append(frame / 255.0)

    cap.release()
    return frames


def build_model():
    """MobileNetV2-035-128 binary classifier."""
    import tensorflow as tf
    import tensorflow_hub as hub

    model_url = "https://www.kaggle.com/models/google/mobilenet-v2/TensorFlow2/035-128-classification/2"
    model = tf.keras.Sequential([
        hub.KerasLayer(model_url, trainable=False),
        tf.keras.layers.Dropout(0.5),
        tf.keras.layers.Dense(128, activation="relu",
                              kernel_regularizer=tf.keras.regularizers.l2(0.01)),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(1, activation="sigmoid"),
    ])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001),
        loss="binary_crossentropy",
        metrics=["accuracy"],
    )
    return model


def main():
    parser = argparse.ArgumentParser(description="Train MobileNet shoplifting classifier")
    parser.add_argument("--dcsass_root", required=True, help="Path to DCSASS Dataset root")
    parser.add_argument("--csv", default="Shoplifting.csv", help="Labels CSV filename")
    parser.add_argument("--output_dir", default="../models", help="Directory to save model")
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    args = parser.parse_args()

    import tensorflow as tf

    dcsass = Path(args.dcsass_root)
    df = load_labels(str(dcsass / args.csv))
    print(f"Loaded {len(df)} video labels")

    all_frames, all_labels = [], []
    for _, row in df.iterrows():
        video_path = str(dcsass / row["video_path"])
        if not Path(video_path).exists():
            continue
        frames = extract_frames(video_path)
        for f in frames:
            all_frames.append(f)
            all_labels.append(row["label"])

    X = np.array(all_frames, dtype=np.float32)
    y = np.array(all_labels, dtype=np.float32)
    print(f"Total frames: {len(X)} (normal: {(y==0).sum()}, suspicious: {(y==1).sum()})")

    # Split
    from sklearn.model_selection import train_test_split
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, stratify=y)

    model = build_model()
    model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=args.epochs,
        batch_size=BATCH_SIZE,
        callbacks=[
            tf.keras.callbacks.ReduceLROnPlateau(patience=3, factor=0.5),
            tf.keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True),
        ],
    )

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    model.save(str(output / "mobilenet_shoplifting.h5"))
    print(f"Model saved to {output / 'mobilenet_shoplifting.h5'}")

    loss, acc = model.evaluate(X_val, y_val)
    print(f"Validation accuracy: {acc:.4f}")


if __name__ == "__main__":
    main()
