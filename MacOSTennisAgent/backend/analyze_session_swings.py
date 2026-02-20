#!/usr/bin/env python3
"""
Analyze swing detection on the latest session.
Uses proper peak detection with distance and prominence filtering.
"""
import csv
import gzip
import io
import sqlite3
import numpy as np
from pathlib import Path
from scipy.signal import find_peaks

DB_PATH = Path.home() / "Downloads/SensorDownload/Current/AppleWatch/direct_download/tennis_watch.db"

def analyze_latest_session():
    """Analyze swing detection on most recent session."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get latest session
    cursor.execute("""
        SELECT session_id, device, start_time
        FROM sessions
        ORDER BY start_time DESC
        LIMIT 1
    """)
    session = cursor.fetchone()

    if not session:
        print("❌ No sessions found")
        return

    session_id, device, start_time = session
    print(f"📊 Session: {session_id}")
    print(f"   Device: {device}")

    # Get all buffers
    cursor.execute("""
        SELECT compressed_data
        FROM raw_sensor_buffer
        WHERE session_id = ?
        ORDER BY start_timestamp ASC
    """, (session_id,))

    buffers = cursor.fetchall()
    conn.close()

    # Parse all samples
    all_samples = []
    for (compressed_data,) in buffers:
        # Not compressed in this version
        csv_data = compressed_data.decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_data))

        for row in reader:
            all_samples.append({
                't': float(row['timestamp']),
                'rx': float(row['rotX']),
                'ry': float(row['rotY']),
                'rz': float(row['rotZ']),
            })

    print(f"   Total samples: {len(all_samples)}")

    # Calculate rotation magnitude
    timestamps = np.array([s['t'] for s in all_samples])
    rx = np.array([s['rx'] for s in all_samples])
    ry = np.array([s['ry'] for s in all_samples])
    rz = np.array([s['rz'] for s in all_samples])

    rotation_mag = np.sqrt(rx**2 + ry**2 + rz**2)

    # Detect swings with different thresholds
    print("\n🔍 Swing Detection Analysis:")
    print("-" * 60)

    for threshold in [2.0, 3.0, 4.0, 5.0]:
        # Find peaks with scipy
        peaks, properties = find_peaks(
            rotation_mag,
            height=threshold,      # Minimum peak height (rad/s)
            distance=50,           # Minimum 0.5s between peaks (50 samples @ 100Hz)
            prominence=1.0         # Peak must stand out by at least 1.0 rad/s
        )

        peak_magnitudes = rotation_mag[peaks]
        peak_times = timestamps[peaks]

        print(f"\nThreshold: {threshold} rad/s, Distance: 0.5s, Prominence: 1.0")
        print(f"  Swings detected: {len(peaks)}")

        if len(peaks) > 0:
            print(f"  Peak magnitudes: min={peak_magnitudes.min():.1f}, "
                  f"max={peak_magnitudes.max():.1f}, "
                  f"mean={peak_magnitudes.mean():.1f} rad/s")

            # Show all peaks
            print(f"  Peak details:")
            for i, (peak_idx, mag, t) in enumerate(zip(peaks, peak_magnitudes, peak_times), 1):
                rel_time = t - timestamps[0]
                print(f"    {i:2d}. t={rel_time:6.2f}s, magnitude={mag:.2f} rad/s")

    print("\n" + "=" * 60)
    print(f"📈 Max rotation magnitude in session: {rotation_mag.max():.2f} rad/s")
    print(f"⏱️  Session duration: {timestamps[-1] - timestamps[0]:.1f} seconds")

if __name__ == "__main__":
    analyze_latest_session()
