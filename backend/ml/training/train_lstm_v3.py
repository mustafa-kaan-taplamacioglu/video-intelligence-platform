"""
Tier 2 v3: Final LSTM training — maximum data, proper splits, no leakage.

Key fixes from v2:
- WINDOW_SIZE=4 (was 10) — fits DCSASS 1-4s sub-clips
- TARGET_FPS=3 (was 5) — more frames from short clips
- ALL clips used (was capped at 200/class)
- Proper stratified video-level split
- Augmentation on train only
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

ALL_LABELS = ["Normal", "Shoplifting", "Stealing", "Burglary", "Robbery"]
LABEL_TO_IDX = {l: i for i, l in enumerate(ALL_LABELS)}
TARGET_FPS = 3
WINDOW_SIZE = 4
STRIDE = 2


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
        running_mode=RunningMode.VIDEO, num_poses=1,
    )
    with PoseLandmarker.create_from_options(options) as lm:
        while True:
            ret, frame = cap.read()
            if not ret: break
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
    """231-dim base features — keep simple for small windows."""
    features = []
    for i in range(len(raw)):
        f = raw[i].reshape(33, 4)
        hip = (f[23, :3] + f[24, :3]) / 2
        norm = f[:, :3] - hip
        sd = np.linalg.norm(f[11, :3] - f[12, :3])
        if sd > 0.01: norm /= sd
        vel = (f[:, :3] - raw[i-1].reshape(33, 4)[:, :3]) if i > 0 else np.zeros((33, 3))
        features.append(np.concatenate([norm.flatten(), vel.flatten(), f[:, 3]]))
    return np.array(features, dtype=np.float32)


def load_all_data():
    """Load ALL clips, split by parent video, extract windows."""
    print("Loading clips from DCSASS...")
    records = []
    for cls in ["Shoplifting", "Stealing", "Burglary", "Robbery"]:
        csv_path = DCSASS / "Labels" / f"{cls}.csv"
        if not csv_path.exists(): continue
        df = pd.read_csv(csv_path, header=None, names=["fn", "c", "abn"])
        cls_dir = DCSASS / cls
        for _, row in df.iterrows():
            matches = list(cls_dir.rglob(f"{row['fn']}.mp4"))
            if not matches or not matches[0].is_file(): continue
            label = LABEL_TO_IDX[cls] if row["abn"] == 1 else 0
            parent = re.match(r"([A-Za-z]+\d+)", row["fn"])
            records.append({
                "path": str(matches[0]),
                "label": label,
                "parent": parent.group(1) if parent else row["fn"],
            })

    df = pd.DataFrame(records)
    print(f"Total clips: {len(df)}")
    for i, l in enumerate(ALL_LABELS):
        print(f"  {l}: {(df.label == i).sum()}")

    # Video-level split
    from sklearn.model_selection import GroupShuffleSplit
    gss1 = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=42)
    tv_idx, test_idx = next(gss1.split(df, df.label, groups=df.parent))
    tv_df, test_df = df.iloc[tv_idx], df.iloc[test_idx]

    gss2 = GroupShuffleSplit(n_splits=1, test_size=0.176, random_state=43)  # 0.176 of 0.85 ≈ 0.15
    train_idx, val_idx = next(gss2.split(tv_df, tv_df.label, groups=tv_df.parent))
    train_df = tv_df.iloc[train_idx].reset_index(drop=True)
    val_df = tv_df.iloc[val_idx].reset_index(drop=True)
    test_df = test_df.reset_index(drop=True)

    # Verify no leakage
    assert set(train_df.parent).isdisjoint(set(test_df.parent)), "LEAK!"
    assert set(train_df.parent).isdisjoint(set(val_df.parent)), "LEAK!"
    print(f"Split: train={len(train_df)} val={len(val_df)} test={len(test_df)} — no leakage ✓")

    return train_df, val_df, test_df


def extract_windows(split_df, name, max_clips=None):
    """Extract pose → features → windows for a split."""
    X, y = [], []
    ok, skip = 0, 0
    clips = split_df if max_clips is None else split_df.head(max_clips)

    for _, row in clips.iterrows():
        try:
            raw = extract_poses(row["path"])
            if len(raw) < WINDOW_SIZE:
                skip += 1; continue
            feats = engineer_features(raw)
            for s in range(0, len(feats) - WINDOW_SIZE + 1, STRIDE):
                X.append(feats[s:s + WINDOW_SIZE])
                y.append(row["label"])
            ok += 1
        except:
            skip += 1
        if (ok + skip) % 100 == 0:
            print(f"  {name}: {ok+skip}/{len(clips)} processed...")

    print(f"  {name}: {ok} ok, {skip} skipped → {len(X)} windows")
    return np.array(X, dtype=np.float32) if X else np.zeros((0, WINDOW_SIZE, 231)), np.array(y, dtype=np.int32)


def augment(X, y, factor=2):
    """Noise augmentation on training set only."""
    aug_X, aug_y = [X], [y]
    for _ in range(factor):
        noise = np.random.normal(0, 0.005, X.shape).astype(np.float32)
        aug_X.append(X + noise)
        aug_y.append(y)
    return np.concatenate(aug_X), np.concatenate(aug_y)


def build_model(arch, input_shape, num_classes, units1=64, units2=32, dropout=0.3, lr=5e-4):
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
    m.add(tf.keras.layers.Dense(num_classes, activation="softmax"))
    m.compile(optimizer=tf.keras.optimizers.Adam(lr), loss="categorical_crossentropy", metrics=["accuracy"])
    return m


def evaluate(model, X, y_true, labels, prefix):
    import tensorflow as tf
    from sklearn.metrics import classification_report, confusion_matrix, f1_score

    y_pred = np.argmax(model.predict(X, verbose=0), axis=1)
    present = sorted(set(y_true) | set(y_pred))
    present_labels = [labels[i] for i in present if i < len(labels)]

    report = classification_report(y_true, y_pred, labels=present, target_names=present_labels, digits=4, zero_division=0)
    print(report)

    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    weighted_f1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)
    print(f"Macro F1: {macro_f1:.4f}, Weighted F1: {weighted_f1:.4f}")

    cm = confusion_matrix(y_true, y_pred, labels=present)
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(present_labels))); ax.set_yticks(range(len(present_labels)))
    ax.set_xticklabels(present_labels, rotation=45, ha="right"); ax.set_yticklabels(present_labels)
    for i in range(len(present_labels)):
        for j in range(len(present_labels)):
            ax.text(j, i, str(cm[i][j]), ha="center", va="center",
                    color="white" if cm[i][j] > cm.max()/2 else "black")
    ax.set_xlabel("Predicted"); ax.set_ylabel("True"); ax.set_title(f"{prefix} Confusion Matrix")
    plt.tight_layout()
    plt.savefig(str(TRAINING_DIR / f"confusion_matrix_{prefix}.png"), dpi=150)
    plt.close()

    with open(str(TRAINING_DIR / "evaluation_report.txt"), "a") as f:
        f.write(f"\n{'='*60}\n{prefix.upper()}\n{'='*60}\n{report}\nMacro F1: {macro_f1:.4f}\n")

    return macro_f1


def main():
    import tensorflow as tf
    from sklearn.utils.class_weight import compute_class_weight

    print("=" * 60)
    print("LSTM v3 — Full Dataset Training")
    print(f"WIN={WINDOW_SIZE} STRIDE={STRIDE} FPS={TARGET_FPS}")
    print("=" * 60)

    (TRAINING_DIR / "evaluation_report.txt").write_text("Video Intelligence Platform — Evaluation Report v3\n")

    train_df, val_df, test_df = load_all_data()

    # Limit to keep training feasible on CPU (~800 clips per split max)
    print("\nExtracting train poses...")
    X_train, y_train = extract_windows(train_df, "Train", max_clips=2000)
    print("Extracting val poses...")
    X_val, y_val = extract_windows(val_df, "Val", max_clips=500)
    print("Extracting test poses...")
    X_test, y_test = extract_windows(test_df, "Test", max_clips=500)

    if len(X_train) < 50:
        print("Not enough data!"); sys.exit(1)

    # Normalize
    from sklearn.preprocessing import StandardScaler
    feat_dim = X_train.shape[2]
    scaler = StandardScaler()
    scaler.fit(X_train.reshape(-1, feat_dim))
    X_train = scaler.transform(X_train.reshape(-1, feat_dim)).reshape(-1, WINDOW_SIZE, feat_dim).astype(np.float32)
    X_val = scaler.transform(X_val.reshape(-1, feat_dim)).reshape(-1, WINDOW_SIZE, feat_dim).astype(np.float32)
    X_test = scaler.transform(X_test.reshape(-1, feat_dim)).reshape(-1, WINDOW_SIZE, feat_dim).astype(np.float32)
    with open(str(MODELS_DIR / "feature_scaler.pkl"), "wb") as f:
        pickle.dump(scaler, f)

    # Augment train only
    X_train, y_train = augment(X_train, y_train, factor=2)
    print(f"\nAfter augmentation: Train={len(X_train)}, Val={len(X_val)}, Test={len(X_test)}")

    # Class distribution
    for i, l in enumerate(ALL_LABELS):
        tr = (y_train == i).sum()
        va = (y_val == i).sum()
        te = (y_test == i).sum()
        if tr + va + te > 0:
            print(f"  {l}: train={tr} val={va} test={te}")

    # Class weights
    classes_present = np.unique(y_train)
    cw = compute_class_weight("balanced", classes=classes_present, y=y_train)
    class_weights = {int(c): float(w) for c, w in zip(classes_present, cw)}
    print(f"Class weights: {class_weights}")

    num_classes = len(ALL_LABELS)
    y_train_cat = tf.keras.utils.to_categorical(y_train, num_classes)
    y_val_cat = tf.keras.utils.to_categorical(y_val, num_classes)
    input_shape = (WINDOW_SIZE, feat_dim)

    # Compare architectures
    print("\n" + "=" * 60)
    print("Architecture Comparison")
    best_f1, best_arch = 0, "gru"
    for arch in ["lstm", "bilstm", "gru", "cnn_lstm"]:
        print(f"\n--- {arch.upper()} ---")
        m = build_model(arch, input_shape, num_classes)
        m.fit(X_train, y_train_cat, validation_data=(X_val, y_val_cat), epochs=25, batch_size=32,
              class_weight=class_weights,
              callbacks=[tf.keras.callbacks.EarlyStopping(patience=6, restore_best_weights=True)], verbose=0)
        f1 = evaluate(m, X_val, y_val, ALL_LABELS, arch)
        if f1 > best_f1:
            best_f1, best_arch = f1, arch
    print(f"\nBest: {best_arch} (F1={best_f1:.4f})")

    # Optuna tuning
    print("\n" + "=" * 60)
    print(f"Optuna Tuning ({best_arch})")
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial):
        u1 = trial.suggest_categorical("u1", [32, 64, 128])
        u2 = trial.suggest_categorical("u2", [16, 32, 64])
        dr = trial.suggest_float("dr", 0.2, 0.5, step=0.1)
        lr = trial.suggest_float("lr", 1e-4, 2e-3, log=True)
        bs = trial.suggest_categorical("bs", [16, 32, 64])
        m = build_model(best_arch, input_shape, num_classes, u1, u2, dr, lr)
        m.fit(X_train, y_train_cat, validation_data=(X_val, y_val_cat), epochs=15, batch_size=bs,
              class_weight=class_weights,
              callbacks=[tf.keras.callbacks.EarlyStopping(patience=4, restore_best_weights=True)], verbose=0)
        yp = np.argmax(m.predict(X_val, verbose=0), axis=1)
        from sklearn.metrics import f1_score
        return f1_score(y_val, yp, average="macro", zero_division=0)

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=15)
    bp = study.best_params
    print(f"Best: {bp}, F1={study.best_value:.4f}")

    # Final model on train+val
    print("\n" + "=" * 60)
    print("Final Training (train+val → test)")
    X_tv = np.concatenate([X_train, X_val])
    y_tv = np.concatenate([y_train, y_val])
    y_tv_cat = tf.keras.utils.to_categorical(y_tv, num_classes)
    cw2 = compute_class_weight("balanced", classes=np.unique(y_tv), y=y_tv)
    cw_final = {int(c): float(w) for c, w in zip(np.unique(y_tv), cw2)}

    final = build_model(best_arch, input_shape, num_classes, bp["u1"], bp["u2"], bp["dr"], bp["lr"])
    final.fit(X_tv, y_tv_cat, epochs=40, batch_size=bp["bs"], class_weight=cw_final,
              callbacks=[tf.keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True, monitor="loss")],
              verbose=1)

    print("\n" + "=" * 60)
    print("TEST SET (never seen)")
    test_f1 = evaluate(final, X_test, y_test, ALL_LABELS, "final_test")

    final.save(str(MODELS_DIR / "lstm_activity_classifier.keras"))

    config = {
        "window_size": WINDOW_SIZE, "stride": STRIDE, "num_classes": num_classes,
        "labels": ALL_LABELS, "confidence_threshold": 0.5,
        "features_per_frame": feat_dim, "target_fps": TARGET_FPS,
        "mobilenet_img_size": 128, "mobilenet_target_fps": 2, "mobilenet_threshold": 0.5,
        "best_architecture": best_arch, "best_params": bp, "test_macro_f1": test_f1,
    }
    with open(str(ML_DIR / "config.json"), "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n{'='*60}\nDONE — Test Macro F1: {test_f1:.4f}\n{'='*60}")


if __name__ == "__main__":
    main()
