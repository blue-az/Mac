#!/usr/bin/env python3
"""
Import Zepp U Tennis Database into MacOSTennisAgent.

Imports swings from ztennis.db into the TennisAgent database:
- Individual swings → shots table
- Session aggregates → sessions table
- Session reports → calculated_metrics table
- Device registration → devices table
"""

import sqlite3
import sys
import json
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class ZeppImporter:
    """Import Zepp U tennis data into TennisAgent database."""

    # Swing type mapping: Zepp → TennisAgent
    SWING_TYPE_MAP = {
        0: 'unknown',
        1: 'forehand',
        2: 'backhand',
        3: 'serve',
        4: 'volley',
        5: 'smash',
        6: 'slice'
    }

    # Swing side mapping
    SWING_SIDE_MAP = {
        0: 'forehand_side',
        1: 'backhand_side'
    }

    def __init__(self, zepp_db_path: Path, tennis_db_path: Path):
        """
        Initialize importer.

        Args:
            zepp_db_path: Path to ztennis.db (Zepp U database)
            tennis_db_path: Path to tennis_watch.db (TennisAgent database)
        """
        self.zepp_db_path = zepp_db_path
        self.tennis_db_path = tennis_db_path
        self.stats = {
            'swings_read': 0,
            'swings_imported': 0,
            'sessions_created': 0,
            'sessions_with_reports': 0,
            'earliest_date': None,
            'latest_date': None
        }

    def connect_zepp_db(self) -> sqlite3.Connection:
        """Connect to Zepp database."""
        if not self.zepp_db_path.exists():
            raise FileNotFoundError(f"Zepp database not found: {self.zepp_db_path}")

        conn = sqlite3.connect(str(self.zepp_db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def connect_tennis_db(self) -> sqlite3.Connection:
        """Connect to TennisAgent database."""
        if not self.tennis_db_path.exists():
            raise FileNotFoundError(f"Tennis database not found: {self.tennis_db_path}")

        conn = sqlite3.connect(str(self.tennis_db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def register_device(self, conn: sqlite3.Connection):
        """Register Zepp U device in devices table."""
        device_metadata = {
            'manufacturer': 'Zepp',
            'product': 'Zepp Tennis',
            'mount_type': 'racket',
            'sensor_type': 'IMU',
            'capabilities': [
                'swing_detection',
                'impact_velocity',
                'ball_velocity',
                'spin_rate',
                'shot_placement',
                'sweet_spot_detection'
            ]
        }

        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO devices (
                device_id, device_type, model, metadata_json
            ) VALUES (?, ?, ?, ?)
        """, (
            'zepp_u_001',
            'ZeppU',
            'Zepp Tennis Sensor',
            json.dumps(device_metadata)
        ))
        conn.commit()

        print("✅ Registered Zepp U device")

    def import_swings(self, zepp_conn: sqlite3.Connection, tennis_conn: sqlite3.Connection) -> Dict[str, List[Dict]]:
        """
        Import swings from Zepp database.

        Returns:
            Dict mapping session_id to list of swing data
        """
        print("\n📊 Reading swings from Zepp database...")

        zepp_cursor = zepp_conn.cursor()
        zepp_cursor.execute("""
            SELECT
                _id,
                client_created,
                year, month, day,
                swing_type, swing_side,
                impact_vel, ball_vel, spin, ball_spin,
                upswing_time, impact_time, backswing_time,
                impact_position_x, impact_position_y,
                impact_region, score,
                power, racket_speed
            FROM swings
            ORDER BY client_created ASC
        """)

        # Group swings by date (session)
        sessions_data = defaultdict(list)

        for row in zepp_cursor.fetchall():
            self.stats['swings_read'] += 1

            # Parse timestamp (client_created is Unix milliseconds)
            timestamp_ms = row['client_created']
            timestamp_dt = datetime.fromtimestamp(timestamp_ms / 1000.0)

            # Create session_id based on date
            session_date = timestamp_dt.strftime('%Y%m%d')
            session_id = f"zepp_{session_date}"

            # Track date range
            date_str = timestamp_dt.strftime('%Y-%m-%d')
            if self.stats['earliest_date'] is None or date_str < self.stats['earliest_date']:
                self.stats['earliest_date'] = date_str
            if self.stats['latest_date'] is None or date_str > self.stats['latest_date']:
                self.stats['latest_date'] = date_str

            # Map swing type
            swing_type_code = row['swing_type']
            shot_type = self.SWING_TYPE_MAP.get(swing_type_code, 'unknown')

            # Determine spin type based on spin value
            spin_val = row['spin'] or 0
            if spin_val > 5:
                spin_type = 'topspin'
            elif spin_val < -5:
                spin_type = 'slice'
            else:
                spin_type = 'flat'

            # Create swing data
            swing_data = {
                '_id': row['_id'],
                'timestamp_ms': timestamp_ms,
                'timestamp_dt': timestamp_dt,
                'shot_type': shot_type,
                'swing_side': self.SWING_SIDE_MAP.get(row['swing_side'], 'unknown'),
                'spin_type': spin_type,

                # Zepp-specific metrics
                'impact_vel_mph': row['impact_vel'] or 0,  # Racket speed at impact
                'ball_vel_mph': row['ball_vel'] or 0,      # Ball speed
                'spin_rpm': row['spin'] or 0,              # Ball spin
                'ball_spin_rpm': row['ball_spin'] or 0,    # Alternative spin field

                # Timing
                'upswing_time_sec': row['upswing_time'] or 0,
                'impact_time_sec': row['impact_time'] or 0,
                'backswing_time_sec': row['backswing_time'] or 0,

                # Position
                'impact_x': row['impact_position_x'] or 0,
                'impact_y': row['impact_position_y'] or 0,
                'impact_region': row['impact_region'] or 0,

                # Quality
                'score': row['score'] or 60,
                'power': row['power'] or 0
            }

            sessions_data[session_id].append(swing_data)

        print(f"✅ Read {self.stats['swings_read']:,} swings")
        print(f"   Grouped into {len(sessions_data)} sessions by date")
        print(f"   Date range: {self.stats['earliest_date']} to {self.stats['latest_date']}")

        return sessions_data

    def create_sessions(self, sessions_data: Dict[str, List[Dict]], tennis_conn: sqlite3.Connection):
        """Create session records from grouped swings."""
        print("\n📅 Creating session records...")

        tennis_cursor = tennis_conn.cursor()

        for session_id, swings in sorted(sessions_data.items()):
            # Calculate session bounds
            timestamps = [s['timestamp_dt'] for s in swings]
            start_time = min(timestamps)
            end_time = max(timestamps)
            duration_sec = (end_time - start_time).total_seconds()
            duration_min = max(1, int(duration_sec / 60))

            # Session metadata
            session_metadata = {
                'source': 'zepp_u',
                'total_swings': len(swings),
                'shot_types': self._count_shot_types(swings),
                'avg_racket_speed_mph': self._avg_metric(swings, 'impact_vel_mph'),
                'avg_ball_speed_mph': self._avg_metric(swings, 'ball_vel_mph'),
                'avg_spin_rpm': self._avg_metric(swings, 'spin_rpm'),
                'avg_score': self._avg_metric(swings, 'score')
            }

            # Insert session
            tennis_cursor.execute("""
                INSERT OR REPLACE INTO sessions (
                    session_id, device, date,
                    start_time, end_time, duration_minutes,
                    shot_count, data_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                'ZeppU',
                start_time.strftime('%Y-%m-%d'),
                int(start_time.timestamp()),
                int(end_time.timestamp()),
                duration_min,
                len(swings),
                json.dumps(session_metadata)
            ))

            self.stats['sessions_created'] += 1

        tennis_conn.commit()
        print(f"✅ Created {self.stats['sessions_created']} session records")

    def import_shots(self, sessions_data: Dict[str, List[Dict]], tennis_conn: sqlite3.Connection):
        """Import individual shots from swings."""
        print("\n🎾 Importing shots...")

        tennis_cursor = tennis_conn.cursor()

        for session_id, swings in sorted(sessions_data.items()):
            for seq_num, swing in enumerate(swings, 1):
                # Create shot_id
                timestamp_str = swing['timestamp_dt'].strftime('%Y%m%d_%H%M%S')
                shot_id = f"{session_id}_shot_{seq_num:03d}"

                # Shot data JSON (preserve all Zepp metrics)
                shot_data = {
                    'zepp_id': swing['_id'],
                    'timestamp_ms': swing['timestamp_ms'],
                    'impact_velocity_mph': swing['impact_vel_mph'],
                    'ball_velocity_mph': swing['ball_vel_mph'],
                    'spin_rpm': swing['spin_rpm'],
                    'ball_spin_rpm': swing['ball_spin_rpm'],
                    'upswing_time_sec': swing['upswing_time_sec'],
                    'impact_time_sec': swing['impact_time_sec'],
                    'backswing_time_sec': swing['backswing_time_sec'],
                    'impact_position': {
                        'x': swing['impact_x'],
                        'y': swing['impact_y']
                    },
                    'impact_region': swing['impact_region'],
                    'swing_side': swing['swing_side'],
                    'quality_score': swing['score'],
                    'power': swing['power']
                }

                # Insert shot
                # Note: Zepp provides racket speed, not rotation magnitude
                # Use impact_vel as the primary speed metric
                tennis_cursor.execute("""
                    INSERT OR REPLACE INTO shots (
                        shot_id, session_id, timestamp, sequence_number,
                        rotation_magnitude, acceleration_magnitude,
                        shot_type, spin_type, speed_mph,
                        power, consistency, data_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    shot_id,
                    session_id,
                    swing['timestamp_ms'] / 1000.0,  # Convert to seconds
                    seq_num,

                    # Zepp doesn't provide raw rotation/accel - use derived metrics
                    swing['impact_vel_mph'] / 10.0,  # Normalized racket speed (approx rad/s equivalent)
                    0.0,  # Acceleration magnitude not available

                    swing['shot_type'],
                    swing['spin_type'],
                    swing['impact_vel_mph'],
                    swing['power'] / 100.0 if swing['power'] > 0 else 0.5,  # Normalize power to 0-1
                    swing['score'] / 100.0,  # Normalize score to 0-1
                    json.dumps(shot_data)
                ))

                self.stats['swings_imported'] += 1

        tennis_conn.commit()
        print(f"✅ Imported {self.stats['swings_imported']:,} shots")

    def import_session_reports(self, zepp_conn: sqlite3.Connection, tennis_conn: sqlite3.Connection):
        """Import session report JSON data as calculated metrics."""
        print("\n📈 Importing session reports...")

        zepp_cursor = zepp_conn.cursor()
        zepp_cursor.execute("""
            SELECT
                session_id, s_id, user_id,
                report, start_time, end_time,
                year, month, day,
                game_type, session_shots, active_time,
                session_score
            FROM session_report
            ORDER BY start_time ASC
        """)

        tennis_cursor = tennis_conn.cursor()

        for row in zepp_cursor.fetchall():
            # Parse timestamp
            start_dt = datetime.fromtimestamp(row['start_time'] / 1000.0)
            session_date = start_dt.strftime('%Y%m%d')
            session_id = f"zepp_{session_date}"

            # Parse report JSON
            try:
                report_json = json.loads(row['report']) if row['report'] else {}
            except json.JSONDecodeError:
                report_json = {}

            # Store as calculated metric
            calc_id = f"calc_{uuid.uuid4().hex[:16]}"

            tennis_cursor.execute("""
                INSERT OR REPLACE INTO calculated_metrics (
                    calc_id, session_id, metric_type, values_json
                ) VALUES (?, ?, ?, ?)
            """, (
                calc_id,
                session_id,
                'zepp_session_report',
                json.dumps({
                    'zepp_session_id': row['session_id'],
                    'zepp_server_id': row['s_id'],
                    'game_type': row['game_type'],
                    'active_time_sec': row['active_time'],
                    'session_shots': row['session_shots'],
                    'session_score': row['session_score'],
                    'report': report_json
                })
            ))

            self.stats['sessions_with_reports'] += 1

        tennis_conn.commit()
        print(f"✅ Imported {self.stats['sessions_with_reports']} session reports")

    def _count_shot_types(self, swings: List[Dict]) -> Dict[str, int]:
        """Count shots by type."""
        counts = defaultdict(int)
        for swing in swings:
            counts[swing['shot_type']] += 1
        return dict(counts)

    def _avg_metric(self, swings: List[Dict], metric: str) -> float:
        """Calculate average of a metric."""
        values = [s[metric] for s in swings if s[metric] > 0]
        return sum(values) / len(values) if values else 0.0

    def print_summary(self):
        """Print import summary statistics."""
        print("\n" + "="*70)
        print("IMPORT SUMMARY")
        print("="*70)
        print(f"Swings read:           {self.stats['swings_read']:,}")
        print(f"Swings imported:       {self.stats['swings_imported']:,}")
        print(f"Sessions created:      {self.stats['sessions_created']}")
        print(f"Session reports:       {self.stats['sessions_with_reports']}")
        print(f"Date range:            {self.stats['earliest_date']} to {self.stats['latest_date']}")
        print("="*70)

    def run(self):
        """Execute the full import process."""
        print("="*70)
        print("Zepp U Tennis Database Import")
        print("="*70)
        print(f"Source: {self.zepp_db_path}")
        print(f"Target: {self.tennis_db_path}")
        print()

        # Connect to databases
        zepp_conn = self.connect_zepp_db()
        tennis_conn = self.connect_tennis_db()

        try:
            # Step 1: Register device
            self.register_device(tennis_conn)

            # Step 2: Import swings (grouped by session)
            sessions_data = self.import_swings(zepp_conn, tennis_conn)

            # Step 3: Create session records
            self.create_sessions(sessions_data, tennis_conn)

            # Step 4: Import individual shots
            self.import_shots(sessions_data, tennis_conn)

            # Step 5: Import session reports
            self.import_session_reports(zepp_conn, tennis_conn)

            # Update device stats
            tennis_cursor = tennis_conn.cursor()
            tennis_cursor.execute("""
                UPDATE devices
                SET total_sessions = ?,
                    last_seen = strftime('%s', 'now')
                WHERE device_id = 'zepp_u_001'
            """, (self.stats['sessions_created'],))
            tennis_conn.commit()

            # Print summary
            self.print_summary()

            print("\n✨ Import complete!")

        finally:
            zepp_conn.close()
            tennis_conn.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Import Zepp U tennis data into TennisAgent database"
    )
    parser.add_argument(
        '--zepp-db',
        type=str,
        default='~/Downloads/SensorDownload/Current/ztennis.db',
        help="Path to Zepp U database (ztennis.db)"
    )
    parser.add_argument(
        '--tennis-db',
        type=str,
        default='database/tennis_watch.db',
        help="Path to TennisAgent database (tennis_watch.db)"
    )

    args = parser.parse_args()

    # Resolve paths
    zepp_db_path = Path(args.zepp_db).expanduser().resolve()
    tennis_db_path = Path(args.tennis_db).expanduser().resolve()

    # Validate paths
    if not zepp_db_path.exists():
        print(f"❌ Zepp database not found: {zepp_db_path}")
        print("\nExpected location: ~/Downloads/SensorDownload/Current/ztennis.db")
        sys.exit(1)

    if not tennis_db_path.exists():
        print(f"❌ Tennis database not found: {tennis_db_path}")
        print("\nRun from MacOSTennisAgent directory with:")
        print("  python backend/scripts/import_zepp_data.py")
        sys.exit(1)

    # Run import
    importer = ZeppImporter(zepp_db_path, tennis_db_path)
    importer.run()


if __name__ == '__main__':
    main()
