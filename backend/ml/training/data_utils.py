"""
Data utilities: video-level splits, class balancing, augmentation.
Prevents data leakage by splitting at the video level.
"""

import re
import random
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

DCSASS = Path.home() / ".cache/kagglehub/datasets/mateohervas/dcsass-dataset/versions/1/DCSASS Dataset"
ALL_LABELS = ["Normal", "Shoplifting", "Stealing", "Burglary", "Robbery"]
LABEL_TO_IDX = {label: idx for idx, label in enumerate(ALL_LABELS)}
TARGET_CLASSES = ALL_LABELS[1:]


def get_parent_video(clip_name: str) -> str:
    """Extract parent video ID from clip name. e.g. 'Shoplifting001_x264_3' → 'Shoplifting001'."""
    match = re.match(r"([A-Za-z]+\d+)", clip_name)
    return match.group(1) if match else clip_name


def load_all_clips(max_per_class: int = 500) -> pd.DataFrame:
    """Load all clips with labels, parent video IDs, and file paths."""
    records = []

    for cls in TARGET_CLASSES:
        csv_path = DCSASS / "Labels" / f"{cls}.csv"
        if not csv_path.exists():
            continue

        df = pd.read_csv(csv_path, header=None, names=["fn", "cls_name", "abn"])
        cls_dir = DCSASS / cls

        normal_n, abn_n = 0, 0
        for _, row in df.iterrows():
            label_idx = LABEL_TO_IDX[cls] if row["abn"] == 1 else 0
            if label_idx == 0 and normal_n >= max_per_class:
                continue
            if label_idx != 0 and abn_n >= max_per_class:
                continue

            matches = list(cls_dir.rglob(f"{row['fn']}.mp4"))
            if not matches or not matches[0].is_file():
                continue

            parent = get_parent_video(row["fn"])
            records.append({
                "path": str(matches[0]),
                "label": label_idx,
                "label_name": ALL_LABELS[label_idx],
                "parent_video": parent,
                "clip_name": row["fn"],
            })

            if label_idx == 0:
                normal_n += 1
            else:
                abn_n += 1

    return pd.DataFrame(records)


def split_by_video(df: pd.DataFrame, test_size=0.15, val_size=0.15, seed=42):
    """
    Split dataset by parent video — no video's clips appear in multiple splits.
    Returns (train_df, val_df, test_df).
    """
    # First split: train+val vs test
    gss1 = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    trainval_idx, test_idx = next(gss1.split(df, df["label"], groups=df["parent_video"]))
    trainval_df = df.iloc[trainval_idx].reset_index(drop=True)
    test_df = df.iloc[test_idx].reset_index(drop=True)

    # Second split: train vs val
    val_frac = val_size / (1 - test_size)
    gss2 = GroupShuffleSplit(n_splits=1, test_size=val_frac, random_state=seed + 1)
    train_idx, val_idx = next(gss2.split(trainval_df, trainval_df["label"], groups=trainval_df["parent_video"]))
    train_df = trainval_df.iloc[train_idx].reset_index(drop=True)
    val_df = trainval_df.iloc[val_idx].reset_index(drop=True)

    return train_df, val_df, test_df


def augment_windows(X: np.ndarray, y: np.ndarray, num_augmented: int = 2) -> tuple[np.ndarray, np.ndarray]:
    """Augment training windows: time-shift, noise, speed variation."""
    aug_X, aug_y = list(X), list(y)

    for i in range(len(X)):
        for _ in range(num_augmented):
            window = X[i].copy()

            # Gaussian noise on landmarks
            noise = np.random.normal(0, 0.01, window.shape).astype(np.float32)
            aug_window = window + noise

            aug_X.append(aug_window)
            aug_y.append(y[i])

    return np.array(aug_X, dtype=np.float32), np.array(aug_y, dtype=np.int32)


def compute_class_weights(y: np.ndarray) -> dict:
    """Compute balanced class weights."""
    from sklearn.utils.class_weight import compute_class_weight
    classes = np.unique(y)
    weights = compute_class_weight("balanced", classes=classes, y=y)
    return {int(c): float(w) for c, w in zip(classes, weights)}
