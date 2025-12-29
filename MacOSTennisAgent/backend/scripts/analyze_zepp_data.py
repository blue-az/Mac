#!/usr/bin/env python3
"""
Analyze Zepp U Tennis Data from TennisAgent database.

Provides tools for:
- Performance metrics by stroke type
- Longitudinal trends over time
- Session summaries and comparisons
- Shot heatmaps and distributions
"""

import sqlite3
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import statistics


class ZeppAnalyzer:
    """Analyze Zepp U tennis data."""

    def __init__(self, db_path: Path):
        """
        Initialize analyzer.

        Args:
            db_path: Path to tennis_watch.db
        """
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        """Connect to database."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def get_date_range(self) -> Tuple[str, str]:
        """Get earliest and latest Zepp session dates."""
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT MIN(date) as earliest, MAX(date) as latest
            FROM sessions
            WHERE device = 'ZeppU'
        """)

        row = cursor.fetchone()
        conn.close()

        return (row['earliest'], row['latest'])

    def get_total_stats(self) -> Dict[str, Any]:
        """Get overall statistics across all Zepp sessions."""
        conn = self.connect()
        cursor = conn.cursor()

        # Session stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_sessions,
                SUM(shot_count) as total_shots,
                SUM(duration_minutes) as total_minutes,
                MIN(date) as earliest_date,
                MAX(date) as latest_date
            FROM sessions
            WHERE device = 'ZeppU'
        """)

        session_row = cursor.fetchone()

        # Shot type distribution
        cursor.execute("""
            SELECT shot_type, COUNT(*) as count
            FROM shots
            WHERE session_id LIKE 'zepp_%'
            GROUP BY shot_type
        """)

        shot_types = {row['shot_type']: row['count'] for row in cursor.fetchall()}

        # Velocity stats (only for shots with velocity > 0)
        cursor.execute("""
            SELECT
                COUNT(CASE WHEN speed_mph > 0 THEN 1 END) as shots_with_speed,
                AVG(CASE WHEN speed_mph > 0 THEN speed_mph END) as avg_speed,
                MAX(speed_mph) as max_speed
            FROM shots
            WHERE session_id LIKE 'zepp_%'
        """)

        velocity_row = cursor.fetchone()

        conn.close()

        return {
            'total_sessions': session_row['total_sessions'],
            'total_shots': session_row['total_shots'],
            'total_minutes': session_row['total_minutes'],
            'date_range': f"{session_row['earliest_date']} to {session_row['latest_date']}",
            'shot_types': shot_types,
            'shots_with_velocity': velocity_row['shots_with_speed'],
            'avg_racket_speed_mph': round(velocity_row['avg_speed'], 2) if velocity_row['avg_speed'] else 0,
            'max_racket_speed_mph': round(velocity_row['max_speed'], 2) if velocity_row['max_speed'] else 0
        }

    def analyze_stroke_performance(self, stroke_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze performance by stroke type.

        Args:
            stroke_type: Filter by specific stroke type (forehand, backhand, serve, etc.)
                        If None, analyze all strokes

        Returns:
            Dict with performance metrics
        """
        conn = self.connect()
        cursor = conn.cursor()

        # Build query
        where_clause = "session_id LIKE 'zepp_%'"
        params = []

        if stroke_type:
            where_clause += " AND shot_type = ?"
            params.append(stroke_type)

        query = f"""
            SELECT
                shot_type,
                COUNT(*) as total_shots,
                COUNT(CASE WHEN speed_mph > 0 THEN 1 END) as shots_with_speed,
                AVG(CASE WHEN speed_mph > 0 THEN speed_mph END) as avg_speed,
                MAX(speed_mph) as max_speed,
                AVG(power) as avg_power,
                AVG(consistency) as avg_consistency
            FROM shots
            WHERE {where_clause}
            GROUP BY shot_type
            ORDER BY total_shots DESC
        """

        cursor.execute(query, params)

        results = []
        for row in cursor.fetchall():
            results.append({
                'stroke_type': row['shot_type'],
                'total_shots': row['total_shots'],
                'shots_with_velocity': row['shots_with_speed'],
                'avg_racket_speed_mph': round(row['avg_speed'], 2) if row['avg_speed'] else None,
                'max_racket_speed_mph': round(row['max_speed'], 2) if row['max_speed'] else None,
                'avg_power': round(row['avg_power'], 3) if row['avg_power'] else None,
                'avg_consistency': round(row['avg_consistency'], 3) if row['avg_consistency'] else None
            })

        conn.close()

        return {
            'stroke_analysis': results,
            'filtered_by': stroke_type if stroke_type else 'all_strokes'
        }

    def analyze_monthly_trends(self, metric: str = 'shot_count') -> List[Dict[str, Any]]:
        """
        Analyze monthly trends for a metric.

        Args:
            metric: Metric to track ('shot_count', 'avg_speed', 'sessions')

        Returns:
            List of monthly data points
        """
        conn = self.connect()
        cursor = conn.cursor()

        if metric == 'sessions':
            query = """
                SELECT
                    strftime('%Y-%m', date) as month,
                    COUNT(*) as value,
                    SUM(shot_count) as total_shots
                FROM sessions
                WHERE device = 'ZeppU'
                GROUP BY month
                ORDER BY month ASC
            """
        elif metric == 'shot_count':
            query = """
                SELECT
                    strftime('%Y-%m', date) as month,
                    SUM(shot_count) as value,
                    COUNT(*) as session_count
                FROM sessions
                WHERE device = 'ZeppU'
                GROUP BY month
                ORDER BY month ASC
            """
        elif metric == 'avg_speed':
            query = """
                SELECT
                    strftime('%Y-%m', s.date) as month,
                    AVG(CASE WHEN sh.speed_mph > 0 THEN sh.speed_mph END) as value,
                    COUNT(CASE WHEN sh.speed_mph > 0 THEN 1 END) as shots_with_speed
                FROM sessions s
                JOIN shots sh ON s.session_id = sh.session_id
                WHERE s.device = 'ZeppU'
                GROUP BY month
                ORDER BY month ASC
            """
        else:
            raise ValueError(f"Unknown metric: {metric}")

        cursor.execute(query)

        results = []
        for row in cursor.fetchall():
            data_point = {
                'month': row['month'],
                'value': round(row['value'], 2) if row['value'] else 0
            }

            # Add context fields
            if metric == 'sessions':
                data_point['total_shots'] = row['total_shots']
            elif metric == 'shot_count':
                data_point['session_count'] = row['session_count']
            elif metric == 'avg_speed':
                data_point['shots_with_speed'] = row['shots_with_speed']

            results.append(data_point)

        conn.close()

        return results

    def get_session_details(self, session_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific session.

        Args:
            session_id: Session identifier (e.g., 'zepp_20251103')

        Returns:
            Dict with session details
        """
        conn = self.connect()
        cursor = conn.cursor()

        # Session metadata
        cursor.execute("""
            SELECT *
            FROM sessions
            WHERE session_id = ?
        """, (session_id,))

        session = cursor.fetchone()
        if not session:
            conn.close()
            raise ValueError(f"Session not found: {session_id}")

        session_data = dict(session)
        session_data['data_json'] = json.loads(session_data['data_json'])

        # Shot breakdown
        cursor.execute("""
            SELECT
                shot_type,
                COUNT(*) as count,
                AVG(CASE WHEN speed_mph > 0 THEN speed_mph END) as avg_speed,
                MAX(speed_mph) as max_speed
            FROM shots
            WHERE session_id = ?
            GROUP BY shot_type
        """, (session_id,))

        shot_breakdown = [
            {
                'stroke_type': row['shot_type'],
                'count': row['count'],
                'avg_speed_mph': round(row['avg_speed'], 2) if row['avg_speed'] else None,
                'max_speed_mph': round(row['max_speed'], 2) if row['max_speed'] else None
            }
            for row in cursor.fetchall()
        ]

        # Session report (if available)
        cursor.execute("""
            SELECT values_json
            FROM calculated_metrics
            WHERE session_id = ? AND metric_type = 'zepp_session_report'
            LIMIT 1
        """, (session_id,))

        report_row = cursor.fetchone()
        session_report = json.loads(report_row['values_json']) if report_row else None

        conn.close()

        return {
            'session': session_data,
            'shot_breakdown': shot_breakdown,
            'session_report': session_report
        }

    def get_top_sessions(self, metric: str = 'shot_count', limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top sessions by a metric.

        Args:
            metric: Sort by ('shot_count', 'duration_minutes', 'avg_speed')
            limit: Number of sessions to return

        Returns:
            List of top sessions
        """
        conn = self.connect()
        cursor = conn.cursor()

        if metric in ['shot_count', 'duration_minutes']:
            order_by = metric
            query = f"""
                SELECT
                    session_id, date, shot_count, duration_minutes,
                    data_json
                FROM sessions
                WHERE device = 'ZeppU'
                ORDER BY {order_by} DESC
                LIMIT ?
            """
            cursor.execute(query, (limit,))

        elif metric == 'avg_speed':
            query = """
                SELECT
                    s.session_id, s.date, s.shot_count, s.duration_minutes,
                    AVG(CASE WHEN sh.speed_mph > 0 THEN sh.speed_mph END) as avg_speed
                FROM sessions s
                JOIN shots sh ON s.session_id = sh.session_id
                WHERE s.device = 'ZeppU'
                GROUP BY s.session_id
                ORDER BY avg_speed DESC
                LIMIT ?
            """
            cursor.execute(query, (limit,))

        else:
            raise ValueError(f"Unknown metric: {metric}")

        results = []
        for row in cursor.fetchall():
            session_info = {
                'session_id': row['session_id'],
                'date': row['date'],
                'shot_count': row['shot_count'],
                'duration_minutes': row['duration_minutes']
            }

            if metric == 'avg_speed':
                session_info['avg_speed_mph'] = round(row['avg_speed'], 2) if row['avg_speed'] else None

            results.append(session_info)

        conn.close()

        return results

    def compare_time_periods(
        self,
        period1_start: str,
        period1_end: str,
        period2_start: str,
        period2_end: str
    ) -> Dict[str, Any]:
        """
        Compare performance between two time periods.

        Args:
            period1_start: ISO date (YYYY-MM-DD)
            period1_end: ISO date (YYYY-MM-DD)
            period2_start: ISO date (YYYY-MM-DD)
            period2_end: ISO date (YYYY-MM-DD)

        Returns:
            Dict comparing the two periods
        """
        conn = self.connect()
        cursor = conn.cursor()

        def get_period_stats(start_date: str, end_date: str) -> Dict:
            cursor.execute("""
                SELECT
                    COUNT(*) as sessions,
                    SUM(shot_count) as total_shots,
                    SUM(duration_minutes) as total_minutes
                FROM sessions
                WHERE device = 'ZeppU'
                  AND date >= ? AND date <= ?
            """, (start_date, end_date))

            session_stats = cursor.fetchone()

            cursor.execute("""
                SELECT
                    AVG(CASE WHEN sh.speed_mph > 0 THEN sh.speed_mph END) as avg_speed,
                    MAX(sh.speed_mph) as max_speed
                FROM sessions s
                JOIN shots sh ON s.session_id = sh.session_id
                WHERE s.device = 'ZeppU'
                  AND s.date >= ? AND s.date <= ?
            """, (start_date, end_date))

            velocity_stats = cursor.fetchone()

            return {
                'sessions': session_stats['sessions'],
                'total_shots': session_stats['total_shots'],
                'total_minutes': session_stats['total_minutes'],
                'avg_speed_mph': round(velocity_stats['avg_speed'], 2) if velocity_stats['avg_speed'] else None,
                'max_speed_mph': round(velocity_stats['max_speed'], 2) if velocity_stats['max_speed'] else None
            }

        period1 = get_period_stats(period1_start, period1_end)
        period2 = get_period_stats(period2_start, period2_end)

        conn.close()

        # Calculate changes
        changes = {}
        for key in ['sessions', 'total_shots', 'total_minutes', 'avg_speed_mph', 'max_speed_mph']:
            val1 = period1.get(key, 0) or 0
            val2 = period2.get(key, 0) or 0

            if val1 > 0:
                percent_change = ((val2 - val1) / val1) * 100
                changes[f'{key}_change_pct'] = round(percent_change, 1)

        return {
            'period1': {
                'date_range': f"{period1_start} to {period1_end}",
                'stats': period1
            },
            'period2': {
                'date_range': f"{period2_start} to {period2_end}",
                'stats': period2
            },
            'changes': changes
        }


def print_dict(data: Dict, indent: int = 0):
    """Pretty print dictionary."""
    prefix = "  " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            print(f"{prefix}{key}:")
            print_dict(value, indent + 1)
        elif isinstance(value, list):
            print(f"{prefix}{key}: {len(value)} items")
            if indent < 2 and value:  # Print first item as example
                print_dict(value[0], indent + 1)
        else:
            print(f"{prefix}{key}: {value}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze Zepp U tennis data"
    )
    parser.add_argument(
        '--db',
        type=str,
        default='database/tennis_watch.db',
        help="Path to TennisAgent database"
    )

    subparsers = parser.add_subparsers(dest='command', help='Analysis commands')

    # Summary command
    subparsers.add_parser('summary', help='Overall statistics summary')

    # Stroke analysis
    stroke_parser = subparsers.add_parser('strokes', help='Analyze stroke performance')
    stroke_parser.add_argument('--type', type=str, help='Filter by stroke type')

    # Trends
    trends_parser = subparsers.add_parser('trends', help='Monthly trends')
    trends_parser.add_argument(
        '--metric',
        type=str,
        default='shot_count',
        choices=['sessions', 'shot_count', 'avg_speed'],
        help='Metric to analyze'
    )

    # Session details
    session_parser = subparsers.add_parser('session', help='Session details')
    session_parser.add_argument('session_id', type=str, help='Session ID (e.g., zepp_20251103)')

    # Top sessions
    top_parser = subparsers.add_parser('top', help='Top sessions')
    top_parser.add_argument(
        '--metric',
        type=str,
        default='shot_count',
        choices=['shot_count', 'duration_minutes', 'avg_speed'],
        help='Sort by metric'
    )
    top_parser.add_argument('--limit', type=int, default=10, help='Number of sessions')

    args = parser.parse_args()

    # Resolve database path
    db_path = Path(args.db).expanduser().resolve()

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    # Create analyzer
    analyzer = ZeppAnalyzer(db_path)

    # Execute command
    if args.command == 'summary':
        print("\n" + "="*70)
        print("ZEPP U TENNIS DATA SUMMARY")
        print("="*70)
        stats = analyzer.get_total_stats()
        print_dict(stats)

    elif args.command == 'strokes':
        print("\n" + "="*70)
        print("STROKE PERFORMANCE ANALYSIS")
        print("="*70)
        results = analyzer.analyze_stroke_performance(args.type)
        print_dict(results)

    elif args.command == 'trends':
        print("\n" + "="*70)
        print(f"MONTHLY TRENDS - {args.metric.upper()}")
        print("="*70)
        trends = analyzer.analyze_monthly_trends(args.metric)
        for month_data in trends:
            print_dict(month_data)
            print()

    elif args.command == 'session':
        print("\n" + "="*70)
        print(f"SESSION DETAILS - {args.session_id}")
        print("="*70)
        details = analyzer.get_session_details(args.session_id)
        print_dict(details)

    elif args.command == 'top':
        print("\n" + "="*70)
        print(f"TOP SESSIONS - BY {args.metric.upper()}")
        print("="*70)
        sessions = analyzer.get_top_sessions(args.metric, args.limit)
        for i, session in enumerate(sessions, 1):
            print(f"\n#{i}")
            print_dict(session, indent=1)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
