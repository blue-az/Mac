#!/usr/bin/env python3
"""
Import WristMotion.csv data for testing and analysis.
Processes historical CSV sensor data through the swing detector.
"""

import pandas as pd
import sys
from pathlib import Path
from typing import List
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.swing_detector import SwingDetector, SensorSample, estimate_swing_speed


def load_wristmotion_csv(csv_path: Path) -> pd.DataFrame:
    """
    Load WristMotion.csv file.

    Expected columns:
    time, seconds_elapsed, rotationRateX, rotationRateY, rotationRateZ,
    gravityX, gravityY, gravityZ, accelerationX, accelerationY, accelerationZ,
    quaternionW, quaternionX, quaternionY, quaternionZ
    """
    print(f"📂 Loading CSV: {csv_path}")

    df = pd.read_csv(csv_path)

    print(f"✅ Loaded {len(df):,} samples")
    print(f"   Duration: {df['seconds_elapsed'].max():.1f} seconds")
    print(f"   Columns: {list(df.columns)}")

    return df


def df_to_sensor_samples(df: pd.DataFrame) -> List[SensorSample]:
    """Convert DataFrame to list of SensorSample objects."""
    samples = []

    for _, row in df.iterrows():
        # Convert nanosecond timestamp to seconds if needed
        if 'time' in row and row['time'] > 1e12:  # Likely nanoseconds
            timestamp = row['time'] / 1e9
        else:
            timestamp = row.get('seconds_elapsed', 0)

        sample = SensorSample(
            timestamp=timestamp,
            rotation_rate=(
                row['rotationRateX'],
                row['rotationRateY'],
                row['rotationRateZ']
            ),
            gravity=(
                row['gravityX'],
                row['gravityY'],
                row['gravityZ']
            ),
            acceleration=(
                row['accelerationX'],
                row['accelerationY'],
                row['accelerationZ']
            ),
            quaternion=(
                row['quaternionW'],
                row['quaternionX'],
                row['quaternionY'],
                row['quaternionZ']
            )
        )
        samples.append(sample)

    return samples


def process_csv_file(csv_path: Path, threshold: float = 2.0):
    """
    Process WristMotion.csv file and detect swings.

    Args:
        csv_path: Path to CSV file
        threshold: Detection threshold (rad/s)
    """
    print("="*70)
    print("MacOSTennisAgent - WristMotion CSV Import")
    print("="*70)
    print()

    # Load CSV
    df = load_wristmotion_csv(csv_path)

    # Convert to sensor samples
    print(f"\n🔄 Converting to sensor samples...")
    samples = df_to_sensor_samples(df)
    print(f"✅ Converted {len(samples):,} samples")

    # Create detector
    print(f"\n🎾 Initializing swing detector...")
    print(f"   Threshold: {threshold} rad/s")
    print(f"   Buffer size: 300 samples (3 seconds)")
    print(f"   Min distance: 50 samples (0.5 seconds)")

    detector = SwingDetector(
        buffer_size=300,
        threshold=threshold,
        min_distance=50
    )

    # Process samples in batches
    print(f"\n🔄 Processing samples...")
    batch_size = 100
    all_detected_swings = []

    start_time = time.time()

    for i in range(0, len(samples), batch_size):
        batch = samples[i:i+batch_size]
        detected_peaks = detector.process_batch(batch)
        all_detected_swings.extend(detected_peaks)

        # Print progress every 1000 samples
        if (i+batch_size) % 1000 == 0:
            progress = (i+batch_size) / len(samples) * 100
            print(f"   Progress: {progress:.1f}% ({i+batch_size:,}/{len(samples):,} samples)")

    elapsed_time = time.time() - start_time

    # Print results
    print(f"\n✅ Processing complete!")
    print(f"   Processing time: {elapsed_time:.2f} seconds")
    print(f"   Processing rate: {len(samples)/elapsed_time:.0f} samples/second")

    print(f"\n🎾 Swing Detection Results:")
    print(f"   Total swings detected: {len(all_detected_swings)}")

    if all_detected_swings:
        print(f"\n📊 Detected Swings:")
        print(f"   {'#':>3} {'Timestamp':>12} {'Rotation':>10} {'Accel':>10} {'Speed (mph)':>12}")
        print(f"   {'-'*3} {'-'*12} {'-'*10} {'-'*10} {'-'*12}")

        for idx, peak in enumerate(all_detected_swings, 1):
            speed = estimate_swing_speed(peak)
            print(f"   {idx:3d} {peak.timestamp:12.3f} {peak.rotation_magnitude:10.2f} "
                  f"{peak.acceleration_magnitude:10.2f} {speed:12.1f}")

    # Statistics
    stats = detector.get_statistics()
    print(f"\n📈 Detector Statistics:")
    print(f"   Total samples processed: {stats['total_samples_processed']:,}")
    print(f"   Total peaks detected: {stats['total_peaks_detected']}")
    print(f"   Buffer usage: {stats['buffer_size']}/{stats['buffer_capacity']}")
    print(f"   Sample rate: {stats['sample_rate_hz']:.1f} Hz")

    # Swing rate
    duration_seconds = df['seconds_elapsed'].max()
    swings_per_minute = (len(all_detected_swings) / duration_seconds) * 60 if duration_seconds > 0 else 0
    print(f"\n⏱️  Session Statistics:")
    print(f"   Duration: {duration_seconds:.1f} seconds ({duration_seconds/60:.1f} minutes)")
    print(f"   Swings per minute: {swings_per_minute:.1f}")

    print(f"\n✨ Import complete!")

    return all_detected_swings, stats


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Import and process WristMotion.csv data"
    )
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help="Path to WristMotion.csv file"
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=2.0,
        help="Detection threshold in rad/s (default: 2.0)"
    )

    args = parser.parse_args()

    csv_path = Path(args.input)

    if not csv_path.exists():
        print(f"❌ File not found: {csv_path}")
        sys.exit(1)

    # Process CSV
    swings, stats = process_csv_file(csv_path, threshold=args.threshold)

    print("\n="*70)


if __name__ == '__main__':
    main()
