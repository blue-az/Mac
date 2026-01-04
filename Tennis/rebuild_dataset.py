#!/usr/bin/env python3
"""
Rebuild train/val/test dataset from frames and labels.

Run this on Desktop after copying frames from USB.

Usage:
    python rebuild_dataset.py <session_date>
    python rebuild_dataset.py 20260103

Creates:
    datasets/<session_date>/
    ├── train/
    │   ├── forehand/
    │   ├── backhand/
    │   └── serve/
    ├── val/
    └── test/
"""

import csv
import random
import shutil
import sys
from pathlib import Path

SPLITS = {"train": 0.7, "val": 0.15, "test": 0.15}
STROKE_TYPES = ["forehand", "backhand", "serve"]


def rebuild_dataset(session_date):
    tennis_dir = Path(__file__).parent
    frames_base = tennis_dir / "frames"
    datasets_dir = tennis_dir / "datasets" / session_date

    # Find all frame directories for this session
    session_dirs = list(frames_base.glob(f"{session_date}*"))
    if not session_dirs:
        print(f"No frame directories found for {session_date}")
        sys.exit(1)

    # Collect all labeled frames
    labeled_frames = {stroke: [] for stroke in STROKE_TYPES}

    for session_dir in session_dirs:
        labels_path = session_dir / "labels.csv"
        if not labels_path.exists():
            continue

        with open(labels_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                label = row.get("label", "")
                if label in STROKE_TYPES:
                    frame_path = session_dir / row["frame_path"]
                    if frame_path.exists():
                        labeled_frames[label].append(frame_path)

    # Create dataset directories
    for split in SPLITS:
        for stroke in STROKE_TYPES:
            (datasets_dir / split / stroke).mkdir(parents=True, exist_ok=True)

    # Split and copy frames
    total_copied = 0
    for stroke, frames in labeled_frames.items():
        if not frames:
            continue

        random.shuffle(frames)
        n = len(frames)
        train_end = int(n * SPLITS["train"])
        val_end = train_end + int(n * SPLITS["val"])

        splits = {
            "train": frames[:train_end],
            "val": frames[train_end:val_end],
            "test": frames[val_end:]
        }

        for split_name, split_frames in splits.items():
            dest_dir = datasets_dir / split_name / stroke
            for frame_path in split_frames:
                dest_path = dest_dir / frame_path.name
                if not dest_path.exists():
                    shutil.copy2(frame_path, dest_path)
                    total_copied += 1

        print(f"{stroke}: {len(frames)} frames -> train={len(splits['train'])}, val={len(splits['val'])}, test={len(splits['test'])}")

    print(f"\nDataset rebuilt: {datasets_dir}")
    print(f"Total frames copied: {total_copied}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    rebuild_dataset(sys.argv[1])
