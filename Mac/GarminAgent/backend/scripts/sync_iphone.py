#!/usr/bin/env python3
"""
Sync Garmin activity data from a plugged-in iPhone.

This script:
1. Detects connected iPhone via pymobiledevice3
2. Accesses the Garmin Connect app container
3. Downloads and parses FIT files
4. Extracts heart rate data
5. Stores in SQLite database

Usage:
    python sync_iphone.py              # Import all new activities
    python sync_iphone.py --list       # List FIT files without importing
    python sync_iphone.py --force      # Re-import all (overwrite existing)
    python sync_iphone.py --limit 10   # Only process first 10 files
"""

import sys
import json
import argparse
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# Add parent directory to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from app.services.iphone_mount import iPhoneMounter
from app.services.fit_parser import FitFileParser

# Project paths
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "tennis_garmin.db"
DOWNLOADS_DIR = PROJECT_ROOT / "downloads"


def get_db_connection() -> sqlite3.Connection:
    """Get a database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def is_file_imported(conn: sqlite3.Connection, fit_file: str) -> bool:
    """Check if a FIT file has already been imported."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT activity_id FROM activities WHERE fit_file_path = ?",
        (fit_file,)
    )
    return cursor.fetchone() is not None


def import_activity(conn: sqlite3.Connection, parser: FitFileParser, fit_path: Path) -> Optional[int]:
    """Import a parsed FIT file into the database."""
    metadata = parser.extract_metadata()
    hr_samples = parser.extract_heart_rate()
    hr_zones = parser.get_hr_zones()

    cursor = conn.cursor()

    # Insert activity
    cursor.execute("""
        INSERT INTO activities (
            fit_file_path, activity_type, start_time, end_time,
            duration_seconds, distance_meters, calories,
            avg_hr, max_hr, min_hr, hr_zones_json, data_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(fit_path.name),
        metadata.get("activity_type", "unknown"),
        metadata.get("start_time"),
        metadata.get("end_time"),
        metadata.get("duration_seconds"),
        metadata.get("distance_meters"),
        metadata.get("calories"),
        metadata.get("avg_hr"),
        metadata.get("max_hr"),
        metadata.get("min_hr"),
        json.dumps(hr_zones),
        json.dumps(metadata)
    ))

    activity_id = cursor.lastrowid

    # Insert HR samples
    if hr_samples:
        cursor.executemany("""
            INSERT INTO heart_rate_samples (activity_id, timestamp, heart_rate)
            VALUES (?, ?, ?)
        """, [
            (activity_id, sample["timestamp"], sample["heart_rate"])
            for sample in hr_samples
        ])

    conn.commit()
    return activity_id


def log_sync(conn: sqlite3.Connection, files_found: int, imported: int,
             skipped: int, status: str, device_info: dict, error: str = None):
    """Log a sync operation."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sync_log (files_found, activities_synced, files_skipped,
                             status, device_info, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        files_found,
        imported,
        skipped,
        status,
        json.dumps(device_info) if device_info else None,
        error
    ))
    conn.commit()


def list_fit_files(mounter: iPhoneMounter):
    """List FIT files without importing."""
    mounter.list_fit_files()


def sync_activities(mounter: iPhoneMounter, force: bool = False,
                   limit: Optional[int] = None) -> dict:
    """Sync activities from iPhone to database."""
    result = {
        "files_found": 0,
        "imported": 0,
        "skipped": 0,
        "errors": []
    }

    # Check database exists
    if not DATABASE_PATH.exists():
        print(f"Error: Database not found at {DATABASE_PATH}")
        print("Run: python init_database.py")
        return result

    conn = get_db_connection()

    # Find and download FIT files
    print("\nScanning for FIT files...")
    fit_files_info = mounter.find_fit_files()
    if limit:
        fit_files_info = fit_files_info[:limit]

    result["files_found"] = len(fit_files_info)
    print(f"Found {len(fit_files_info)} FIT files")

    if not fit_files_info:
        print("No FIT files found in Garmin Connect container")
        return result

    # Process each file
    for i, fit_info in enumerate(fit_files_info, 1):
        file_name = fit_info["name"]
        print(f"\n[{i}/{len(fit_files_info)}] Processing: {file_name}")

        # Check if already imported
        if not force and is_file_imported(conn, file_name):
            print(f"  Skipped (already imported)")
            result["skipped"] += 1
            continue

        # Download FIT file
        local_path = mounter.download_fit_file(
            fit_info["path"],
            DOWNLOADS_DIR / file_name
        )
        if not local_path:
            print(f"  Error: Failed to download")
            result["errors"].append(f"Failed to download: {file_name}")
            continue

        # Parse FIT file
        parser = FitFileParser(local_path)
        if not parser.parse():
            print(f"  Error: Failed to parse")
            result["errors"].append(f"Failed to parse: {file_name}")
            continue

        # Import to database
        try:
            activity_id = import_activity(conn, parser, local_path)
            metadata = parser.extract_metadata()
            hr_count = len(parser.extract_heart_rate())

            print(f"  Imported: activity_id={activity_id}")
            print(f"  Type: {metadata.get('activity_type', 'unknown')}")
            print(f"  Start: {metadata.get('start_time')}")
            print(f"  Duration: {(metadata.get('duration_seconds') or 0) // 60} min")
            print(f"  HR samples: {hr_count}")
            print(f"  Avg HR: {metadata.get('avg_hr')}, Max: {metadata.get('max_hr')}")

            result["imported"] += 1

        except Exception as e:
            print(f"  Error importing: {e}")
            result["errors"].append(f"Import error for {file_name}: {str(e)}")

    # Log sync
    device_info = mounter.get_device_info()
    log_sync(
        conn,
        result["files_found"],
        result["imported"],
        result["skipped"],
        "success" if not result["errors"] else "partial",
        device_info,
        "; ".join(result["errors"]) if result["errors"] else None
    )

    conn.close()
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Sync Garmin activity data from iPhone"
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List FIT files without importing"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-import all files (overwrite existing)"
    )
    parser.add_argument(
        "--limit", type=int,
        help="Limit number of files to process"
    )
    args = parser.parse_args()

    print("GarminTennisAgent - iPhone Sync")
    print("=" * 40)

    # Ensure downloads directory exists
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize mounter
    mounter = iPhoneMounter(str(DOWNLOADS_DIR))

    # Check device connection
    print("\nChecking for connected iPhone...")
    if not mounter.is_device_connected():
        print("Error: No iPhone connected")
        print("\nTroubleshooting:")
        print("  1. Connect iPhone via USB")
        print("  2. Unlock iPhone and trust this computer")
        print("  3. Check pymobiledevice3 is installed: pip install pymobiledevice3")
        sys.exit(1)

    device_info = mounter.get_device_info()
    device_name = device_info.get("DeviceName", "Unknown")
    ios_version = device_info.get("ProductVersion", "Unknown")
    print(f"Connected: {device_name} (iOS {ios_version})")

    if args.list:
        list_fit_files(mounter)
    else:
        result = sync_activities(mounter, force=args.force, limit=args.limit)

        print("\n" + "=" * 40)
        print("Sync Complete")
        print(f"  Files found:    {result['files_found']}")
        print(f"  Imported:       {result['imported']}")
        print(f"  Skipped:        {result['skipped']}")
        if result["errors"]:
            print(f"  Errors:         {len(result['errors'])}")
            for err in result["errors"]:
                print(f"    - {err}")

    print("\nDone!")


if __name__ == "__main__":
    main()
