"""
Statistics and analytics for TS6 Activity Bot.

Provides functions to calculate various metrics from activity data.

Copyright (C) 2025 Metroseksuaali
Licensed under GNU AGPL v3.0 - see LICENSE file for details.
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

        # Get favorite channels (with names from cache)
        channel_query = """
        SELECT
            cs.channel_id,
            ch.channel_name,
            COUNT(*) as visits
        FROM client_snapshots cs
        JOIN snapshots s ON cs.snapshot_id = s.id
        LEFT JOIN channels ch ON cs.channel_id = ch.channel_id
        WHERE cs.client_uid = ? AND s.timestamp BETWEEN ? AND ?
        GROUP BY cs.channel_id
        ORDER BY visits DESC
        LIMIT 5
        """
        cursor.execute(channel_query, (client_uid, start_time, end_time))
        favorite_channels = [
            {
                'channel_id': r['channel_id'],
                'channel_name': r['channel_name'] or f'Channel {r["channel_id"]}',
                'visits': r['visits']
            }
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
            cs.channel_id,
            ch.channel_name,
            COUNT(*) as total_visits,
            COUNT(DISTINCT cs.client_uid) as unique_users,
            AVG(cs.idle_ms) as avg_idle_ms
        FROM client_snapshots cs
        JOIN snapshots s ON cs.snapshot_id = s.id
        LEFT JOIN channels ch ON cs.channel_id = ch.channel_id
        WHERE s.timestamp BETWEEN ? AND ?
        GROUP BY cs.channel_id
        ORDER BY total_visits DESC
        """

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_time, end_time))

        results = [
            {
                'channel_id': row['channel_id'],
                'channel_name': row['channel_name'] or f'Channel {row["channel_id"]}',
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
        Get currently online users (from last snapshot) with detailed status.

        Returns:
            list: Users from most recent snapshot with all tracked fields
        """
        query = """
        SELECT
            cs.client_uid,
            cs.nickname,
            cs.channel_id,
            ch.channel_name,
            cs.idle_ms,
            cs.is_away,
            cs.away_message,
            cs.is_talking,
            cs.input_muted,
            cs.output_muted,
            cs.is_recording,
            cs.server_groups,
            cs.connected_time,
            s.timestamp
        FROM client_snapshots cs
        JOIN snapshots s ON cs.snapshot_id = s.id
        LEFT JOIN channels ch ON cs.channel_id = ch.channel_id
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
                'channel_name': row['channel_name'] or f'Channel {row["channel_id"]}',
                'idle_ms': row['idle_ms'],
                'idle_minutes': round(row['idle_ms'] / 60000, 2) if row['idle_ms'] else 0,
                'is_away': bool(row['is_away']),
                'away_message': row['away_message'] or '',
                'is_talking': bool(row['is_talking']),
                'input_muted': bool(row['input_muted']),
                'output_muted': bool(row['output_muted']),
                'is_recording': bool(row['is_recording']),
                'server_groups': row['server_groups'].split(',') if row['server_groups'] else [],
                'connected_time': row['connected_time'],
                'connected_hours': round(row['connected_time'] / 3600, 2) if row['connected_time'] else 0,
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

    def get_away_stats(self, days: Optional[int] = 7, limit: int = 10) -> Dict:
        """
        Get AFK/Away status statistics.

        Args:
            days: Number of days to analyze
            limit: Number of top away users to return

        Returns:
            dict: Away statistics including top away users and percentages
        """
        start_time, end_time = self._get_time_range(days)

        conn = self._get_connection()
        cursor = conn.cursor()

        # Overall away percentage
        cursor.execute("""
            SELECT
                COUNT(*) as total_samples,
                SUM(CASE WHEN is_away = 1 THEN 1 ELSE 0 END) as away_samples
            FROM client_snapshots cs
            JOIN snapshots s ON cs.snapshot_id = s.id
            WHERE s.timestamp BETWEEN ? AND ?
        """, (start_time, end_time))
        row = cursor.fetchone()
        total_samples = row['total_samples']
        away_samples = row['away_samples']
        away_percentage = round((away_samples / total_samples * 100) if total_samples > 0 else 0, 2)

        # Top away users (users who are away most often)
        cursor.execute("""
            SELECT
                client_uid,
                nickname,
                COUNT(*) as total_samples,
                SUM(CASE WHEN is_away = 1 THEN 1 ELSE 0 END) as away_count,
                away_message
            FROM client_snapshots cs
            JOIN snapshots s ON cs.snapshot_id = s.id
            WHERE s.timestamp BETWEEN ? AND ? AND away_message IS NOT NULL AND away_message != ''
            GROUP BY client_uid
            HAVING total_samples > 10
            ORDER BY away_count DESC
            LIMIT ?
        """, (start_time, end_time, limit))

        top_away_users = [
            {
                'client_uid': row['client_uid'],
                'nickname': row['nickname'],
                'total_samples': row['total_samples'],
                'away_count': row['away_count'],
                'away_percentage': round((row['away_count'] / row['total_samples'] * 100), 2),
                'last_away_message': row['away_message']
            }
            for row in cursor.fetchall()
        ]

        conn.close()

        return {
            'period_days': days,
            'total_samples': total_samples,
            'away_samples': away_samples,
            'away_percentage': away_percentage,
            'top_away_users': top_away_users
        }

    def get_mute_stats(self, days: Optional[int] = 7) -> Dict:
        """
        Get microphone/speaker mute and recording statistics.

        Args:
            days: Number of days to analyze

        Returns:
            dict: Mute/recording statistics
        """
        start_time, end_time = self._get_time_range(days)

        conn = self._get_connection()
        cursor = conn.cursor()

        # Overall mute statistics
        cursor.execute("""
            SELECT
                COUNT(*) as total_samples,
                SUM(CASE WHEN input_muted = 1 THEN 1 ELSE 0 END) as mic_muted_samples,
                SUM(CASE WHEN output_muted = 1 THEN 1 ELSE 0 END) as speaker_muted_samples,
                SUM(CASE WHEN is_recording = 1 THEN 1 ELSE 0 END) as recording_samples,
                SUM(CASE WHEN is_talking = 1 THEN 1 ELSE 0 END) as talking_samples
            FROM client_snapshots cs
            JOIN snapshots s ON cs.snapshot_id = s.id
            WHERE s.timestamp BETWEEN ? AND ?
        """, (start_time, end_time))
        row = cursor.fetchone()

        total = row['total_samples']
        mic_muted_pct = round((row['mic_muted_samples'] / total * 100) if total > 0 else 0, 2)
        speaker_muted_pct = round((row['speaker_muted_samples'] / total * 100) if total > 0 else 0, 2)
        recording_pct = round((row['recording_samples'] / total * 100) if total > 0 else 0, 2)
        talking_pct = round((row['talking_samples'] / total * 100) if total > 0 else 0, 2)

        # Users who record most often
        cursor.execute("""
            SELECT
                client_uid,
                nickname,
                COUNT(*) as total_samples,
                SUM(CASE WHEN is_recording = 1 THEN 1 ELSE 0 END) as recording_count
            FROM client_snapshots cs
            JOIN snapshots s ON cs.snapshot_id = s.id
            WHERE s.timestamp BETWEEN ? AND ?
            GROUP BY client_uid
            HAVING recording_count > 0
            ORDER BY recording_count DESC
            LIMIT 10
        """, (start_time, end_time))

        top_recorders = [
            {
                'client_uid': row['client_uid'],
                'nickname': row['nickname'],
                'recording_count': row['recording_count'],
                'recording_percentage': round((row['recording_count'] / row['total_samples'] * 100), 2)
            }
            for row in cursor.fetchall()
        ]

        conn.close()

        return {
            'period_days': days,
            'total_samples': total,
            'mic_muted_percentage': mic_muted_pct,
            'speaker_muted_percentage': speaker_muted_pct,
            'recording_percentage': recording_pct,
            'talking_percentage': talking_pct,
            'top_recorders': top_recorders
        }

    def get_server_group_stats(self, days: Optional[int] = 7) -> List[Dict]:
        """
        Get server group membership statistics.

        Args:
            days: Number of days to analyze

        Returns:
            list: Server groups with member counts and activity
        """
        start_time, end_time = self._get_time_range(days)

        conn = self._get_connection()
        cursor = conn.cursor()

        # Get all unique group IDs and their stats
        cursor.execute("""
            SELECT
                server_groups,
                COUNT(DISTINCT client_uid) as unique_members,
                COUNT(*) as total_samples
            FROM client_snapshots cs
            JOIN snapshots s ON cs.snapshot_id = s.id
            WHERE s.timestamp BETWEEN ? AND ?
              AND server_groups IS NOT NULL
              AND server_groups != ''
            GROUP BY server_groups
            ORDER BY unique_members DESC
        """, (start_time, end_time))

        # Parse comma-separated groups
        group_stats = {}
        for row in cursor.fetchall():
            groups_str = row['server_groups']
            if groups_str:
                # Split comma-separated group IDs
                group_ids = groups_str.split(',')
                for gid in group_ids:
                    gid = gid.strip()
                    if gid:
                        if gid not in group_stats:
                            group_stats[gid] = {'unique_members': 0, 'total_samples': 0}
                        group_stats[gid]['unique_members'] += row['unique_members']
                        group_stats[gid]['total_samples'] += row['total_samples']

        conn.close()

        results = [
            {
                'group_id': gid,
                'unique_members': stats['unique_members'],
                'total_samples': stats['total_samples']
            }
            for gid, stats in sorted(group_stats.items(), key=lambda x: x[1]['unique_members'], reverse=True)
        ]

        return results

    def get_channel_switches(self, days: Optional[int] = 7, limit: int = 10) -> List[Dict]:
        """
        Detect and count channel switches for users.

        Args:
            days: Number of days to analyze
            limit: Number of top channel hoppers to return

        Returns:
            list: Users who switch channels most frequently
        """
        start_time, end_time = self._get_time_range(days)

        conn = self._get_connection()
        cursor = conn.cursor()

        # This query detects channel switches by comparing consecutive snapshots
        # We use LAG() window function to get previous channel_id
        query = """
        WITH channel_changes AS (
            SELECT
                client_uid,
                nickname,
                channel_id,
                LAG(channel_id) OVER (
                    PARTITION BY client_uid
                    ORDER BY s.timestamp
                ) as prev_channel_id
            FROM client_snapshots cs
            JOIN snapshots s ON cs.snapshot_id = s.id
            WHERE s.timestamp BETWEEN ? AND ?
        )
        SELECT
            client_uid,
            nickname,
            COUNT(*) as total_samples,
            SUM(CASE WHEN channel_id != prev_channel_id AND prev_channel_id IS NOT NULL THEN 1 ELSE 0 END) as channel_switches
        FROM channel_changes
        GROUP BY client_uid
        HAVING channel_switches > 0
        ORDER BY channel_switches DESC
        LIMIT ?
        """

        cursor.execute(query, (start_time, end_time, limit))

        results = [
            {
                'client_uid': row['client_uid'],
                'nickname': row['nickname'],
                'total_samples': row['total_samples'],
                'channel_switches': row['channel_switches'],
                'switches_per_hour': round(
                    (row['channel_switches'] / (row['total_samples'] * self.poll_interval / 3600)),
                    2
                )
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return results

    def get_connection_patterns(self, days: Optional[int] = 7, limit: int = 10) -> Dict:
        """
        Analyze connection patterns (connect/disconnect frequency, session length).

        Args:
            days: Number of days to analyze
            limit: Number of users to include in top lists

        Returns:
            dict: Connection pattern statistics
        """
        start_time, end_time = self._get_time_range(days)

        conn = self._get_connection()
        cursor = conn.cursor()

        # Detect sessions by finding gaps in snapshots
        # A gap > 2 * poll_interval indicates disconnect/reconnect
        query = """
        WITH snapshot_gaps AS (
            SELECT
                client_uid,
                nickname,
                s.timestamp,
                LAG(s.timestamp) OVER (
                    PARTITION BY client_uid
                    ORDER BY s.timestamp
                ) as prev_timestamp
            FROM client_snapshots cs
            JOIN snapshots s ON cs.snapshot_id = s.id
            WHERE s.timestamp BETWEEN ? AND ?
        ),
        sessions AS (
            SELECT
                client_uid,
                nickname,
                SUM(CASE
                    WHEN prev_timestamp IS NULL OR (timestamp - prev_timestamp) > (? * 2)
                    THEN 1
                    ELSE 0
                END) as session_count,
                COUNT(*) as total_samples
            FROM snapshot_gaps
            GROUP BY client_uid
        )
        SELECT
            client_uid,
            nickname,
            session_count,
            total_samples,
            CAST(total_samples AS FLOAT) / session_count as avg_samples_per_session
        FROM sessions
        WHERE session_count > 0
        ORDER BY session_count DESC
        LIMIT ?
        """

        cursor.execute(query, (start_time, end_time, self.poll_interval, limit))

        top_reconnectors = [
            {
                'client_uid': row['client_uid'],
                'nickname': row['nickname'],
                'session_count': row['session_count'],
                'avg_session_length_minutes': round(
                    (row['avg_samples_per_session'] * self.poll_interval / 60),
                    2
                )
            }
            for row in cursor.fetchall()
        ]

        # Overall session statistics
        cursor.execute("""
            SELECT
                COUNT(DISTINCT client_uid) as total_users,
                AVG(total_samples) as avg_samples_per_user
            FROM (
                SELECT client_uid, COUNT(*) as total_samples
                FROM client_snapshots cs
                JOIN snapshots s ON cs.snapshot_id = s.id
                WHERE s.timestamp BETWEEN ? AND ?
                GROUP BY client_uid
            )
        """, (start_time, end_time))

        row = cursor.fetchone()
        avg_online_time_hours = round(
            (row['avg_samples_per_user'] * self.poll_interval / 3600) if row['avg_samples_per_user'] else 0,
            2
        )

        conn.close()

        return {
            'period_days': days,
            'total_users': row['total_users'],
            'avg_online_time_hours': avg_online_time_hours,
            'top_reconnectors': top_reconnectors
        }

    def get_user_lifetime_value(self, days: Optional[int] = None, limit: int = 50) -> List[Dict]:
        """
        Calculate User Lifetime Value (LTV) score for users.

        LTV is calculated based on:
        - Total online time (weighted heavily)
        - Activity consistency (days active)
        - Engagement (talking time, channel visits)
        - Social interaction (different channels visited)

        Args:
            days: Number of days to analyze (None = all time)
            limit: Number of users to return

        Returns:
            list: Users sorted by LTV score with categorization
        """
        start_time, end_time = self._get_time_range(days)

        conn = self._get_connection()
        cursor = conn.cursor()

        query = """
        WITH session_gaps AS (
            -- First calculate LAG without aggregation
            SELECT
                cs.client_uid,
                s.timestamp,
                LAG(s.timestamp) OVER (PARTITION BY cs.client_uid ORDER BY s.timestamp) as prev_timestamp
            FROM client_snapshots cs
            JOIN snapshots s ON cs.snapshot_id = s.id
            WHERE s.timestamp BETWEEN ? AND ?
        ),
        user_metrics AS (
            -- Then aggregate the results
            SELECT
                cs.client_uid,
                MAX(cs.nickname) as nickname,
                COUNT(*) as total_samples,
                COUNT(DISTINCT DATE(s.timestamp, 'unixepoch')) as days_active,
                COUNT(DISTINCT cs.channel_id) as channels_visited,
                SUM(CASE WHEN cs.is_talking = 1 THEN 1 ELSE 0 END) as talking_samples,
                AVG(cs.idle_ms) as avg_idle_ms,
                MIN(s.timestamp) as first_seen,
                MAX(s.timestamp) as last_seen,
                -- Calculate session count from session_gaps
                (
                    SELECT COUNT(*)
                    FROM session_gaps sg
                    WHERE sg.client_uid = cs.client_uid
                      AND (sg.prev_timestamp IS NULL
                           OR sg.timestamp - sg.prev_timestamp > (? * 2))
                ) as session_count
            FROM client_snapshots cs
            JOIN snapshots s ON cs.snapshot_id = s.id
            WHERE s.timestamp BETWEEN ? AND ?
            GROUP BY cs.client_uid
        )
        SELECT
            client_uid,
            nickname,
            total_samples,
            days_active,
            channels_visited,
            talking_samples,
            avg_idle_ms,
            first_seen,
            last_seen,
            session_count,
            -- LTV Score calculation (0-100 scale)
            CAST(
                -- Online time score (40% weight) - normalized to 40 points max
                (CAST(total_samples AS FLOAT) / (SELECT MAX(total_samples) FROM user_metrics) * 40) +
                -- Consistency score (30% weight) - days_active normalized to 30 points
                (CAST(days_active AS FLOAT) / (SELECT MAX(days_active) FROM user_metrics) * 30) +
                -- Engagement score (20% weight) - talking activity normalized to 20 points
                (CAST(talking_samples AS FLOAT) / NULLIF((SELECT MAX(talking_samples) FROM user_metrics), 0) * 20) +
                -- Social score (10% weight) - channel diversity normalized to 10 points
                (CAST(channels_visited AS FLOAT) / (SELECT MAX(channels_visited) FROM user_metrics) * 10)
            AS INTEGER) as ltv_score
        FROM user_metrics
        WHERE total_samples > 5  -- Filter out users with very few samples
        ORDER BY ltv_score DESC
        LIMIT ?
        """

        cursor.execute(query, (start_time, end_time, self.poll_interval, start_time, end_time, limit))

        results = []
        for row in cursor.fetchall():
            # Calculate derived metrics
            online_seconds = row['total_samples'] * self.poll_interval
            online_hours = online_seconds / 3600
            talking_percentage = round((row['talking_samples'] / row['total_samples'] * 100) if row['total_samples'] > 0 else 0, 2)

            # Categorize user based on LTV score
            ltv_score = row['ltv_score']
            if ltv_score >= 80:
                category = 'power_user'
                category_label = 'Power User'
            elif ltv_score >= 50:
                category = 'regular'
                category_label = 'Regular User'
            else:
                category = 'casual'
                category_label = 'Casual User'

            # Calculate activity frequency
            time_span_days = (row['last_seen'] - row['first_seen']) / 86400
            activity_frequency = round((row['days_active'] / time_span_days * 100) if time_span_days > 0 else 0, 2)

            results.append({
                'client_uid': row['client_uid'],
                'nickname': row['nickname'],
                'ltv_score': ltv_score,
                'category': category,
                'category_label': category_label,
                'total_samples': row['total_samples'],
                'online_hours': round(online_hours, 2),
                'days_active': row['days_active'],
                'activity_frequency_percent': activity_frequency,
                'channels_visited': row['channels_visited'],
                'talking_samples': row['talking_samples'],
                'talking_percentage': talking_percentage,
                'avg_idle_minutes': round(row['avg_idle_ms'] / 60000, 2) if row['avg_idle_ms'] else 0,
                'session_count': row['session_count'],
                'avg_session_length_hours': round((online_hours / row['session_count']) if row['session_count'] > 0 else 0, 2),
                'first_seen': row['first_seen'],
                'last_seen': row['last_seen']
            })

        conn.close()
        return results

    def get_ltv_summary(self, days: Optional[int] = None) -> Dict:
        """
        Get summary statistics for User Lifetime Value distribution.

        Args:
            days: Number of days to analyze (None = all time)

        Returns:
            dict: LTV distribution and summary statistics
        """
        ltv_data = self.get_user_lifetime_value(days=days, limit=10000)  # Get all users

        if not ltv_data:
            return {
                'total_users': 0,
                'avg_ltv_score': 0,
                'power_users': 0,
                'regular_users': 0,
                'casual_users': 0,
                'distribution': {}
            }

        # Count users by category
        power_users = sum(1 for u in ltv_data if u['category'] == 'power_user')
        regular_users = sum(1 for u in ltv_data if u['category'] == 'regular')
        casual_users = sum(1 for u in ltv_data if u['category'] == 'casual')

        # Calculate average LTV score
        avg_ltv = sum(u['ltv_score'] for u in ltv_data) / len(ltv_data)

        return {
            'period_days': days,
            'total_users': len(ltv_data),
            'avg_ltv_score': round(avg_ltv, 2),
            'power_users': power_users,
            'power_users_percent': round((power_users / len(ltv_data) * 100), 2),
            'regular_users': regular_users,
            'regular_users_percent': round((regular_users / len(ltv_data) * 100), 2),
            'casual_users': casual_users,
            'casual_users_percent': round((casual_users / len(ltv_data) * 100), 2)
        }
