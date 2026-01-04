#!/usr/bin/env python3
"""
Sync Apple Watch IMU data with video frames.

Extracts Watch sensor samples that correspond to each video frame timestamp,
enabling fusion of wrist motion data with visual analysis.

Usage:
    python sync_watch_video.py <session_date> <watch_session_id>
    python sync_watch_video.py 20260103 watch_20260103_192900

Output:
    frames/<session>/watch_imu.csv - IMU data aligned to frame timestamps
"""

import csv
import json
import sqlite3
import sys
from pathlib import Path


def get_watch_samples(db_path, session_id):
    """Extract raw sensor samples for a session."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Check if raw_sensor_buffer has data
    cursor = conn.execute("""
        SELECT * FROM raw_sensor_buffer
        WHERE session_id = ?
        ORDER BY timestamp
    """, (session_id,))

    samples = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return samples


def get_shot_timestamps(db_path, session_id):
    """Get detected shot timestamps."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute("""
        SELECT shot_id, timestamp, rotation_magnitude, acceleration_magnitude,
               shot_type, speed_mph
        FROM shots
        WHERE session_id = ?
        ORDER BY timestamp
    """, (session_id,))

    shots = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return shots


def load_frame_timestamps(manifest_path):
    """Load frame timestamps from manifest."""
    frames = []
    with open(manifest_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            frames.append({
                'frame_num': int(row['frame_num']),
                'filename': row['filename'],
                'timestamp_ms': int(row['timestamp_ms'])
            })
    return frames


def sync_watch_to_frames(watch_samples, frame_timestamps, video_start_epoch_ms, tolerance_ms=50):
    """
    Align Watch IMU samples to video frame timestamps.

    Args:
        watch_samples: List of Watch sensor samples with epoch timestamps
        frame_timestamps: List of frame info with relative timestamps
        video_start_epoch_ms: Epoch time when video started
        tolerance_ms: Max time difference to consider a match

    Returns:
        List of frames with matched IMU data
    """
    synced = []

    for frame in frame_timestamps:
        frame_epoch_ms = video_start_epoch_ms + frame['timestamp_ms']

        # Find closest Watch sample
        best_match = None
        best_diff = float('inf')

        for sample in watch_samples:
            sample_epoch_ms = sample.get('timestamp', 0) * 1000  # Convert to ms if needed
            diff = abs(sample_epoch_ms - frame_epoch_ms)

            if diff < best_diff and diff <= tolerance_ms:
                best_diff = diff
                best_match = sample

        synced.append({
            'frame_num': frame['frame_num'],
            'filename': frame['filename'],
            'frame_epoch_ms': frame_epoch_ms,
            'watch_match': best_match is not None,
            'time_diff_ms': best_diff if best_match else None,
            'rotation_x': best_match.get('rotation_x') if best_match else None,
            'rotation_y': best_match.get('rotation_y') if best_match else None,
            'rotation_z': best_match.get('rotation_z') if best_match else None,
            'accel_x': best_match.get('accel_x') if best_match else None,
            'accel_y': best_match.get('accel_y') if best_match else None,
            'accel_z': best_match.get('accel_z') if best_match else None,
        })

    return synced


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nAvailable Watch sessions:")

        tennis_dir = Path(__file__).parent
        db_path = tennis_dir / "data" / "tennis_watch.db"

        if db_path.exists():
            conn = sqlite3.connect(db_path)
            cursor = conn.execute("""
                SELECT session_id, date, shot_count
                FROM sessions
                WHERE device = 'AppleWatch'
                ORDER BY date DESC
                LIMIT 10
            """)
            for row in cursor.fetchall():
                print(f"  {row[0]} ({row[1]}, {row[2]} shots)")
            conn.close()

        sys.exit(1)

    session_date = sys.argv[1]
    watch_session_id = sys.argv[2]

    tennis_dir = Path(__file__).parent
    db_path = tennis_dir / "data" / "tennis_watch.db"

    if not db_path.exists():
        print(f"Watch database not found: {db_path}")
        sys.exit(1)

    # Get Watch data
    print(f"Loading Watch session: {watch_session_id}")
    samples = get_watch_samples(db_path, watch_session_id)
    shots = get_shot_timestamps(db_path, watch_session_id)
    print(f"  Found {len(samples)} IMU samples, {len(shots)} detected shots")

    if not samples:
        print("  Warning: No raw sensor data found for this session")

    # Find frame directories for this date
    frames_dir = tennis_dir / "frames"
    session_dirs = list(frames_dir.glob(f"{session_date}*"))

    if not session_dirs:
        print(f"No frame directories found for {session_date}")
        sys.exit(1)

    for session_dir in session_dirs:
        manifest_path = session_dir / "manifest.csv"
        metadata_path = session_dir / "metadata.json"

        if not manifest_path.exists() or not metadata_path.exists():
            continue

        # Load metadata for video start time
        with open(metadata_path) as f:
            metadata = json.load(f)

        video_start_epoch_ms = metadata.get('sync', {}).get('video_start_epoch_ms')
        if not video_start_epoch_ms:
            print(f"  Skipping {session_dir.name}: no video_start_epoch_ms in metadata")
            continue

        # Load frame timestamps
        frame_timestamps = load_frame_timestamps(manifest_path)
        print(f"\nSyncing {session_dir.name}: {len(frame_timestamps)} frames")

        # Sync Watch to frames
        synced = sync_watch_to_frames(samples, frame_timestamps, video_start_epoch_ms)

        # Count matches
        matches = sum(1 for s in synced if s['watch_match'])
        print(f"  Matched {matches}/{len(synced)} frames to Watch IMU")

        # Save output
        output_path = session_dir / "watch_imu.csv"
        with open(output_path, 'w', newline='') as f:
            fieldnames = ['frame_num', 'filename', 'frame_epoch_ms', 'watch_match',
                         'time_diff_ms', 'rotation_x', 'rotation_y', 'rotation_z',
                         'accel_x', 'accel_y', 'accel_z']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(synced)

        print(f"  Saved: {output_path}")

        # Also save shots if any
        if shots:
            shots_output = session_dir / "watch_shots.csv"
            with open(shots_output, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=shots[0].keys())
                writer.writeheader()
                writer.writerows(shots)
            print(f"  Saved: {shots_output}")


if __name__ == "__main__":
    main()
