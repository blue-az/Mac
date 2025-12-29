#!/usr/bin/env python3
"""
Initialize the MacOSTennisAgent SQLite database.
Creates tables based on schema.sql.
"""

import sqlite3
from pathlib import Path
import sys


def init_database(db_path: Path = None):
    """
    Initialize database with schema.

    Args:
        db_path: Path to database file. If None, uses default location.
    """
    if db_path is None:
        # Default location
        script_dir = Path(__file__).parent
        db_path = script_dir.parent.parent / "database" / "tennis_watch.db"

    # Ensure database directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Read schema
    schema_path = Path(__file__).parent.parent / "app" / "database" / "schema.sql"

    if not schema_path.exists():
        print(f"❌ Schema file not found: {schema_path}")
        sys.exit(1)

    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    # Create database
    print(f"📦 Initializing database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Execute schema
    cursor.executescript(schema_sql)
    conn.commit()

    # Verify tables created
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        ORDER BY name
    """)
    tables = cursor.fetchall()

    print(f"✅ Database initialized successfully!")
    print(f"\n📊 Tables created:")
    for table in tables:
        print(f"   - {table[0]}")

    # Show table counts
    print(f"\n📈 Current data:")
    for table_name in ['sessions', 'shots', 'calculated_metrics', 'devices']:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"   {table_name}: {count} rows")
        except sqlite3.OperationalError:
            pass

    conn.close()

    print(f"\n✨ Database ready at: {db_path}")
    return db_path


if __name__ == '__main__':
    print("="*70)
    print("MacOSTennisAgent - Database Initialization")
    print("="*70)
    print()

    db_path = init_database()

    print()
    print("="*70)
    print("Next steps:")
    print("1. Start the backend server: uvicorn app.main:app --reload")
    print("2. Connect iPhone app to: ws://YOUR_MAC_IP:8000/ws")
    print("3. Or import test data: python scripts/import_wristmotion.py")
    print("="*70)
