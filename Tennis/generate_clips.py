#!/usr/bin/env python3
"""
Generate stroke clips from labeled tennis frames.

Usage:
    python generate_clips.py <session_date> [--output-dir ~/Desktop]

Example:
    python generate_clips.py 20260103
"""

import subprocess
import json
import csv
import sys
from pathlib import Path

# Default clip settings (frames relative to contact)
CLIP_SETTINGS = {
    "forehand": {"pre": 8, "post": 2, "fps": 5},   # 8 frames before, 2 after
    "backhand": {"pre": 5, "post": 5, "fps": 5},   # 5 frames before, 5 after
    "serve":    {"pre": 5, "post": 19, "fps": 5},  # 5 frames before, 19 after (longer motion)
}

def find_contact_frames(labels_path):
    """Find frames closest to contact (distance_ms=0 or minimum)."""
    contacts = {"forehand": [], "backhand": [], "serve": []}

    with open(labels_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = row.get("label", "")
            if label in contacts:
                frame_num = int(row["frame_num"])
                distance = int(row.get("distance_ms", 0))
                swing_id = row.get("swing_id", "")
                if distance == 0:  # Contact frame
                    contacts[label].append((frame_num, swing_id))

    return contacts

def generate_clip(frames_dir, start_frame, num_frames, output_path, fps=5):
    """Generate video clip from frames using ffmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-start_number", str(start_frame),
        "-i", str(frames_dir / "frame_%04d.jpg"),
        "-frames:v", str(num_frames),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(output_path)
    ]
    subprocess.run(cmd, capture_output=True)
    return output_path.exists()

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    session_date = sys.argv[1]
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.home() / "Desktop"

    tennis_dir = Path(__file__).parent

    # Find all frame directories for this session
    frames_base = tennis_dir / "frames"
    session_dirs = list(frames_base.glob(f"{session_date}*"))

    if not session_dirs:
        print(f"No frame directories found for session {session_date}")
        sys.exit(1)

    clips_generated = []

    for session_dir in session_dirs:
        labels_path = session_dir / "labels.csv"
        if not labels_path.exists():
            print(f"No labels.csv in {session_dir.name}, skipping")
            continue

        view = "side" if "side" in session_dir.name else "back"
        contacts = find_contact_frames(labels_path)

        for stroke_type, contact_list in contacts.items():
            if not contact_list:
                continue

            settings = CLIP_SETTINGS[stroke_type]

            # Generate clip for first contact of each type
            contact_frame, swing_id = contact_list[0]
            start_frame = contact_frame - settings["pre"]
            num_frames = settings["pre"] + settings["post"] + 1

            output_name = f"{stroke_type}_{view}_{session_date}.mp4"
            output_path = output_dir / output_name

            if generate_clip(session_dir, start_frame, num_frames, output_path, settings["fps"]):
                duration = num_frames / settings["fps"]
                clips_generated.append({
                    "clip": output_name,
                    "stroke": stroke_type,
                    "view": view,
                    "frames": f"{start_frame}-{start_frame + num_frames - 1}",
                    "duration": f"{duration:.1f}s",
                    "contact_frame": contact_frame,
                    "swing_id": swing_id
                })
                print(f"✓ {output_name} ({duration:.1f}s)")

    # Summary
    print(f"\nGenerated {len(clips_generated)} clips in {output_dir}")

    # Save manifest
    manifest_path = output_dir / f"clips_{session_date}.json"
    with open(manifest_path, "w") as f:
        json.dump(clips_generated, f, indent=2)
    print(f"Manifest: {manifest_path}")

if __name__ == "__main__":
    main()
