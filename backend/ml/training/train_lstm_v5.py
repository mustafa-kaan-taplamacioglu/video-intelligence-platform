"""
LSTM v5 — Concatenated Clips + Higher FPS (Binary Classification)

Key improvement: sub-clips from the same parent video are concatenated back
into one long sequence, giving LSTM real temporal context (2+ minutes instead of 2 seconds).

Pipeline:
1. Group sub-clips by parent video, sort by index
2. Concatenate pose sequences per parent → long temporal sequences
3. Frame-level labels from CSV (each sub-clip's label maps to its frames)
4. Window label = majority vote (>50% suspicious frames → suspicious window)
5. Split by parent video (no leakage)
6. 8fps, window=20 frames (2.5s), stride=10
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
TARGET_FPS = 8
WINDOW_SIZE = 20
STRIDE = 10


def extract_poses_single(video_path: str) -> np.ndarray:
    """Extract poses from one sub-clip at TARGET_FPS."""
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
    return np.array(landmarks, dtype=np.float32) if landmarks else np.zeros((0, 132), dtype=np.float32)


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


def load_parent_videos():
    """Load dataset grouped by parent video with sub-clip order + labels."""
    parents = {}  # parent_id → {"class": str, "clips": [(index, path, label), ...]}

    for cls in ["Shoplifting", "Stealing", "Burglary", "Robbery"]:
        csv_path = DCSASS / "Labels" / f"{cls}.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path, header=None, names=["fn", "c", "abn"])
        cls_dir = DCSASS / cls

        for _, row in df.iterrows():
            match = re.match(r"([A-Za-z]+\d+_x264)", row["fn"])
            if not match:
                continue
            parent_id = match.group(1)
            # Extract clip index
            idx_match = re.search(r"_(\d+)$", row["fn"])
            clip_idx = int(idx_match.group(1)) if idx_match else 0

            matches = list(cls_dir.rglob(f"{row['fn']}.mp4"))
            if not matches or not matches[0].is_file():
                continue

            if parent_id not in parents:
                parents[parent_id] = {"class": cls, "clips": []}
            parents[parent_id]["clips"].append((clip_idx, str(matches[0]), int(row["abn"])))

    # Sort clips within each parent by index
    for pid in parents:
        parents[pid]["clips"].sort(key=lambda x: x[0])

    return parents


def process_parent_video(parent_data):
    """
    Concatenate sub-clips → extract poses → engineer features → create labeled windows.
    Returns (windows, window_labels) or (None, None) on failure.
    """
    clips = parent_data["clips"]
    all_poses = []
    frame_labels = []

    for clip_idx, clip_path, clip_label in clips:
        poses = extract_poses_single(clip_path)
        if len(poses) == 0:
            continue
        all_poses.append(poses)
        frame_labels.extend([clip_label] * len(poses))

    if not all_poses:
        return None, None

    # Concatenate all sub-clip poses into one sequence
    full_sequence = np.concatenate(all_poses, axis=0)
    frame_labels = np.array(frame_labels, dtype=np.int32)

    if len(full_sequence) < WINDOW_SIZE:
        return None, None

    # Engineer features
    features = engineer_features(full_sequence)

    # Create windows with majority-vote labels
    windows, labels = [], []
    for start in range(0, len(features) - WINDOW_SIZE + 1, STRIDE):
        window = features[start:start + WINDOW_SIZE]
        window_frame_labels = frame_labels[start:start + WINDOW_SIZE]
        # Majority vote: >50% suspicious → suspicious
        label = 1 if window_frame_labels.mean() > 0.5 else 0
        windows.append(window)
        labels.append(label)

    return np.array(windows, dtype=np.float32), np.array(labels, dtype=np.int32)


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
    else:
        m.add(tf.keras.layers.LSTM(units1, return_sequences=True, dropout=dropout))
        m.add(tf.keras.layers.LSTM(units2, dropout=dropout))
    m.add(tf.keras.layers.BatchNormalization())
    m.add(tf.keras.layers.Dense(32, activation="relu"))
    m.add(tf.keras.layers.Dropout(dropout))
    m.add(tf.keras.layers.Dense(1, activation="sigmoid"))
    m.compile(optimizer=tf.keras.optimizers.Adam(lr), loss="binary_crossentropy", metrics=["accuracy"])
    return m


def full_evaluate(model, X, y_true, prefix="model"):
    from sklearn.metrics import (classification_report, confusion_matrix,
                                  f1_score, roc_auc_score, average_precision_score)
    y_prob = model.predict(X, verbose=0).flatten()
    y_pred = (y_prob > 0.5).astype(int)

    report = classification_report(y_true, y_pred, target_names=LABELS, digits=4, zero_division=0)
    print(report)

    acc = (y_pred == y_true).mean()
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    weighted_f1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)
    try: roc_auc = roc_auc_score(y_true, y_prob)
    except: roc_auc = 0.0
    try: pr_auc = average_precision_score(y_true, y_prob)
    except: pr_auc = 0.0

    print(f"Accuracy: {acc:.4f} | Macro F1: {macro_f1:.4f} | ROC-AUC: {roc_auc:.4f} | PR-AUC: {pr_auc:.4f}")

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
    ax.set_title(f"{prefix} — Acc={acc:.1%} F1={macro_f1:.4f} AUC={roc_auc:.4f}")
    plt.tight_layout()
    plt.savefig(str(TRAINING_DIR / f"confusion_matrix_{prefix}.png"), dpi=150)
    plt.close()

    with open(str(TRAINING_DIR / "evaluation_report.txt"), "a") as f:
        f.write(f"\n{'='*60}\n{prefix.upper()}\n{'='*60}\n{report}")
        f.write(f"Accuracy: {acc:.4f} | Macro F1: {macro_f1:.4f} | ROC-AUC: {roc_auc:.4f} | PR-AUC: {pr_auc:.4f}\n")

    return {"accuracy": acc, "macro_f1": macro_f1, "roc_auc": roc_auc, "pr_auc": pr_auc}


def main():
    import tensorflow as tf
    from sklearn.preprocessing import StandardScaler
    from sklearn.utils.class_weight import compute_class_weight
    from sklearn.model_selection import GroupShuffleSplit

    print("=" * 60)
    print("LSTM v5 — Concatenated Clips + 8fps")
    print(f"WIN={WINDOW_SIZE} STRIDE={STRIDE} FPS={TARGET_FPS}")
    print("=" * 60)

    (TRAINING_DIR / "evaluation_report.txt").write_text("Video Intelligence Platform — LSTM v5 Evaluation\n")

    # 1. Load parent videos
    print("\n1. Loading parent videos...")
    parents = load_parent_videos()
    parent_ids = list(parents.keys())
    print(f"   {len(parent_ids)} parent videos across 4 classes")
    for cls in ["Shoplifting", "Stealing", "Burglary", "Robbery"]:
        count = sum(1 for p in parents.values() if p["class"] == cls)
        clips = sum(len(p["clips"]) for p in parents.values() if p["class"] == cls)
        print(f"   {cls}: {count} videos, {clips} total sub-clips")

    # 2. Split parent videos (not sub-clips)
    print("\n2. Splitting by parent video...")
    # Create a DF of parent videos for splitting
    parent_df = pd.DataFrame([
        {"parent_id": pid, "has_suspicious": any(c[2] == 1 for c in pdata["clips"])}
        for pid, pdata in parents.items()
    ])
    parent_df["label"] = parent_df["has_suspicious"].astype(int)

    gss1 = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=42)
    tv_idx, test_idx = next(gss1.split(parent_df, parent_df.label, groups=parent_df.parent_id))
    tv_df = parent_df.iloc[tv_idx]
    test_pids = set(parent_df.iloc[test_idx].parent_id)

    gss2 = GroupShuffleSplit(n_splits=1, test_size=0.176, random_state=43)
    train_idx, val_idx = next(gss2.split(tv_df, tv_df.label, groups=tv_df.parent_id))
    train_pids = set(tv_df.iloc[train_idx].parent_id)
    val_pids = set(tv_df.iloc[val_idx].parent_id)

    assert train_pids.isdisjoint(test_pids) and train_pids.isdisjoint(val_pids) and val_pids.isdisjoint(test_pids)
    print(f"   Train: {len(train_pids)} | Val: {len(val_pids)} | Test: {len(test_pids)} — no leakage ✓")

    # 3. Process each parent video → concatenated windows
    def process_split(pids, name):
        X_all, y_all = [], []
        ok, skip = 0, 0
        pid_list = sorted(pids)
        for i, pid in enumerate(pid_list):
            windows, labels = process_parent_video(parents[pid])
            if windows is not None and len(windows) > 0:
                X_all.append(windows)
                y_all.append(labels)
                ok += 1
            else:
                skip += 1
            if (i + 1) % 10 == 0:
                print(f"   {name}: {i+1}/{len(pid_list)} ({ok} ok, {skip} skip)")

        if not X_all:
            return np.zeros((0, WINDOW_SIZE, 231), dtype=np.float32), np.array([], dtype=np.int32)
        X = np.concatenate(X_all)
        y = np.concatenate(y_all)
        print(f"   {name}: {ok} videos → {len(X)} windows (Normal={int((y==0).sum())}, Susp={int((y==1).sum())})")
        return X, y

    print("\n3. Processing train videos...")
    X_train, y_train = process_split(train_pids, "Train")
    print("\n   Processing val videos...")
    X_val, y_val = process_split(val_pids, "Val")
    print("\n   Processing test videos...")
    X_test, y_test = process_split(test_pids, "Test")

    if len(X_train) < 100:
        print("NOT ENOUGH DATA!"); sys.exit(1)

    # 4. Normalize
    print("\n4. Normalizing (fit on train only)...")
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
    aug_X, aug_y = [X_train], [y_train]
    for _ in range(2):
        aug_X.append(X_train + np.random.normal(0, 0.008, X_train.shape).astype(np.float32))
        aug_y.append(y_train)
    X_train = np.concatenate(aug_X)
    y_train = np.concatenate(aug_y)
    print(f"   After: Train={len(X_train)} Val={len(X_val)} Test={len(X_test)}")

    # 6. Class weights
    cw = compute_class_weight("balanced", classes=np.array([0, 1]), y=y_train)
    class_weights = {0: float(cw[0]), 1: float(cw[1])}
    print(f"   Class weights: {class_weights}")

    input_shape = (WINDOW_SIZE, feat_dim)
    y_train_f, y_val_f = y_train.astype(np.float32), y_val.astype(np.float32)

    # 7. Architecture comparison
    print("\n" + "=" * 60)
    print("7. Architecture Comparison")
    best_f1, best_arch = 0, "lstm"
    for arch in ["lstm", "bilstm", "gru", "cnn_lstm"]:
        print(f"\n--- {arch.upper()} ---")
        m = build_model(arch, input_shape)
        m.fit(X_train, y_train_f, validation_data=(X_val, y_val_f), epochs=25, batch_size=32,
              class_weight=class_weights,
              callbacks=[tf.keras.callbacks.EarlyStopping(patience=6, restore_best_weights=True)], verbose=0)
        metrics = full_evaluate(m, X_val, y_val, prefix=f"val_{arch}")
        if metrics["macro_f1"] > best_f1:
            best_f1, best_arch = metrics["macro_f1"], arch
            print(f"  → New best!")
    print(f"\nBest: {best_arch} (F1={best_f1:.4f})")

    # 8. Optuna
    print("\n" + "=" * 60)
    print(f"8. Optuna ({best_arch})")
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

    # 9. Cross-validation
    print("\n" + "=" * 60)
    print("9. 5-Fold CV")
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import f1_score

    X_tv = np.concatenate([X_train, X_val])
    y_tv = np.concatenate([y_train, y_val])

    cv_scores = []
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    for fold, (tr_idx, va_idx) in enumerate(skf.split(X_tv, y_tv)):
        m = build_model(best_arch, input_shape, bp["u1"], bp["u2"], bp["dr"], bp["lr"])
        m.fit(X_tv[tr_idx], y_tv[tr_idx].astype(np.float32), epochs=15, batch_size=bp["bs"],
              class_weight=class_weights, verbose=0,
              callbacks=[tf.keras.callbacks.EarlyStopping(patience=4, restore_best_weights=True, monitor="loss")])
        yp = (m.predict(X_tv[va_idx], verbose=0).flatten() > 0.5).astype(int)
        fold_f1 = f1_score(y_tv[va_idx], yp, average="macro", zero_division=0)
        cv_scores.append(fold_f1)
        print(f"  Fold {fold+1}: {fold_f1:.4f}")
    cv_mean, cv_std = np.mean(cv_scores), np.std(cv_scores)
    print(f"  Mean: {cv_mean:.4f} ± {cv_std:.4f}")

    with open(str(TRAINING_DIR / "evaluation_report.txt"), "a") as f:
        f.write(f"\n{'='*60}\n5-FOLD CV\nFolds: {[f'{s:.4f}' for s in cv_scores]}\nMean: {cv_mean:.4f} ± {cv_std:.4f}\n")

    # 10. Final model
    print("\n" + "=" * 60)
    print("10. Final Model → Test")
    cw2 = compute_class_weight("balanced", classes=np.array([0, 1]), y=y_tv)
    final = build_model(best_arch, input_shape, bp["u1"], bp["u2"], bp["dr"], bp["lr"])
    final.fit(X_tv, y_tv.astype(np.float32), epochs=40, batch_size=bp["bs"],
              class_weight={0: float(cw2[0]), 1: float(cw2[1])}, verbose=1,
              callbacks=[tf.keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True, monitor="loss")])

    print("\nTEST SET (never seen)")
    test_metrics = full_evaluate(final, X_test, y_test, prefix="v5_final_test")

    final.save(str(MODELS_DIR / "lstm_activity_classifier.keras"))
    config = {
        "window_size": WINDOW_SIZE, "stride": STRIDE, "num_classes": 2, "labels": LABELS,
        "confidence_threshold": 0.5, "features_per_frame": feat_dim, "target_fps": TARGET_FPS,
        "mobilenet_img_size": 128, "mobilenet_target_fps": 2, "mobilenet_threshold": 0.5,
        "best_architecture": best_arch, "best_params": bp,
        "cv_macro_f1": f"{cv_mean:.4f} ± {cv_std:.4f}",
        "test_accuracy": test_metrics["accuracy"], "test_macro_f1": test_metrics["macro_f1"],
        "test_roc_auc": test_metrics["roc_auc"], "test_pr_auc": test_metrics["pr_auc"],
    }
    with open(str(ML_DIR / "config.json"), "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n{'='*60}\nDONE — Test: Acc={test_metrics['accuracy']:.1%} F1={test_metrics['macro_f1']:.4f} AUC={test_metrics['roc_auc']:.4f}\n{'='*60}")


if __name__ == "__main__":
    main()
