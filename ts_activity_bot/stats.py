"""
Statistics and analytics for TS6 Activity Bot.

Provides functions to calculate various metrics from activity data.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class StatsCalculator:
    """Calculate statistics from activity database."""

    def __init__(self, db_path: str, poll_interval: int):
        """
        Initialize stats calculator.

        Args:
            db_path: Path to SQLite database
            poll_interval: Polling interval in seconds (for time calculations)
        """
        self.db_path = db_path
        self.poll_interval = poll_interval

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_time_range(self, days: Optional[int] = None) -> Tuple[int, int]:
        """
        Get timestamp range for query.

        Args:
            days: Number of days to look back (None = all time)

        Returns:
            tuple: (start_timestamp, end_timestamp)
        """
        end_time = int(datetime.now().timestamp())
        if days is None:
            start_time = 0
        else:
            start_time = int((datetime.now() - timedelta(days=days)).timestamp())
        return start_time, end_time

    def get_top_users(self, days: Optional[int] = 7, limit: int = 10) -> List[Dict]:
        """
        Get top users by online time.

        Args:
            days: Number of days to analyze (None = all time)
            limit: Maximum number of users to return

        Returns:
            list: Top users with stats
        """
        start_time, end_time = self._get_time_range(days)

        query = """
        SELECT
            client_uid,
            nickname,
            COUNT(*) as sample_count,
            MIN(s.timestamp) as first_seen,
            MAX(s.timestamp) as last_seen
        FROM client_snapshots cs
        JOIN snapshots s ON cs.snapshot_id = s.id
        WHERE s.timestamp BETWEEN ? AND ?
        GROUP BY client_uid
        ORDER BY sample_count DESC
        LIMIT ?
        """

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_time, end_time, limit))

        results = []
        for row in cursor.fetchall():
            # Calculate online time: sample_count * poll_interval
            online_seconds = row['sample_count'] * self.poll_interval
            online_minutes = online_seconds / 60
            online_hours = online_minutes / 60

            results.append({
                'client_uid': row['client_uid'],
                'nickname': row['nickname'],
                'sample_count': row['sample_count'],
                'online_seconds': online_seconds,
                'online_minutes': round(online_minutes, 2),
                'online_hours': round(online_hours, 2),
                'first_seen': row['first_seen'],
                'last_seen': row['last_seen']
            })

        conn.close()
        return results

    def get_user_stats(self, client_uid: str, days: Optional[int] = 30) -> Optional[Dict]:
        """
        Get detailed statistics for a specific user.

        Args:
            client_uid: Client unique identifier
            days: Number of days to analyze (None = all time)

        Returns:
            dict: User statistics or None if not found
        """
        start_time, end_time = self._get_time_range(days)

        # Get basic stats
        query = """
        SELECT
            client_uid,
            nickname,
            COUNT(*) as sample_count,
            MIN(s.timestamp) as first_seen,
            MAX(s.timestamp) as last_seen,
            AVG(idle_ms) as avg_idle_ms
        FROM client_snapshots cs
        JOIN snapshots s ON cs.snapshot_id = s.id
        WHERE client_uid = ? AND s.timestamp BETWEEN ? AND ?
        GROUP BY client_uid
        """

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (client_uid, start_time, end_time))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        # Calculate online time
        online_seconds = row['sample_count'] * self.poll_interval
        online_hours = online_seconds / 3600

        # Get favorite channels
        channel_query = """
        SELECT
            channel_id,
            COUNT(*) as visits
        FROM client_snapshots cs
        JOIN snapshots s ON cs.snapshot_id = s.id
        WHERE client_uid = ? AND s.timestamp BETWEEN ? AND ?
        GROUP BY channel_id
        ORDER BY visits DESC
        LIMIT 5
        """
        cursor.execute(channel_query, (client_uid, start_time, end_time))
        favorite_channels = [
            {'channel_id': r['channel_id'], 'visits': r['visits']}
            for r in cursor.fetchall()
        ]

        # Get activity by day of week
        dow_query = """
        SELECT
            CAST(strftime('%w', datetime(s.timestamp, 'unixepoch')) AS INTEGER) as day_of_week,
            COUNT(*) as sample_count
        FROM client_snapshots cs
        JOIN snapshots s ON cs.snapshot_id = s.id
        WHERE client_uid = ? AND s.timestamp BETWEEN ? AND ?
        GROUP BY day_of_week
        ORDER BY day_of_week
        """
        cursor.execute(dow_query, (client_uid, start_time, end_time))
        activity_by_dow = {r['day_of_week']: r['sample_count'] for r in cursor.fetchall()}

        conn.close()

        return {
            'client_uid': row['client_uid'],
            'nickname': row['nickname'],
            'sample_count': row['sample_count'],
            'online_seconds': online_seconds,
            'online_hours': round(online_hours, 2),
            'first_seen': row['first_seen'],
            'last_seen': row['last_seen'],
            'avg_idle_ms': int(row['avg_idle_ms']) if row['avg_idle_ms'] else 0,
            'favorite_channels': favorite_channels,
            'activity_by_day_of_week': activity_by_dow
        }

    def get_hourly_heatmap(self, days: Optional[int] = 7) -> List[Dict]:
        """
        Get average user count by hour of day.

        Args:
            days: Number of days to analyze

        Returns:
            list: Average users per hour (0-23)
        """
        start_time, end_time = self._get_time_range(days)

        query = """
        SELECT
            CAST(strftime('%H', datetime(timestamp, 'unixepoch')) AS INTEGER) as hour,
            AVG(total_clients) as avg_clients,
            COUNT(*) as sample_count
        FROM snapshots
        WHERE timestamp BETWEEN ? AND ?
        GROUP BY hour
        ORDER BY hour
        """

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_time, end_time))

        results = [
            {
                'hour': row['hour'],
                'avg_clients': round(row['avg_clients'], 2),
                'sample_count': row['sample_count']
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return results

    def get_daily_activity(self, days: Optional[int] = 30) -> List[Dict]:
        """
        Get average user count by day of week.

        Args:
            days: Number of days to analyze

        Returns:
            list: Average users per day (0=Sunday, 6=Saturday)
        """
        start_time, end_time = self._get_time_range(days)

        query = """
        SELECT
            CAST(strftime('%w', datetime(timestamp, 'unixepoch')) AS INTEGER) as day_of_week,
            AVG(total_clients) as avg_clients,
            COUNT(*) as sample_count
        FROM snapshots
        WHERE timestamp BETWEEN ? AND ?
        GROUP BY day_of_week
        ORDER BY day_of_week
        """

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_time, end_time))

        day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

        results = [
            {
                'day_of_week': row['day_of_week'],
                'day_name': day_names[row['day_of_week']],
                'avg_clients': round(row['avg_clients'], 2),
                'sample_count': row['sample_count']
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return results

    def get_top_idle_users(self, days: Optional[int] = 7, limit: int = 10) -> List[Dict]:
        """
        Get users with highest average idle time.

        Args:
            days: Number of days to analyze
            limit: Maximum number of users to return

        Returns:
            list: Users sorted by average idle time
        """
        start_time, end_time = self._get_time_range(days)

        query = """
        SELECT
            client_uid,
            nickname,
            AVG(idle_ms) as avg_idle_ms,
            COUNT(*) as sample_count
        FROM client_snapshots cs
        JOIN snapshots s ON cs.snapshot_id = s.id
        WHERE s.timestamp BETWEEN ? AND ? AND idle_ms IS NOT NULL
        GROUP BY client_uid
        HAVING sample_count > 10  -- Require at least 10 samples
        ORDER BY avg_idle_ms DESC
        LIMIT ?
        """

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_time, end_time, limit))

        results = [
            {
                'client_uid': row['client_uid'],
                'nickname': row['nickname'],
                'avg_idle_ms': int(row['avg_idle_ms']),
                'avg_idle_minutes': round(row['avg_idle_ms'] / 60000, 2),
                'sample_count': row['sample_count']
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return results

    def get_peak_times(self, days: Optional[int] = 7, limit: int = 10) -> List[Dict]:
        """
        Get times when server had most users online.

        Args:
            days: Number of days to analyze
            limit: Number of peak times to return

        Returns:
            list: Peak times with user counts
        """
        start_time, end_time = self._get_time_range(days)

        query = """
        SELECT
            timestamp,
            total_clients
        FROM snapshots
        WHERE timestamp BETWEEN ? AND ?
        ORDER BY total_clients DESC, timestamp DESC
        LIMIT ?
        """

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_time, end_time, limit))

        results = [
            {
                'timestamp': row['timestamp'],
                'datetime': datetime.fromtimestamp(row['timestamp']).isoformat(),
                'total_clients': row['total_clients']
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return results

    def get_channel_stats(self, days: Optional[int] = 7) -> List[Dict]:
        """
        Get channel popularity statistics.

        Args:
            days: Number of days to analyze

        Returns:
            list: Channels sorted by total visits
        """
        start_time, end_time = self._get_time_range(days)

        query = """
        SELECT
            channel_id,
            COUNT(*) as total_visits,
            COUNT(DISTINCT client_uid) as unique_users,
            AVG(idle_ms) as avg_idle_ms
        FROM client_snapshots cs
        JOIN snapshots s ON cs.snapshot_id = s.id
        WHERE s.timestamp BETWEEN ? AND ?
        GROUP BY channel_id
        ORDER BY total_visits DESC
        """

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_time, end_time))

        results = [
            {
                'channel_id': row['channel_id'],
                'total_visits': row['total_visits'],
                'unique_users': row['unique_users'],
                'avg_idle_ms': int(row['avg_idle_ms']) if row['avg_idle_ms'] else 0
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return results

    def get_growth_metrics(self, days: int = 7) -> Dict:
        """
        Get growth metrics (new vs returning users).

        Args:
            days: Number of days to analyze

        Returns:
            dict: Growth metrics
        """
        start_time, end_time = self._get_time_range(days)

        conn = self._get_connection()
        cursor = conn.cursor()

        # Total unique users in period
        cursor.execute("""
            SELECT COUNT(DISTINCT client_uid) as total_users
            FROM client_snapshots cs
            JOIN snapshots s ON cs.snapshot_id = s.id
            WHERE s.timestamp BETWEEN ? AND ?
        """, (start_time, end_time))
        total_users = cursor.fetchone()['total_users']

        # New users (first seen in this period)
        cursor.execute("""
            SELECT COUNT(DISTINCT client_uid) as new_users
            FROM client_snapshots cs
            JOIN snapshots s ON cs.snapshot_id = s.id
            WHERE client_uid IN (
                SELECT client_uid
                FROM client_snapshots cs2
                JOIN snapshots s2 ON cs2.snapshot_id = s2.id
                GROUP BY client_uid
                HAVING MIN(s2.timestamp) BETWEEN ? AND ?
            )
        """, (start_time, end_time))
        new_users = cursor.fetchone()['new_users']

        returning_users = total_users - new_users

        conn.close()

        return {
            'period_days': days,
            'total_unique_users': total_users,
            'new_users': new_users,
            'returning_users': returning_users,
            'new_user_percentage': round((new_users / total_users * 100) if total_users > 0 else 0, 2)
        }

    def get_online_now(self) -> List[Dict]:
        """
        Get currently online users (from last snapshot).

        Returns:
            list: Users from most recent snapshot
        """
        query = """
        SELECT
            cs.client_uid,
            cs.nickname,
            cs.channel_id,
            cs.idle_ms,
            s.timestamp
        FROM client_snapshots cs
        JOIN snapshots s ON cs.snapshot_id = s.id
        WHERE s.id = (SELECT MAX(id) FROM snapshots)
        ORDER BY cs.nickname
        """

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query)

        results = [
            {
                'client_uid': row['client_uid'],
                'nickname': row['nickname'],
                'channel_id': row['channel_id'],
                'idle_ms': row['idle_ms'],
                'idle_minutes': round(row['idle_ms'] / 60000, 2) if row['idle_ms'] else 0,
                'snapshot_time': row['timestamp']
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return results

    def get_summary(self, days: Optional[int] = 7) -> Dict:
        """
        Get overall summary statistics.

        Args:
            days: Number of days to analyze

        Returns:
            dict: Summary statistics
        """
        start_time, end_time = self._get_time_range(days)

        conn = self._get_connection()
        cursor = conn.cursor()

        # Total snapshots
        cursor.execute("""
            SELECT COUNT(*) as total_snapshots
            FROM snapshots
            WHERE timestamp BETWEEN ? AND ?
        """, (start_time, end_time))
        total_snapshots = cursor.fetchone()['total_snapshots']

        # Average users online
        cursor.execute("""
            SELECT AVG(total_clients) as avg_clients, MAX(total_clients) as max_clients
            FROM snapshots
            WHERE timestamp BETWEEN ? AND ?
        """, (start_time, end_time))
        row = cursor.fetchone()
        avg_clients = row['avg_clients'] or 0
        max_clients = row['max_clients'] or 0

        # Total unique users
        cursor.execute("""
            SELECT COUNT(DISTINCT client_uid) as unique_users
            FROM client_snapshots cs
            JOIN snapshots s ON cs.snapshot_id = s.id
            WHERE s.timestamp BETWEEN ? AND ?
        """, (start_time, end_time))
        unique_users = cursor.fetchone()['unique_users']

        conn.close()

        return {
            'period_days': days,
            'total_snapshots': total_snapshots,
            'avg_users_online': round(avg_clients, 2),
            'max_users_online': max_clients,
            'unique_users': unique_users
        }
