#!/usr/bin/env python3
"""
Extract body pose keypoints from tennis video frames using Apple Vision.

Usage:
    source venv/bin/activate
    python extract_poses.py <session_dir>
    python extract_poses.py frames/20260103_side

Output:
    poses.csv - keypoint coordinates for each frame
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image

import Vision
from Quartz import (
    CGImageSourceCreateWithURL,
    CGImageSourceCreateImageAtIndex,
)
from Foundation import NSURL


# Apple Vision body pose joint names (actual API names)
# Maps friendly name -> Vision API joint key
VISION_JOINTS = {
    "head": "head_joint",
    "neck": "neck_1_joint",
    "left_shoulder": "left_shoulder_1_joint",
    "right_shoulder": "right_shoulder_1_joint",
    "left_elbow": "left_forearm_joint",
    "right_elbow": "right_forearm_joint",
    "left_wrist": "left_hand_joint",
    "right_wrist": "right_hand_joint",
    "left_hip": "left_upLeg_joint",
    "right_hip": "right_upLeg_joint",
    "left_knee": "left_leg_joint",
    "right_knee": "right_leg_joint",
    "left_ankle": "left_foot_joint",
    "right_ankle": "right_foot_joint",
    "root": "root",  # hip center
}


def load_image_as_cgimage(image_path):
    """Load image file as CGImage."""
    url = NSURL.fileURLWithPath_(str(image_path))
    source = CGImageSourceCreateWithURL(url, None)
    if source is None:
        return None
    return CGImageSourceCreateImageAtIndex(source, 0, None)


def extract_pose_from_image(image_path):
    """Extract body pose keypoints from a single image."""
    cgimage = load_image_as_cgimage(image_path)
    if cgimage is None:
        return None

    # Create pose detection request
    request = Vision.VNDetectHumanBodyPoseRequest.alloc().init()

    # Create handler and perform request
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
        cgimage, None
    )

    success, error = handler.performRequests_error_([request], None)
    if not success or error:
        return None

    results = request.results()
    if not results or len(results) == 0:
        return None

    # Get first detected person
    observation = results[0]

    # Extract keypoints
    keypoints = {}

    # Get all recognized points
    all_points, error = observation.recognizedPointsForGroupKey_error_(
        Vision.VNHumanBodyPoseObservationJointsGroupNameAll, None
    )

    if all_points:
        for friendly_name, vision_key in VISION_JOINTS.items():
            if vision_key in all_points:
                point = all_points[vision_key]
                keypoints[friendly_name] = {
                    "x": float(point.x()),
                    "y": float(point.y()),
                    "confidence": float(point.confidence()),
                }

    return keypoints


def extract_poses_for_session(session_dir):
    """Extract poses for all frames in a session directory."""
    session_dir = Path(session_dir)

    # Find all frames
    frames = sorted(session_dir.glob("frame_*.jpg"))
    if not frames:
        print(f"No frames found in {session_dir}")
        return

    print(f"Processing {len(frames)} frames in {session_dir.name}...")

    # Prepare CSV output
    csv_path = session_dir / "poses.csv"

    # Build header
    joint_names = list(VISION_JOINTS.keys())
    header = ["frame_num", "frame_path"]
    for joint in joint_names:
        header.extend([f"{joint}_x", f"{joint}_y", f"{joint}_conf"])

    rows = []
    detected = 0

    for i, frame_path in enumerate(frames):
        frame_num = int(frame_path.stem.split("_")[1])

        keypoints = extract_pose_from_image(frame_path)

        row = [frame_num, frame_path.name]

        if keypoints:
            detected += 1
            for joint in joint_names:
                if joint in keypoints:
                    kp = keypoints[joint]
                    row.extend([f"{kp['x']:.4f}", f"{kp['y']:.4f}", f"{kp['confidence']:.3f}"])
                else:
                    row.extend(["", "", ""])
        else:
            # No pose detected - empty columns
            row.extend([""] * (len(joint_names) * 3))

        rows.append(row)

        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(frames)} frames...")

    # Write CSV
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    print(f"Wrote {csv_path}")
    print(f"Pose detected in {detected}/{len(frames)} frames ({100*detected/len(frames):.1f}%)")

    return csv_path


def main():
    parser = argparse.ArgumentParser(description="Extract body poses from frames")
    parser.add_argument("session_dir", help="Session directory with frames")
    args = parser.parse_args()

    extract_poses_for_session(args.session_dir)


if __name__ == "__main__":
    main()
