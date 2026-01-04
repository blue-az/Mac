#!/usr/bin/env python3
"""
Extract contact-point frames for all labeled strokes.

Usage:
    python extract_contacts.py <session_date> [--output-dir ~/Desktop/contact_frames]
    python extract_contacts.py 20260103

Output:
    {view}_{swing_id}_{stroke}.jpg for each contact frame
"""

import argparse
import csv
import shutil
from pathlib import Path


def extract_contacts(session_date, output_dir):
    tennis_dir = Path(__file__).parent
    frames_base = tennis_dir / "frames"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    session_dirs = list(frames_base.glob(f"{session_date}*"))
    if not session_dirs:
        print(f"No frame directories found for {session_date}")
        return

    total = 0
    by_stroke = {"forehand": 0, "backhand": 0, "serve": 0}

    for session_dir in session_dirs:
        labels_path = session_dir / "labels.csv"
        if not labels_path.exists():
            continue

        view = "side" if "side" in session_dir.name else "back"

        with open(labels_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("distance_ms") == "0":
                    src = session_dir / row["frame_path"]
                    stroke = row["label"]
                    swing_id = row["swing_id"]

                    if not src.exists():
                        continue

                    dst = output_dir / f"{view}_{swing_id}_{stroke}.jpg"
                    shutil.copy(src, dst)
                    total += 1
                    if stroke in by_stroke:
                        by_stroke[stroke] += 1

    print(f"Extracted {total} contact frames to {output_dir}")
    print(f"  Forehand: {by_stroke['forehand']}")
    print(f"  Backhand: {by_stroke['backhand']}")
    print(f"  Serve: {by_stroke['serve']}")


def main():
    parser = argparse.ArgumentParser(description="Extract contact-point frames")
    parser.add_argument("session_date", help="Session date (YYYYMMDD)")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    args = parser.parse_args()

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path.home() / "Desktop" / f"contact_frames_{args.session_date}"

    extract_contacts(args.session_date, output_dir)


if __name__ == "__main__":
    main()
