#!/usr/bin/env python3
"""
Import Garmin FIT files from a local folder.

Workflow:
1. Export FIT files from Garmin Connect on iPhone
2. AirDrop to Mac (or save to iCloud Drive)
3. Place files in the imports/ folder
4. Run this script

Usage:
    python sync_local.py              # Import all new FIT files
    python sync_local.py --list       # List FIT files without importing
    python sync_local.py --force      # Re-import all (overwrite existing)
"""

import sys
import json
import argparse
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Optional


def datetime_to_str(dt):
    """Convert datetime to ISO string, or return None."""
    if isinstance(dt, datetime):
        return dt.isoformat()
    return dt


def json_serializer(obj):
    """JSON serializer for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

# Add parent directory to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from app.services.fit_parser import FitFileParser

# Project paths
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "tennis_garmin.db"
IMPORTS_DIR = PROJECT_ROOT / "imports"


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

    # Convert datetime values to ISO strings
    start_time = datetime_to_str(metadata.get("start_time"))
    end_time = datetime_to_str(metadata.get("end_time"))

    # Skip files without start_time
    if not start_time:
        raise ValueError("No start_time in activity")

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
        start_time,
        end_time,
        metadata.get("duration_seconds"),
        metadata.get("distance_meters"),
        metadata.get("calories"),
        metadata.get("avg_hr"),
        metadata.get("max_hr"),
        metadata.get("min_hr"),
        json.dumps(hr_zones, default=json_serializer),
        json.dumps(metadata, default=json_serializer)
    ))

    activity_id = cursor.lastrowid

    # Insert HR samples
    if hr_samples:
        cursor.executemany("""
            INSERT INTO heart_rate_samples (activity_id, timestamp, heart_rate)
            VALUES (?, ?, ?)
        """, [
            (activity_id, datetime_to_str(sample["timestamp"]), sample["heart_rate"])
            for sample in hr_samples
        ])

    conn.commit()
    return activity_id


def log_sync(conn: sqlite3.Connection, files_found: int, imported: int,
             skipped: int, status: str, error: str = None):
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
        json.dumps({"source": "local_import"}),
        error
    ))
    conn.commit()


def find_fit_files() -> List[Path]:
    """Find all FIT files in the imports folder."""
    IMPORTS_DIR.mkdir(parents=True, exist_ok=True)

    fit_files = []
    for ext in ["*.fit", "*.FIT"]:
        fit_files.extend(IMPORTS_DIR.glob(ext))

    # Sort by modification time (newest first)
    fit_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return fit_files


def list_fit_files():
    """List FIT files in imports folder."""
    fit_files = find_fit_files()
    print(f"\nFound {len(fit_files)} FIT files in {IMPORTS_DIR}:\n")

    for i, f in enumerate(fit_files, 1):
        size_kb = f.stat().st_size / 1024
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        print(f"  {i:3}. {f.name} ({size_kb:.1f} KB) - {mtime}")


def sync_activities(force: bool = False, limit: Optional[int] = None) -> dict:
    """Import activities from local imports folder."""
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

    # Find FIT files
    fit_files = find_fit_files()
    if limit:
        fit_files = fit_files[:limit]

    result["files_found"] = len(fit_files)
    print(f"\nFound {len(fit_files)} FIT files in {IMPORTS_DIR}")

    if not fit_files:
        print("\nTo import activities:")
        print("  1. Open Garmin Connect on your iPhone")
        print("  2. Go to an activity → tap ⋮ → Export Original")
        print("  3. AirDrop the .fit file to this Mac")
        print(f"  4. Move it to: {IMPORTS_DIR}/")
        print("  5. Run this script again")
        return result

    # Process each file
    for i, fit_path in enumerate(fit_files, 1):
        file_name = fit_path.name
        print(f"\n[{i}/{len(fit_files)}] Processing: {file_name}")

        # Check if already imported
        if not force and is_file_imported(conn, file_name):
            print(f"  Skipped (already imported)")
            result["skipped"] += 1
            continue

        # Parse FIT file
        parser = FitFileParser(fit_path)
        if not parser.parse():
            print(f"  Error: Failed to parse")
            result["errors"].append(f"Failed to parse: {file_name}")
            continue

        # Import to database
        try:
            activity_id = import_activity(conn, parser, fit_path)
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
    log_sync(
        conn,
        result["files_found"],
        result["imported"],
        result["skipped"],
        "success" if not result["errors"] else "partial",
        "; ".join(result["errors"]) if result["errors"] else None
    )

    conn.close()
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Import Garmin FIT files from local folder"
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

    print("GarminTennisAgent - Local Import")
    print("=" * 40)
    print(f"Import folder: {IMPORTS_DIR}")

    # Ensure imports directory exists
    IMPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.list:
        list_fit_files()
    else:
        result = sync_activities(force=args.force, limit=args.limit)

        print("\n" + "=" * 40)
        print("Import Complete")
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
