"""
LSTM v4 — Binary Classification (Normal vs Suspicious)
Maximum performance with proper ML engineering.

Pipeline:
1. Load ALL DCSASS clips → binary labels (normal=0, suspicious=1)
2. Video-level split (70/15/15) — no data leakage
3. Pose extraction (MediaPipe Tasks API, 3fps)
4. Feature engineering (231-dim)
5. StandardScaler fit on train only
6. Augmentation on train only
7. Compare 4 architectures
8. Optuna hyperparameter tuning (15 trials)
9. 5-fold GroupKFold cross-validation
10. Final model on train+val → evaluate on test
11. Full metrics: Accuracy, P/R/F1, ROC-AUC, PR-AUC, confusion matrix
"""

import sys
import json
import pickle
import re
import warnings
from pathlib import Path
from collections import defaultdict

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
DCSASS = Path.home() / ".cache/kagglehub/datasets/mateohervas/dcsass-dataset/versions/1/DCSASS Dataset"

LABELS = ["Normal", "Suspicious"]
TARGET_FPS = 3
WINDOW_SIZE = 4
STRIDE = 2


# ============================================================
# POSE EXTRACTION
# ============================================================

def extract_poses(video_path: str) -> np.ndarray:
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
        running_mode=RunningMode.VIDEO, num_poses=1)

    with PoseLandmarker.create_from_options(options) as lm:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % interval == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = lm.detect_for_video(img, int(idx * 1000 / fps))
                if result.pose_landmarks and len(result.pose_landmarks) > 0:
                    kp = []
                    for p in result.pose_landmarks[0]:
                        kp.extend([p.x, p.y, p.z, p.visibility])
                    landmarks.append(kp)
                else:
                    landmarks.append([0.0] * 132)
            idx += 1
    cap.release()
    return np.array(landmarks, dtype=np.float32)


def engineer_features(raw: np.ndarray) -> np.ndarray:
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


# ============================================================
# DATA LOADING + SPLITTING
# ============================================================

def load_binary_clips():
    """Load all clips with binary labels. No cap — use everything."""
    records = []
    for cls in ["Shoplifting", "Stealing", "Burglary", "Robbery"]:
        csv_path = DCSASS / "Labels" / f"{cls}.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path, header=None, names=["fn", "c", "abn"])
        cls_dir = DCSASS / cls
        for _, row in df.iterrows():
            matches = list(cls_dir.rglob(f"{row['fn']}.mp4"))
            if not matches or not matches[0].is_file():
                continue
            parent = re.match(r"([A-Za-z]+\d+)", row["fn"])
            records.append({
                "path": str(matches[0]),
                "label": int(row["abn"]),  # 0=normal, 1=suspicious
                "parent": parent.group(1) if parent else row["fn"],
            })
    return pd.DataFrame(records)


def split_by_video(df):
    from sklearn.model_selection import GroupShuffleSplit
    gss1 = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=42)
    tv_idx, test_idx = next(gss1.split(df, df.label, groups=df.parent))
    tv_df, test_df = df.iloc[tv_idx], df.iloc[test_idx]
    gss2 = GroupShuffleSplit(n_splits=1, test_size=0.176, random_state=43)
    train_idx, val_idx = next(gss2.split(tv_df, tv_df.label, groups=tv_df.parent))
    train_df = tv_df.iloc[train_idx].reset_index(drop=True)
    val_df = tv_df.iloc[val_idx].reset_index(drop=True)
    test_df = test_df.reset_index(drop=True)
    # Verify no leakage
    assert set(train_df.parent).isdisjoint(set(test_df.parent))
    assert set(train_df.parent).isdisjoint(set(val_df.parent))
    assert set(val_df.parent).isdisjoint(set(test_df.parent))
    return train_df, val_df, test_df


def extract_windows(split_df, name, max_clips=None):
    X, y = [], []
    ok, skip = 0, 0
    clips = split_df if max_clips is None else split_df.sample(min(max_clips, len(split_df)), random_state=42)
    for _, row in clips.iterrows():
        try:
            raw = extract_poses(row["path"])
            if len(raw) < WINDOW_SIZE:
                skip += 1
                continue
            feats = engineer_features(raw)
            for s in range(0, len(feats) - WINDOW_SIZE + 1, STRIDE):
                X.append(feats[s:s + WINDOW_SIZE])
                y.append(row["label"])
            ok += 1
        except:
            skip += 1
        if (ok + skip) % 200 == 0:
            print(f"  {name}: {ok + skip}/{len(clips)} processed...")
    print(f"  {name}: {ok} ok, {skip} skipped → {len(X)} windows")
    if not X:
        return np.zeros((0, WINDOW_SIZE, 231), dtype=np.float32), np.array([], dtype=np.int32)
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)


def augment_train(X, y, factor=2):
    aug_X, aug_y = [X], [y]
    for _ in range(factor):
        noise = np.random.normal(0, 0.008, X.shape).astype(np.float32)
        aug_X.append(X + noise)
        aug_y.append(y)
    return np.concatenate(aug_X), np.concatenate(aug_y)


# ============================================================
# MODEL BUILDING
# ============================================================

def build_model(arch, input_shape, units1=64, units2=32, dropout=0.3, lr=5e-4):
    import tensorflow as tf
    m = tf.keras.Sequential()
    m.add(tf.keras.layers.Input(shape=input_shape))
    if arch == "bilstm":
        m.add(tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(units1, return_sequences=True, dropout=dropout)))
        m.add(tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(units2, dropout=dropout)))
    elif arch == "gru":
        m.add(tf.keras.layers.GRU(units1, return_sequences=True, dropout=dropout))
        m.add(tf.keras.layers.GRU(units2, dropout=dropout))
    elif arch == "cnn_lstm":
        m.add(tf.keras.layers.Conv1D(64, 3, activation="relu", padding="same"))
        m.add(tf.keras.layers.LSTM(units1, dropout=dropout))
    else:  # lstm
        m.add(tf.keras.layers.LSTM(units1, return_sequences=True, dropout=dropout))
        m.add(tf.keras.layers.LSTM(units2, dropout=dropout))
    m.add(tf.keras.layers.BatchNormalization())
    m.add(tf.keras.layers.Dense(32, activation="relu"))
    m.add(tf.keras.layers.Dropout(dropout))
    m.add(tf.keras.layers.Dense(1, activation="sigmoid"))  # BINARY
    m.compile(optimizer=tf.keras.optimizers.Adam(lr), loss="binary_crossentropy",
              metrics=["accuracy"])
    return m


# ============================================================
# EVALUATION
# ============================================================

def full_evaluate(model, X, y_true, prefix="model"):
    from sklearn.metrics import (classification_report, confusion_matrix,
                                  f1_score, roc_auc_score, average_precision_score)

    y_pred_prob = model.predict(X, verbose=0).flatten()
    y_pred = (y_pred_prob > 0.5).astype(int)

    report = classification_report(y_true, y_pred, target_names=LABELS, digits=4, zero_division=0)
    print(report)

    acc = (y_pred == y_true).mean()
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    weighted_f1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)

    try:
        roc_auc = roc_auc_score(y_true, y_pred_prob)
    except:
        roc_auc = 0.0
    try:
        pr_auc = average_precision_score(y_true, y_pred_prob)
    except:
        pr_auc = 0.0

    print(f"Accuracy: {acc:.4f} | Macro F1: {macro_f1:.4f} | Weighted F1: {weighted_f1:.4f}")
    print(f"ROC-AUC: {roc_auc:.4f} | PR-AUC: {pr_auc:.4f}")

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(LABELS); ax.set_yticklabels(LABELS)
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i][j]), ha="center", va="center",
                    color="white" if cm[i][j] > cm.max() / 2 else "black")
    ax.set_xlabel("Predicted"); ax.set_ylabel("True")
    ax.set_title(f"{prefix} — Acc={acc:.2%} F1={macro_f1:.4f} AUC={roc_auc:.4f}")
    plt.tight_layout()
    plt.savefig(str(TRAINING_DIR / f"confusion_matrix_{prefix}.png"), dpi=150)
    plt.close()

    with open(str(TRAINING_DIR / "evaluation_report.txt"), "a") as f:
        f.write(f"\n{'=' * 60}\n{prefix.upper()}\n{'=' * 60}\n{report}")
        f.write(f"Accuracy: {acc:.4f} | Macro F1: {macro_f1:.4f} | ROC-AUC: {roc_auc:.4f} | PR-AUC: {pr_auc:.4f}\n")

    return {"accuracy": acc, "macro_f1": macro_f1, "roc_auc": roc_auc, "pr_auc": pr_auc}


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():
    import tensorflow as tf
    from sklearn.preprocessing import StandardScaler
    from sklearn.utils.class_weight import compute_class_weight

    print("=" * 60)
    print("LSTM v4 — Binary Classification")
    print(f"WIN={WINDOW_SIZE} STRIDE={STRIDE} FPS={TARGET_FPS}")
    print("=" * 60)

    (TRAINING_DIR / "evaluation_report.txt").write_text("Video Intelligence Platform — LSTM v4 Binary Evaluation\n")

    # 1. Load data
    print("\n1. Loading clips...")
    df = load_binary_clips()
    print(f"   Total: {len(df)} (Normal={int((df.label == 0).sum())}, Suspicious={int((df.label == 1).sum())})")

    # 2. Video-level split
    print("\n2. Splitting by video...")
    train_df, val_df, test_df = split_by_video(df)
    print(f"   Train={len(train_df)} Val={len(val_df)} Test={len(test_df)} — no leakage ✓")

    # 3. Extract windows
    print("\n3. Extracting poses + windows...")
    X_train, y_train = extract_windows(train_df, "Train", max_clips=3000)
    X_val, y_val = extract_windows(val_df, "Val", max_clips=700)
    X_test, y_test = extract_windows(test_df, "Test", max_clips=700)

    if len(X_train) < 100:
        print("NOT ENOUGH DATA"); sys.exit(1)

    # 4. Normalize (fit on train only)
    print("\n4. Normalizing...")
    feat_dim = X_train.shape[2]
    scaler = StandardScaler()
    scaler.fit(X_train.reshape(-1, feat_dim))
    X_train = scaler.transform(X_train.reshape(-1, feat_dim)).reshape(-1, WINDOW_SIZE, feat_dim).astype(np.float32)
    X_val = scaler.transform(X_val.reshape(-1, feat_dim)).reshape(-1, WINDOW_SIZE, feat_dim).astype(np.float32)
    X_test = scaler.transform(X_test.reshape(-1, feat_dim)).reshape(-1, WINDOW_SIZE, feat_dim).astype(np.float32)
    with open(str(MODELS_DIR / "feature_scaler.pkl"), "wb") as f:
        pickle.dump(scaler, f)

    # 5. Augment train only
    print("\n5. Augmenting train...")
    X_train, y_train = augment_train(X_train, y_train, factor=2)
    print(f"   After augmentation: Train={len(X_train)} Val={len(X_val)} Test={len(X_test)}")
    print(f"   Train dist: Normal={int((y_train == 0).sum())} Suspicious={int((y_train == 1).sum())}")

    # 6. Class weights
    cw = compute_class_weight("balanced", classes=np.array([0, 1]), y=y_train)
    class_weights = {0: float(cw[0]), 1: float(cw[1])}
    print(f"   Class weights: {class_weights}")

    input_shape = (WINDOW_SIZE, feat_dim)
    y_train_f = y_train.astype(np.float32)
    y_val_f = y_val.astype(np.float32)

    # 7. Compare architectures
    print("\n" + "=" * 60)
    print("7. Architecture Comparison")
    print("=" * 60)
    best_f1, best_arch = 0, "lstm"
    for arch in ["lstm", "bilstm", "gru", "cnn_lstm"]:
        print(f"\n--- {arch.upper()} ---")
        m = build_model(arch, input_shape)
        m.fit(X_train, y_train_f, validation_data=(X_val, y_val_f), epochs=25, batch_size=32,
              class_weight=class_weights,
              callbacks=[tf.keras.callbacks.EarlyStopping(patience=6, restore_best_weights=True)], verbose=0)
        metrics = full_evaluate(m, X_val, y_val, prefix=f"val_{arch}")
        if metrics["macro_f1"] > best_f1:
            best_f1 = metrics["macro_f1"]
            best_arch = arch
            print(f"  → New best!")
    print(f"\nBest: {best_arch} (macro F1={best_f1:.4f})")

    # 8. Optuna tuning
    print("\n" + "=" * 60)
    print(f"8. Optuna Tuning ({best_arch})")
    print("=" * 60)
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial):
        u1 = trial.suggest_categorical("u1", [32, 64, 128])
        u2 = trial.suggest_categorical("u2", [16, 32, 64])
        dr = trial.suggest_float("dr", 0.2, 0.5, step=0.1)
        lr = trial.suggest_float("lr", 1e-4, 2e-3, log=True)
        bs = trial.suggest_categorical("bs", [16, 32, 64])
        m = build_model(best_arch, input_shape, u1, u2, dr, lr)
        m.fit(X_train, y_train_f, validation_data=(X_val, y_val_f), epochs=15, batch_size=bs,
              class_weight=class_weights,
              callbacks=[tf.keras.callbacks.EarlyStopping(patience=4, restore_best_weights=True)], verbose=0)
        yp = (m.predict(X_val, verbose=0).flatten() > 0.5).astype(int)
        from sklearn.metrics import f1_score
        return f1_score(y_val, yp, average="macro", zero_division=0)

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=15)
    bp = study.best_params
    print(f"Best: {bp}, F1={study.best_value:.4f}")

    # 9. Cross-validation (5-fold GroupKFold)
    print("\n" + "=" * 60)
    print("9. 5-Fold GroupKFold Cross-Validation")
    print("=" * 60)
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.metrics import f1_score

    # Combine train+val for CV
    X_tv = np.concatenate([X_train, X_val])
    y_tv = np.concatenate([y_train, y_val])
    # Create group IDs (approximate: use index ranges)
    groups_tv = np.concatenate([
        np.arange(len(X_train)) // 10,  # pseudo-groups for train
        np.arange(len(X_val)) // 10 + 99999,  # separate for val
    ])

    cv_scores = []
    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    for fold, (tr_idx, va_idx) in enumerate(sgkf.split(X_tv, y_tv, groups_tv)):
        m = build_model(best_arch, input_shape, bp["u1"], bp["u2"], bp["dr"], bp["lr"])
        m.fit(X_tv[tr_idx], y_tv[tr_idx].astype(np.float32), epochs=15, batch_size=bp["bs"],
              class_weight=class_weights, verbose=0,
              callbacks=[tf.keras.callbacks.EarlyStopping(patience=4, restore_best_weights=True,
                                                          monitor="loss")])
        yp = (m.predict(X_tv[va_idx], verbose=0).flatten() > 0.5).astype(int)
        fold_f1 = f1_score(y_tv[va_idx], yp, average="macro", zero_division=0)
        cv_scores.append(fold_f1)
        print(f"  Fold {fold + 1}: macro F1 = {fold_f1:.4f}")

    cv_mean = np.mean(cv_scores)
    cv_std = np.std(cv_scores)
    print(f"  CV Mean: {cv_mean:.4f} ± {cv_std:.4f}")

    with open(str(TRAINING_DIR / "evaluation_report.txt"), "a") as f:
        f.write(f"\n{'=' * 60}\nCROSS-VALIDATION (5-fold)\n{'=' * 60}\n")
        f.write(f"Folds: {[f'{s:.4f}' for s in cv_scores]}\n")
        f.write(f"Mean: {cv_mean:.4f} ± {cv_std:.4f}\n")

    # 10. Final model (train+val → test)
    print("\n" + "=" * 60)
    print("10. Final Model (train+val → test)")
    print("=" * 60)

    cw2 = compute_class_weight("balanced", classes=np.array([0, 1]), y=y_tv)
    cw_final = {0: float(cw2[0]), 1: float(cw2[1])}

    final = build_model(best_arch, input_shape, bp["u1"], bp["u2"], bp["dr"], bp["lr"])
    final.fit(X_tv, y_tv.astype(np.float32), epochs=40, batch_size=bp["bs"],
              class_weight=cw_final, verbose=1,
              callbacks=[tf.keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True, monitor="loss")])

    print("\n" + "=" * 60)
    print("TEST SET (NEVER seen during tuning)")
    print("=" * 60)
    test_metrics = full_evaluate(final, X_test, y_test, prefix="final_test")

    # Save
    final.save(str(MODELS_DIR / "lstm_activity_classifier.keras"))
    config = {
        "window_size": WINDOW_SIZE, "stride": STRIDE,
        "num_classes": 2, "labels": LABELS,
        "confidence_threshold": 0.5, "features_per_frame": feat_dim,
        "target_fps": TARGET_FPS,
        "mobilenet_img_size": 128, "mobilenet_target_fps": 2, "mobilenet_threshold": 0.5,
        "best_architecture": best_arch, "best_params": bp,
        "cv_macro_f1_mean": cv_mean, "cv_macro_f1_std": cv_std,
        "test_accuracy": test_metrics["accuracy"],
        "test_macro_f1": test_metrics["macro_f1"],
        "test_roc_auc": test_metrics["roc_auc"],
        "test_pr_auc": test_metrics["pr_auc"],
    }
    with open(str(ML_DIR / "config.json"), "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"DONE")
    print(f"  Architecture: {best_arch}")
    print(f"  CV Macro F1: {cv_mean:.4f} ± {cv_std:.4f}")
    print(f"  Test Accuracy: {test_metrics['accuracy']:.4f}")
    print(f"  Test Macro F1: {test_metrics['macro_f1']:.4f}")
    print(f"  Test ROC-AUC: {test_metrics['roc_auc']:.4f}")
    print(f"  Test PR-AUC: {test_metrics['pr_auc']:.4f}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
