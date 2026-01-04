#!/usr/bin/env python3
"""
Match voice announcements to Zepp sensor swings.

Pairs transcribed shot announcements (from transcribe_audio.py) with
Zepp swing timestamps to create ground truth labels.

Usage:
    python match_announcements.py <announcements_csv> <session_date> [--audio-offset-ms 0]
    python match_announcements.py announcements_watch_20260104.csv 20260104

The audio_offset_ms parameter adjusts for time sync between Watch and Zepp:
- Positive: Watch audio started AFTER Zepp (add to announcement times)
- Negative: Watch audio started BEFORE Zepp (subtract from announcement times)

Output:
    matched_labels_{date}.csv - swing_id, zepp_timestamp, announced_stroke, zepp_stroke
"""

import argparse
import csv
import sqlite3
from datetime import datetime
from pathlib import Path


def load_announcements(csv_path: Path) -> list:
    """Load announcements from transcription CSV."""
    announcements = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            announcements.append({
                "start_ms": int(row["start_ms"]),
                "end_ms": int(row["end_ms"]),
                "text": row["text"],
                "stroke": row["stroke"],
            })
    return announcements


def load_zepp_swings(db_path: Path, session_date: str) -> list:
    """
    Load Zepp swings for a given date.

    Args:
        db_path: Path to ztennis.db
        session_date: Date string YYYYMMDD

    Returns:
        List of dicts with swing_id, timestamp_ms, stroke_type
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Convert date to timestamp range
    date_obj = datetime.strptime(session_date, "%Y%m%d")
    start_ts = int(date_obj.timestamp() * 1000)
    end_ts = start_ts + 86400000  # +24 hours

    # Query swings - adjust table/column names based on actual schema
    cursor.execute("""
        SELECT swing_id, timestamp, swing_type
        FROM Swing
        WHERE timestamp >= ? AND timestamp < ?
        ORDER BY timestamp
    """, (start_ts, end_ts))

    swings = []
    for row in cursor.fetchall():
        swing_id, timestamp, swing_type = row
        # Map Zepp swing types: 1=forehand, 2=backhand, 3=serve
        stroke_map = {1: "forehand", 2: "backhand", 3: "serve"}
        swings.append({
            "swing_id": swing_id,
            "timestamp_ms": timestamp,
            "stroke": stroke_map.get(swing_type, f"unknown_{swing_type}"),
        })

    conn.close()
    return swings


def estimate_audio_start(swings: list, announcements: list) -> int:
    """
    Estimate the audio recording start time relative to Zepp epoch.

    Assumes first announcement corresponds to first swing.
    Announcement should be ~1-3 seconds before the swing.

    Returns estimated audio start time in epoch ms.
    """
    if not swings or not announcements:
        return 0

    # First announcement should be ~1-2 sec before first swing
    first_announcement_ms = announcements[0]["start_ms"]
    first_swing_ms = swings[0]["timestamp_ms"]

    # Typical announcement-to-swing delay: 1-3 seconds
    # Audio start = swing time - announcement time (in audio) - expected delay
    expected_delay_ms = 2000  # 2 seconds default

    audio_start_epoch = first_swing_ms - first_announcement_ms - expected_delay_ms
    return audio_start_epoch


def match_announcements_to_swings(
    announcements: list,
    swings: list,
    audio_start_epoch_ms: int,
    max_distance_ms: int = 5000
) -> list:
    """
    Match each announcement to the nearest subsequent Zepp swing.

    Args:
        announcements: List of announcement dicts with start_ms, stroke
        swings: List of swing dicts with timestamp_ms, stroke
        audio_start_epoch_ms: When audio recording started (epoch ms)
        max_distance_ms: Maximum time between announcement and swing

    Returns:
        List of matched pairs with both announcement and Zepp data
    """
    matches = []
    used_swings = set()

    for ann in announcements:
        # Convert announcement time to epoch
        ann_epoch_ms = audio_start_epoch_ms + ann["start_ms"]

        # Find nearest swing AFTER the announcement
        best_match = None
        best_distance = float('inf')

        for swing in swings:
            if swing["swing_id"] in used_swings:
                continue

            # Swing should be after announcement (or very close before)
            distance = swing["timestamp_ms"] - ann_epoch_ms

            # Accept swings within -500ms to +max_distance_ms
            if -500 < distance < max_distance_ms and distance < best_distance:
                best_distance = distance
                best_match = swing

        if best_match:
            used_swings.add(best_match["swing_id"])
            matches.append({
                "swing_id": best_match["swing_id"],
                "zepp_timestamp_ms": best_match["timestamp_ms"],
                "zepp_stroke": best_match["stroke"],
                "announced_stroke": ann["stroke"],
                "announcement_text": ann["text"],
                "time_delta_ms": best_distance,
                "match_correct": best_match["stroke"] == ann["stroke"],
            })

    return matches


def match_session(
    announcements_csv: Path,
    session_date: str,
    db_path: Path = None,
    audio_offset_ms: int = 0,
    output_dir: Path = None
) -> Path:
    """
    Match announcements to Zepp swings for a session.

    Args:
        announcements_csv: Path to announcements CSV from transcribe_audio.py
        session_date: Date string YYYYMMDD
        db_path: Path to ztennis.db (default: Tennis/data/ztennis.db)
        audio_offset_ms: Manual offset adjustment
        output_dir: Where to save output CSV

    Returns:
        Path to matched_labels CSV
    """
    announcements_csv = Path(announcements_csv)

    if db_path is None:
        db_path = Path(__file__).parent / "data/ztennis.db"
    db_path = Path(db_path)

    if output_dir is None:
        output_dir = Path(__file__).parent / "data"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    print(f"Loading announcements from {announcements_csv.name}...")
    announcements = load_announcements(announcements_csv)
    print(f"  Found {len(announcements)} announcements")

    print(f"Loading Zepp swings for {session_date}...")
    swings = load_zepp_swings(db_path, session_date)
    print(f"  Found {len(swings)} swings")

    if not swings:
        print("Error: No Zepp swings found for this date")
        return None

    if not announcements:
        print("Error: No announcements found")
        return None

    # Estimate audio start time
    audio_start_epoch = estimate_audio_start(swings, announcements)
    audio_start_epoch += audio_offset_ms  # Apply manual offset

    print(f"Estimated audio start: {datetime.fromtimestamp(audio_start_epoch/1000)}")

    # Match announcements to swings
    matches = match_announcements_to_swings(
        announcements, swings, audio_start_epoch
    )

    print(f"\nMatched {len(matches)} announcements to swings")

    # Calculate accuracy
    correct = sum(1 for m in matches if m["match_correct"])
    if matches:
        accuracy = correct / len(matches) * 100
        print(f"Zepp vs Announced agreement: {correct}/{len(matches)} ({accuracy:.1f}%)")

    # Count by stroke
    stroke_counts = {"forehand": 0, "backhand": 0, "serve": 0}
    for m in matches:
        if m["announced_stroke"] in stroke_counts:
            stroke_counts[m["announced_stroke"]] += 1

    print(f"\nBy announced stroke:")
    print(f"  Forehand: {stroke_counts['forehand']}")
    print(f"  Backhand: {stroke_counts['backhand']}")
    print(f"  Serve: {stroke_counts['serve']}")

    # Save matches
    csv_path = output_dir / f"matched_labels_{session_date}.csv"

    with open(csv_path, "w", newline="") as f:
        fieldnames = [
            "swing_id", "zepp_timestamp_ms", "zepp_stroke",
            "announced_stroke", "announcement_text", "time_delta_ms", "match_correct"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(matches)

    print(f"\nSaved: {csv_path}")

    # Show mismatches for debugging
    mismatches = [m for m in matches if not m["match_correct"]]
    if mismatches:
        print(f"\nMismatches ({len(mismatches)}):")
        for m in mismatches[:5]:
            print(f"  Swing {m['swing_id']}: Zepp={m['zepp_stroke']}, "
                  f"Announced={m['announced_stroke']} ({m['announcement_text']})")

    return csv_path


def main():
    parser = argparse.ArgumentParser(description="Match announcements to Zepp swings")
    parser.add_argument("announcements_csv", help="Path to announcements CSV")
    parser.add_argument("session_date", help="Session date (YYYYMMDD)")
    parser.add_argument("--db", help="Path to ztennis.db")
    parser.add_argument("--audio-offset-ms", type=int, default=0,
                        help="Audio time offset (ms)")
    parser.add_argument("--output-dir", "-o", help="Output directory")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else None
    output_dir = Path(args.output_dir) if args.output_dir else None

    match_session(
        args.announcements_csv,
        args.session_date,
        db_path,
        args.audio_offset_ms,
        output_dir
    )


if __name__ == "__main__":
    main()
