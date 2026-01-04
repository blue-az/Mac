#!/usr/bin/env python3
"""
Analyze tennis poses and compute stroke metrics.

Usage:
    source venv/bin/activate
    python analyze_poses.py <session_dir>
    python analyze_poses.py frames/20260103_side --visualize

Output:
    pose_metrics.csv - computed angles and positions per frame
    pose_overlay_*.jpg - visualization of keypoints on contact frames
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def angle_between_points(a, b, c):
    """
    Calculate angle at point b formed by points a, b, c.
    Returns angle in degrees (0-180).
    """
    if any(p is None for p in [a, b, c]):
        return None

    ba = np.array(a) - np.array(b)
    bc = np.array(c) - np.array(b)

    cos_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    cos_angle = np.clip(cos_angle, -1, 1)
    return np.degrees(np.arccos(cos_angle))


def load_poses(poses_csv):
    """Load poses from CSV file."""
    poses = {}
    with open(poses_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            frame_num = int(row["frame_num"])
            poses[frame_num] = row
    return poses


def get_point(row, joint_name, min_conf=0.1):
    """Extract (x, y) for a joint if confidence is sufficient."""
    x_key = f"{joint_name}_x"
    y_key = f"{joint_name}_y"
    conf_key = f"{joint_name}_conf"

    if not row.get(x_key) or not row.get(conf_key):
        return None

    try:
        conf = float(row[conf_key])
        if conf < min_conf:
            return None
        return (float(row[x_key]), float(row[y_key]))
    except (ValueError, TypeError):
        return None


def compute_metrics(row):
    """Compute tennis-specific metrics for a single frame."""
    metrics = {}

    # Get key points
    left_shoulder = get_point(row, "left_shoulder")
    right_shoulder = get_point(row, "right_shoulder")
    left_elbow = get_point(row, "left_elbow")
    right_elbow = get_point(row, "right_elbow")
    left_wrist = get_point(row, "left_wrist")
    right_wrist = get_point(row, "right_wrist")
    left_hip = get_point(row, "left_hip")
    right_hip = get_point(row, "right_hip")
    left_knee = get_point(row, "left_knee")
    right_knee = get_point(row, "right_knee")

    # Elbow angles (higher = more extended)
    metrics["left_elbow_angle"] = angle_between_points(left_shoulder, left_elbow, left_wrist)
    metrics["right_elbow_angle"] = angle_between_points(right_shoulder, right_elbow, right_wrist)

    # Knee angles (higher = more straight)
    metrics["left_knee_angle"] = angle_between_points(left_hip, left_knee, get_point(row, "left_ankle"))
    metrics["right_knee_angle"] = angle_between_points(right_hip, right_knee, get_point(row, "right_ankle"))

    # Shoulder rotation (angle between shoulder line and camera)
    if left_shoulder and right_shoulder:
        dx = right_shoulder[0] - left_shoulder[0]
        dy = right_shoulder[1] - left_shoulder[1]
        # Angle from horizontal (0 = facing camera, 90 = side-on)
        metrics["shoulder_rotation"] = abs(np.degrees(np.arctan2(dy, dx)))

    # Hip rotation
    if left_hip and right_hip:
        dx = right_hip[0] - left_hip[0]
        dy = right_hip[1] - left_hip[1]
        metrics["hip_rotation"] = abs(np.degrees(np.arctan2(dy, dx)))

    # Trunk separation (shoulder vs hip rotation difference)
    if metrics.get("shoulder_rotation") and metrics.get("hip_rotation"):
        metrics["trunk_separation"] = abs(metrics["shoulder_rotation"] - metrics["hip_rotation"])

    # Wrist height (relative to frame, 0=bottom, 1=top)
    if left_wrist:
        metrics["left_wrist_height"] = 1 - left_wrist[1]  # Invert since y=0 is top
    if right_wrist:
        metrics["right_wrist_height"] = 1 - right_wrist[1]

    return metrics


def analyze_session(session_dir, visualize=False):
    """Analyze poses for a session and compute metrics."""
    session_dir = Path(session_dir)
    poses_csv = session_dir / "poses.csv"

    if not poses_csv.exists():
        print(f"No poses.csv found in {session_dir}")
        print("Run extract_poses.py first")
        return

    poses = load_poses(poses_csv)
    print(f"Loaded {len(poses)} frames from {poses_csv}")

    # Define fixed fieldnames for consistent CSV output
    metric_names = [
        "left_elbow_angle", "right_elbow_angle",
        "left_knee_angle", "right_knee_angle",
        "shoulder_rotation", "hip_rotation", "trunk_separation",
        "left_wrist_height", "right_wrist_height",
    ]

    # Compute metrics for each frame
    metrics_rows = []
    for frame_num in sorted(poses.keys()):
        row = poses[frame_num]
        metrics = compute_metrics(row)

        metrics_row = {
            "frame_num": frame_num,
            "frame_path": row["frame_path"],
        }
        for key in metric_names:
            value = metrics.get(key)
            metrics_row[key] = f"{value:.1f}" if value is not None else ""

        metrics_rows.append(metrics_row)

    # Write metrics CSV
    if metrics_rows:
        metrics_csv = session_dir / "pose_metrics.csv"
        fieldnames = ["frame_num", "frame_path"] + metric_names
        with open(metrics_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(metrics_rows)
        print(f"Wrote {metrics_csv}")

    # Load labels to find contact frames
    labels_csv = session_dir / "labels.csv"
    contact_frames = []
    if labels_csv.exists():
        with open(labels_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("distance_ms") == "0":
                    contact_frames.append({
                        "frame_num": int(row["frame_num"]),
                        "frame_path": row["frame_path"],
                        "label": row["label"],
                        "swing_id": row["swing_id"],
                    })

    if visualize and contact_frames:
        print(f"\nVisualizing {len(contact_frames)} contact frames...")
        overlay_dir = session_dir / "pose_overlays"
        overlay_dir.mkdir(exist_ok=True)

        for cf in contact_frames[:10]:  # Limit to first 10
            frame_num = cf["frame_num"]
            if frame_num not in poses:
                continue

            frame_path = session_dir / cf["frame_path"]
            if not frame_path.exists():
                continue

            output_path = overlay_dir / f"overlay_{cf['swing_id']}_{cf['label']}.jpg"
            draw_pose_overlay(frame_path, poses[frame_num], output_path, cf["label"])

        print(f"Saved overlays to {overlay_dir}")

    # Print summary of contact frame metrics
    if contact_frames:
        print(f"\n=== Contact Frame Metrics ({len(contact_frames)} shots) ===")

        for label in ["forehand", "backhand", "serve"]:
            label_frames = [cf for cf in contact_frames if cf["label"] == label]
            if not label_frames:
                continue

            elbow_angles = []
            knee_angles = []

            for cf in label_frames:
                frame_num = cf["frame_num"]
                if frame_num not in poses:
                    continue

                metrics = compute_metrics(poses[frame_num])

                # Use right arm for forehand (righty), left for backhand
                if label == "forehand":
                    ea = metrics.get("right_elbow_angle")
                else:
                    ea = metrics.get("left_elbow_angle")

                if ea:
                    elbow_angles.append(ea)

                # Average knee bend
                lk = metrics.get("left_knee_angle")
                rk = metrics.get("right_knee_angle")
                if lk and rk:
                    knee_angles.append((lk + rk) / 2)

            print(f"\n{label.upper()} ({len(label_frames)} shots):")
            if elbow_angles:
                print(f"  Elbow angle: {np.mean(elbow_angles):.0f}° (range: {min(elbow_angles):.0f}°-{max(elbow_angles):.0f}°)")
            if knee_angles:
                print(f"  Knee bend:   {np.mean(knee_angles):.0f}° (range: {min(knee_angles):.0f}°-{max(knee_angles):.0f}°)")


def draw_pose_overlay(image_path, pose_row, output_path, label=""):
    """Draw pose keypoints and skeleton on an image."""
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)

    width, height = img.size

    # Define skeleton connections
    skeleton = [
        ("left_shoulder", "right_shoulder"),
        ("left_shoulder", "left_elbow"),
        ("left_elbow", "left_wrist"),
        ("right_shoulder", "right_elbow"),
        ("right_elbow", "right_wrist"),
        ("left_shoulder", "left_hip"),
        ("right_shoulder", "right_hip"),
        ("left_hip", "right_hip"),
        ("left_hip", "left_knee"),
        ("left_knee", "left_ankle"),
        ("right_hip", "right_knee"),
        ("right_knee", "right_ankle"),
        ("neck", "head"),
    ]

    # Get all points
    points = {}
    for joint in ["head", "neck", "left_shoulder", "right_shoulder",
                  "left_elbow", "right_elbow", "left_wrist", "right_wrist",
                  "left_hip", "right_hip", "left_knee", "right_knee",
                  "left_ankle", "right_ankle"]:
        pt = get_point(pose_row, joint, min_conf=0.1)
        if pt:
            # Convert normalized coords to pixels
            points[joint] = (int(pt[0] * width), int((1 - pt[1]) * height))

    # Draw skeleton lines
    for joint1, joint2 in skeleton:
        if joint1 in points and joint2 in points:
            draw.line([points[joint1], points[joint2]], fill="lime", width=3)

    # Draw keypoints
    radius = 6
    for joint, (x, y) in points.items():
        color = "red" if "wrist" in joint else "yellow"
        draw.ellipse([x-radius, y-radius, x+radius, y+radius], fill=color, outline="white")

    # Compute and display elbow angle
    metrics = compute_metrics(pose_row)

    # Display metrics
    y_offset = 20
    if label:
        draw.text((10, y_offset), f"Stroke: {label.upper()}", fill="white")
        y_offset += 25

    if label == "forehand" and metrics.get("right_elbow_angle"):
        draw.text((10, y_offset), f"R.Elbow: {metrics['right_elbow_angle']:.0f}°", fill="cyan")
        y_offset += 25
    elif metrics.get("left_elbow_angle"):
        draw.text((10, y_offset), f"L.Elbow: {metrics['left_elbow_angle']:.0f}°", fill="cyan")
        y_offset += 25

    if metrics.get("trunk_separation"):
        draw.text((10, y_offset), f"Trunk sep: {metrics['trunk_separation']:.0f}°", fill="cyan")

    img.save(output_path, quality=90)


def main():
    parser = argparse.ArgumentParser(description="Analyze tennis poses")
    parser.add_argument("session_dir", help="Session directory with poses.csv")
    parser.add_argument("--visualize", "-v", action="store_true", help="Generate pose overlay images")
    args = parser.parse_args()

    analyze_session(args.session_dir, visualize=args.visualize)


if __name__ == "__main__":
    main()
