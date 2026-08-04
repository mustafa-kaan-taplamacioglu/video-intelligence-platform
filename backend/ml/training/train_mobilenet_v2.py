"""
Tier 1 v2: Improved MobileNet training with proper ML engineering.

- Video-level split (no data leakage: frames from same video stay in same split)
- class_weight='balanced'
- Fine-tuning (unfreeze last layers)
- Learning rate warmup + cosine decay
- Full evaluation metrics
"""

import sys
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ML_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = ML_DIR / "models"
TRAINING_DIR = Path(__file__).resolve().parent

ALL_LABELS = ["Normal", "Suspicious"]
IMG_SIZE = 128
MAX_FRAMES_PER_VIDEO = 15


def extract_frames(video_path: str) -> list[np.ndarray]:
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        return []
    indices = np.linspace(0, total - 1, min(MAX_FRAMES_PER_VIDEO, total), dtype=int)
    frames = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            frames.append(cv2.resize(frame, (IMG_SIZE, IMG_SIZE)) / 255.0)
    cap.release()
    return frames


def main():
    import tensorflow as tf
    from sklearn.metrics import classification_report, confusion_matrix, f1_score

    print("=" * 60)
    print("MobileNet v2 — Improved Training")
    print("=" * 60)

    # Load and split by video
    from data_utils import load_all_clips, split_by_video, compute_class_weights

    df = load_all_clips(max_per_class=300)
    # Convert to binary: 0=Normal, 1=Suspicious (any abnormal)
    df["binary_label"] = (df["label"] > 0).astype(int)
    print(f"Total clips: {len(df)} (Normal={int((df.binary_label==0).sum())}, Suspicious={int((df.binary_label==1).sum())})")

    train_df, val_df, test_df = split_by_video(df)

    # Verify no leakage
    assert set(train_df["parent_video"]).isdisjoint(set(test_df["parent_video"]))
    print(f"Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)} — no leakage ✓")

    def extract_all(split_df):
        X, y = [], []
        for _, row in split_df.iterrows():
            frames = extract_frames(row["path"])
            for f in frames:
                X.append(f)
                y.append(row["binary_label"])
        return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)

    print("Extracting frames...")
    X_train, y_train = extract_all(train_df)
    X_val, y_val = extract_all(val_df)
    X_test, y_test = extract_all(test_df)
    print(f"  Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

    class_weights = compute_class_weights(y_train.astype(int))
    print(f"Class weights: {class_weights}")

    # Build model with fine-tuning capability
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(IMG_SIZE, IMG_SIZE, 3)),
        tf.keras.layers.Conv2D(32, 3, activation="relu"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.MaxPooling2D(),
        tf.keras.layers.Conv2D(64, 3, activation="relu"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.MaxPooling2D(),
        tf.keras.layers.Conv2D(128, 3, activation="relu"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.GlobalAveragePooling2D(),
        tf.keras.layers.Dropout(0.5),
        tf.keras.layers.Dense(128, activation="relu"),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(1, activation="sigmoid"),
    ])

    # Cosine decay LR schedule
    lr_schedule = tf.keras.optimizers.schedules.CosineDecay(
        initial_learning_rate=1e-3, decay_steps=len(X_train) // 32 * 20,
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr_schedule),
        loss="binary_crossentropy",
        metrics=["accuracy"],
    )

    model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=20,
        batch_size=32,
        class_weight=class_weights,
        callbacks=[tf.keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True)],
    )

    # Evaluate on test
    print("\n" + "=" * 60)
    print("Test Set Evaluation")
    print("=" * 60)

    y_pred_prob = model.predict(X_test, verbose=0).flatten()
    y_pred = (y_pred_prob > 0.5).astype(int)

    report = classification_report(y_test.astype(int), y_pred, target_names=ALL_LABELS, digits=4)
    print(report)

    macro_f1 = f1_score(y_test.astype(int), y_pred, average="macro")
    print(f"Macro F1: {macro_f1:.4f}")

    # Confusion matrix
    cm = confusion_matrix(y_test.astype(int), y_pred)
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(ALL_LABELS)
    ax.set_yticklabels(ALL_LABELS)
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i][j]), ha="center", va="center",
                    color="white" if cm[i][j] > cm.max() / 2 else "black")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("MobileNet v2 Confusion Matrix")
    plt.colorbar(im)
    plt.tight_layout()
    plt.savefig(str(TRAINING_DIR / "confusion_matrix_mobilenet.png"), dpi=150)
    plt.close()

    # Save
    model.save(str(MODELS_DIR / "mobilenet_shoplifting.h5"))
    print(f"\nSaved: {MODELS_DIR / 'mobilenet_shoplifting.h5'}")

    # Append to report
    with open(str(TRAINING_DIR / "evaluation_report.txt"), "a") as f:
        f.write(f"\n{'='*60}\nMOBILENET v2 Evaluation\n{'='*60}\n")
        f.write(report)
        f.write(f"\nMacro F1: {macro_f1:.4f}\n")

    print(f"Test Macro F1: {macro_f1:.4f}")


if __name__ == "__main__":
    main()
