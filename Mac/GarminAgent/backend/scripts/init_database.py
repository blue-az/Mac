#!/usr/bin/env python3
"""
Initialize the SQLite database for GarminTennisAgent.

Usage:
    python init_database.py [--force]

Options:
    --force    Drop and recreate existing tables
"""

import sqlite3
import sys
from pathlib import Path

# Project paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_PATH = DATABASE_DIR / "tennis_garmin.db"
SCHEMA_PATH = SCRIPT_DIR.parent / "app" / "database" / "schema.sql"


def init_database(force: bool = False) -> bool:
    """Initialize the database with the schema."""
    print(f"Database path: {DATABASE_PATH}")
    print(f"Schema path: {SCHEMA_PATH}")

    # Ensure database directory exists
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    # Read schema
    if not SCHEMA_PATH.exists():
        print(f"Error: Schema file not found at {SCHEMA_PATH}")
        return False

    schema = SCHEMA_PATH.read_text()

    # Handle force flag
    if force and DATABASE_PATH.exists():
        print("Force flag set - removing existing database...")
        DATABASE_PATH.unlink()

    # Connect and execute schema
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Execute schema (handles IF NOT EXISTS)
        cursor.executescript(schema)
        conn.commit()

        # Verify tables
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = cursor.fetchall()
        print(f"\nTables created: {len(tables)}")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"  - {table[0]}: {count} rows")

        # Check views
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
        )
        views = cursor.fetchall()
        if views:
            print(f"\nViews created: {len(views)}")
            for view in views:
                print(f"  - {view[0]}")

        conn.close()
        print(f"\nDatabase initialized successfully at {DATABASE_PATH}")
        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False


def main():
    force = "--force" in sys.argv

    if force:
        response = input("This will delete all existing data. Continue? [y/N]: ")
        if response.lower() != "y":
            print("Aborted.")
            return

    success = init_database(force=force)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
