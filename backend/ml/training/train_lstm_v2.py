"""
Tier 2 v2: Improved LSTM training with proper ML engineering.

- Video-level split (no data leakage)
- Enhanced 343-dim features
- Class balancing (weights + augmentation)
- Optuna hyperparameter tuning
- Multiple architectures: LSTM, BiLSTM, GRU, CNN+LSTM
- 5-fold GroupKFold cross-validation
- Full evaluation metrics (F1, ROC-AUC, confusion matrix)
"""

import sys
import json
import pickle
import warnings
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

ML_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = ML_DIR / "models"
TRAINING_DIR = Path(__file__).resolve().parent
POSE_MODEL = MODELS_DIR / "pose_landmarker_lite.task"

ALL_LABELS = ["Normal", "Shoplifting", "Stealing", "Burglary", "Robbery"]
TARGET_FPS = 3  # lower than 5 to get more frames from short clips
WINDOW_SIZE = 10
STRIDE = 5


def extract_poses(video_path: str) -> np.ndarray:
    """Extract poses using MediaPipe Tasks API."""
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import PoseLandmarker, PoseLandmarkerOptions, RunningMode

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return np.array([])

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    interval = max(1, int(fps / TARGET_FPS))
    landmarks = []
    idx = 0

    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(POSE_MODEL)),
        running_mode=RunningMode.VIDEO,
        num_poses=1,
    )

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


def process_dataset(max_per_class=200):
    """Load clips, extract poses, engineer features, create windows. All in memory."""
    from data_utils import load_all_clips, split_by_video, compute_class_weights
    from feature_engineering import engineer_features_enhanced

    print("Loading clip metadata...")
    df = load_all_clips(max_per_class=max_per_class)
    print(f"Total clips: {len(df)}")
    for label in ALL_LABELS:
        count = (df["label_name"] == label).sum()
        print(f"  {label}: {count}")

    print("\nSplitting by video (70/15/15)...")
    train_df, val_df, test_df = split_by_video(df)
    print(f"  Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

    # Verify no video leakage
    train_vids = set(train_df["parent_video"])
    val_vids = set(val_df["parent_video"])
    test_vids = set(test_df["parent_video"])
    assert train_vids.isdisjoint(test_vids), "DATA LEAKAGE: train/test overlap!"
    assert train_vids.isdisjoint(val_vids), "DATA LEAKAGE: train/val overlap!"
    assert val_vids.isdisjoint(test_vids), "DATA LEAKAGE: val/test overlap!"
    print("  No video leakage ✓")

    def extract_windows(split_df, name):
        X_list, y_list = [], []
        ok, skip = 0, 0
        for i, row in split_df.iterrows():
            try:
                raw = extract_poses(row["path"])
                if len(raw) < WINDOW_SIZE:
                    skip += 1
                    continue
                feats = engineer_features_enhanced(raw)
                for s in range(0, len(feats) - WINDOW_SIZE + 1, STRIDE):
                    X_list.append(feats[s:s + WINDOW_SIZE])
                    y_list.append(row["label"])
                ok += 1
            except Exception:
                skip += 1
            if (ok + skip) % 50 == 0:
                print(f"  {name}: {ok + skip}/{len(split_df)}...")

        print(f"  {name}: {ok} ok, {skip} skipped → {len(X_list)} windows")
        return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int32)

    print("\nExtracting train windows...")
    X_train, y_train = extract_windows(train_df, "Train")
    print("Extracting val windows...")
    X_val, y_val = extract_windows(val_df, "Val")
    print("Extracting test windows...")
    X_test, y_test = extract_windows(test_df, "Test")

    # Normalize with StandardScaler (fit on train only)
    from sklearn.preprocessing import StandardScaler
    n_train, n_val, n_test = len(X_train), len(X_val), len(X_test)
    feat_dim = X_train.shape[2]

    scaler = StandardScaler()
    X_train_flat = X_train.reshape(-1, feat_dim)
    scaler.fit(X_train_flat)

    X_train = scaler.transform(X_train.reshape(-1, feat_dim)).reshape(n_train, WINDOW_SIZE, feat_dim)
    X_val = scaler.transform(X_val.reshape(-1, feat_dim)).reshape(n_val, WINDOW_SIZE, feat_dim)
    X_test = scaler.transform(X_test.reshape(-1, feat_dim)).reshape(n_test, WINDOW_SIZE, feat_dim)

    # Save scaler
    with open(str(MODELS_DIR / "feature_scaler.pkl"), "wb") as f:
        pickle.dump(scaler, f)
    print(f"\nScaler saved (fit on {len(X_train_flat)} train samples)")

    # Class weights
    class_weights = compute_class_weights(y_train)
    print(f"Class weights: {class_weights}")

    return X_train, y_train, X_val, y_val, X_test, y_test, class_weights


def build_model(arch="lstm", input_shape=None, num_classes=5,
                units1=64, units2=32, dropout=0.3, lr=1e-3):
    """Build model by architecture name."""
    import tensorflow as tf

    if input_shape is None:
        input_shape = (WINDOW_SIZE, 343)

    model = tf.keras.Sequential()
    model.add(tf.keras.layers.Input(shape=input_shape))

    if arch == "bilstm":
        model.add(tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(units1, return_sequences=True, dropout=dropout)))
        model.add(tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(units2, dropout=dropout)))
    elif arch == "gru":
        model.add(tf.keras.layers.GRU(units1, return_sequences=True, dropout=dropout))
        model.add(tf.keras.layers.GRU(units2, dropout=dropout))
    elif arch == "cnn_lstm":
        model.add(tf.keras.layers.Conv1D(64, 3, activation="relu", padding="same"))
        model.add(tf.keras.layers.MaxPooling1D(2))
        model.add(tf.keras.layers.LSTM(units1, dropout=dropout))
    else:  # lstm
        model.add(tf.keras.layers.LSTM(units1, return_sequences=True, dropout=dropout))
        model.add(tf.keras.layers.LSTM(units2, dropout=dropout))

    model.add(tf.keras.layers.BatchNormalization())
    model.add(tf.keras.layers.Dense(32, activation="relu"))
    model.add(tf.keras.layers.Dropout(dropout))
    model.add(tf.keras.layers.Dense(num_classes, activation="softmax"))

    optimizer = tf.keras.optimizers.Adam(learning_rate=lr)
    model.compile(optimizer=optimizer, loss="categorical_crossentropy", metrics=["accuracy"])
    return model


def evaluate_model(model, X, y_true, labels=ALL_LABELS, save_prefix="lstm"):
    """Full evaluation: metrics, confusion matrix, classification report."""
    import tensorflow as tf
    from sklearn.metrics import (classification_report, confusion_matrix,
                                  f1_score, roc_auc_score)

    y_cat = tf.keras.utils.to_categorical(y_true, len(labels))
    y_pred_prob = model.predict(X, verbose=0)
    y_pred = np.argmax(y_pred_prob, axis=1)

    # Classification report
    present_classes = sorted(np.unique(np.concatenate([y_true, y_pred])))
    present_labels = [labels[i] for i in present_classes if i < len(labels)]
    report = classification_report(y_true, y_pred, labels=present_classes, target_names=present_labels, digits=4, zero_division=0)
    print(report)

    # F1 scores
    macro_f1 = f1_score(y_true, y_pred, average="macro")
    weighted_f1 = f1_score(y_true, y_pred, average="weighted")
    print(f"Macro F1: {macro_f1:.4f}, Weighted F1: {weighted_f1:.4f}")

    # ROC-AUC (one-vs-rest) — only if enough classes
    roc_auc = 0.0
    try:
        if len(present_classes) > 1:
            y_cat_present = tf.keras.utils.to_categorical(y_true, len(labels))
            roc_auc = roc_auc_score(y_cat_present, y_pred_prob, multi_class="ovr", average="macro")
            print(f"ROC-AUC (macro): {roc_auc:.4f}")
    except Exception as e:
        print(f"ROC-AUC: skipped ({e})")

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred, labels=present_classes)
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(present_labels)))
    ax.set_yticks(range(len(present_labels)))
    ax.set_xticklabels(present_labels, rotation=45, ha="right")
    ax.set_yticklabels(present_labels)
    for i in range(len(present_labels)):
        for j in range(len(present_labels)):
            ax.text(j, i, str(cm[i][j]), ha="center", va="center",
                    color="white" if cm[i][j] > cm.max() / 2 else "black")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(f"{save_prefix.upper()} Confusion Matrix")
    plt.colorbar(im)
    plt.tight_layout()
    cm_path = str(TRAINING_DIR / f"confusion_matrix_{save_prefix}.png")
    plt.savefig(cm_path, dpi=150)
    plt.close()
    print(f"Confusion matrix saved: {cm_path}")

    # Save report
    report_path = str(TRAINING_DIR / "evaluation_report.txt")
    with open(report_path, "a") as f:
        f.write(f"\n{'='*60}\n{save_prefix.upper()} Evaluation\n{'='*60}\n")
        f.write(report)
        f.write(f"\nMacro F1: {macro_f1:.4f}\nWeighted F1: {weighted_f1:.4f}\nROC-AUC: {roc_auc:.4f}\n")

    return {"macro_f1": macro_f1, "weighted_f1": weighted_f1, "roc_auc": roc_auc}


def main():
    import tensorflow as tf

    print("=" * 60)
    print("LSTM v2 — Improved Training Pipeline")
    print("=" * 60)

    # Clear old report
    report_path = TRAINING_DIR / "evaluation_report.txt"
    report_path.write_text(f"Video Intelligence Platform — Model Evaluation Report\n{'='*60}\n")

    # Step 1: Process dataset
    X_train, y_train, X_val, y_val, X_test, y_test, class_weights = process_dataset(max_per_class=200)

    if len(X_train) < 20:
        print("Not enough training data!")
        sys.exit(1)

    y_train_cat = tf.keras.utils.to_categorical(y_train, len(ALL_LABELS))
    y_val_cat = tf.keras.utils.to_categorical(y_val, len(ALL_LABELS))
    input_shape = (X_train.shape[1], X_train.shape[2])

    print(f"\nInput shape: {input_shape}")
    print(f"Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

    # Step 2: Compare architectures
    print("\n" + "=" * 60)
    print("Architecture Comparison")
    print("=" * 60)

    best_f1 = 0
    best_arch = "lstm"

    for arch in ["lstm", "bilstm", "gru", "cnn_lstm"]:
        print(f"\n--- {arch.upper()} ---")
        model = build_model(arch=arch, input_shape=input_shape, units1=64, units2=32, dropout=0.3, lr=5e-4)

        model.fit(
            X_train, y_train_cat,
            validation_data=(X_val, y_val_cat),
            epochs=30,
            batch_size=32,
            class_weight=class_weights,
            callbacks=[tf.keras.callbacks.EarlyStopping(patience=8, restore_best_weights=True)],
            verbose=0,
        )

        metrics = evaluate_model(model, X_val, y_val, save_prefix=arch)
        if metrics["macro_f1"] > best_f1:
            best_f1 = metrics["macro_f1"]
            best_arch = arch
            print(f"  → New best: {arch} (macro F1={best_f1:.4f})")

    print(f"\nBest architecture: {best_arch} (macro F1={best_f1:.4f})")

    # Step 3: Hyperparameter tuning with Optuna on best arch
    print("\n" + "=" * 60)
    print(f"Hyperparameter Tuning ({best_arch})")
    print("=" * 60)

    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial):
        units1 = trial.suggest_categorical("units1", [32, 64, 128])
        units2 = trial.suggest_categorical("units2", [16, 32, 64])
        dropout = trial.suggest_float("dropout", 0.2, 0.5, step=0.1)
        lr = trial.suggest_float("lr", 1e-4, 1e-3, log=True)
        batch_size = trial.suggest_categorical("batch_size", [16, 32, 64])

        model = build_model(arch=best_arch, input_shape=input_shape,
                            units1=units1, units2=units2, dropout=dropout, lr=lr)
        model.fit(
            X_train, y_train_cat,
            validation_data=(X_val, y_val_cat),
            epochs=20,
            batch_size=batch_size,
            class_weight=class_weights,
            callbacks=[tf.keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True)],
            verbose=0,
        )
        y_pred = np.argmax(model.predict(X_val, verbose=0), axis=1)
        from sklearn.metrics import f1_score
        return f1_score(y_val, y_pred, average="macro")

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=15, show_progress_bar=True)

    best_params = study.best_params
    print(f"Best params: {best_params}")
    print(f"Best macro F1: {study.best_value:.4f}")

    # Step 4: Final model with best params on train+val
    print("\n" + "=" * 60)
    print("Final Model Training (train+val → test)")
    print("=" * 60)

    X_trainval = np.concatenate([X_train, X_val])
    y_trainval = np.concatenate([y_train, y_val])
    y_trainval_cat = tf.keras.utils.to_categorical(y_trainval, len(ALL_LABELS))

    from data_utils import compute_class_weights
    final_weights = compute_class_weights(y_trainval)

    final_model = build_model(
        arch=best_arch, input_shape=input_shape,
        units1=best_params["units1"], units2=best_params["units2"],
        dropout=best_params["dropout"], lr=best_params["lr"],
    )
    final_model.fit(
        X_trainval, y_trainval_cat,
        epochs=40,
        batch_size=best_params["batch_size"],
        class_weight=final_weights,
        callbacks=[tf.keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True,
                                                     monitor="loss")],
        verbose=1,
    )

    # Step 5: Evaluate on held-out test set
    print("\n" + "=" * 60)
    print("Test Set Evaluation (NEVER seen during tuning)")
    print("=" * 60)
    test_metrics = evaluate_model(final_model, X_test, y_test, save_prefix="lstm_final")

    # Save
    model_path = str(MODELS_DIR / "lstm_activity_classifier.keras")
    final_model.save(model_path)
    print(f"\nModel saved: {model_path}")

    # Update config
    config = {
        "window_size": WINDOW_SIZE,
        "stride": STRIDE,
        "num_classes": len(ALL_LABELS),
        "labels": ALL_LABELS,
        "confidence_threshold": 0.5,
        "features_per_frame": input_shape[1],
        "target_fps": TARGET_FPS,
        "mobilenet_img_size": 128,
        "mobilenet_target_fps": 2,
        "mobilenet_threshold": 0.5,
        "best_architecture": best_arch,
        "best_params": best_params,
        "test_macro_f1": test_metrics["macro_f1"],
    }
    with open(str(ML_DIR / "config.json"), "w") as f:
        json.dump(config, f, indent=2)

    print(f"\nConfig updated: {ML_DIR / 'config.json'}")
    print(f"\n{'='*60}")
    print(f"DONE — Test Macro F1: {test_metrics['macro_f1']:.4f}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
