"""
PostgreSQL database backend for TS6 Activity Bot.

Provides high-performance PostgreSQL storage for large-scale deployments.

Copyright (C) 2025 Metroseksuaali
Licensed under GNU AGPL v3.0 - see LICENSE file for details.
"""

import logging
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from ts_activity_bot.db_base import DatabaseBackend

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 3

# PostgreSQL schema (using BIGINT for timestamps, BIGSERIAL for auto-increment)
SCHEMA_SQL = """
-- Main snapshots table (one row per poll)
CREATE TABLE IF NOT EXISTS snapshots (
    id BIGSERIAL PRIMARY KEY,
    timestamp BIGINT NOT NULL,
    total_clients INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp);

-- Client snapshots (one row per client per poll)
CREATE TABLE IF NOT EXISTS client_snapshots (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    client_uid TEXT NOT NULL,
    nickname TEXT NOT NULL,
    channel_id INTEGER NOT NULL,
    idle_ms INTEGER,
    is_away INTEGER DEFAULT 0,
    away_message TEXT DEFAULT '',
    is_talking INTEGER DEFAULT 0,
    input_muted INTEGER DEFAULT 0,
    output_muted INTEGER DEFAULT 0,
    is_recording INTEGER DEFAULT 0,
    server_groups TEXT DEFAULT '',
    connected_time INTEGER,
    client_database_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_client_uid_snapshot ON client_snapshots(client_uid, snapshot_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_id ON client_snapshots(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_client_uid ON client_snapshots(client_uid);
CREATE INDEX IF NOT EXISTS idx_channel_id ON client_snapshots(channel_id);

-- Channel metadata cache
CREATE TABLE IF NOT EXISTS channels (
    channel_id INTEGER PRIMARY KEY,
    channel_name TEXT NOT NULL,
    parent_channel_id INTEGER,
    channel_order INTEGER,
    total_clients INTEGER DEFAULT 0,
    last_updated BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_channels_parent ON channels(parent_channel_id);

-- User daily aggregates for faster queries
CREATE TABLE IF NOT EXISTS user_aggregates (
    id BIGSERIAL PRIMARY KEY,
    client_uid TEXT NOT NULL,
    date TEXT NOT NULL,
    nickname TEXT NOT NULL,
    total_samples INTEGER NOT NULL,
    online_seconds INTEGER NOT NULL,
    avg_idle_ms INTEGER,
    most_visited_channel_id INTEGER,
    is_away_count INTEGER DEFAULT 0,
    is_talking_count INTEGER DEFAULT 0,
    input_muted_count INTEGER DEFAULT 0,
    output_muted_count INTEGER DEFAULT 0,
    is_recording_count INTEGER DEFAULT 0,
    UNIQUE(client_uid, date)
);

CREATE INDEX IF NOT EXISTS idx_user_aggregates_uid ON user_aggregates(client_uid);
CREATE INDEX IF NOT EXISTS idx_user_aggregates_date ON user_aggregates(date);
CREATE INDEX IF NOT EXISTS idx_user_aggregates_uid_date ON user_aggregates(client_uid, date);

-- Metadata table for versioning and settings
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class PostgreSQLBackend(DatabaseBackend):
    """PostgreSQL database backend implementation."""

    def __init__(self, connection_string: str):
        """
        Initialize PostgreSQL backend with connection pooling.

        Args:
            connection_string: PostgreSQL connection URI
                Format: postgresql://user:password@host:port/database
        """
        self.connection_string = connection_string

        # Create connection pool (min 2, max 10 connections)
        try:
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=10,
                dsn=connection_string
            )
            logger.info("PostgreSQL connection pool created")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise

        # Initialize schema
        self.initialize_schema()

    @contextmanager
    def get_connection(self):
        """Get a connection from the pool."""
        conn = self.pool.getconn()
        try:
            # Use RealDictCursor for dictionary-like row access
            conn.cursor_factory = psycopg2.extras.RealDictCursor
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    def initialize_schema(self) -> None:
        """Initialize database schema and run migrations."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Create tables
            cursor.execute(SCHEMA_SQL)

            # Check current schema version
            cursor.execute("SELECT value FROM metadata WHERE key = 'schema_version'")
            row = cursor.fetchone()
            current_version = int(row['value']) if row else 0

            if current_version == 0:
                # First time initialization
                cursor.execute(
                    "INSERT INTO metadata (key, value) VALUES ('schema_version', %s)",
                    (str(SCHEMA_VERSION),)
                )
                logger.info(f"Database schema initialized (version {SCHEMA_VERSION})")
            elif current_version < SCHEMA_VERSION:
                # Run migrations
                self._migrate_schema(cursor, current_version, SCHEMA_VERSION)
            else:
                logger.debug(f"Database schema up to date (version {SCHEMA_VERSION})")

    def _migrate_schema(self, cursor, from_version: int, to_version: int) -> None:
        """
        Run schema migrations.

        Args:
            cursor: Database cursor
            from_version: Current schema version
            to_version: Target schema version
        """
        logger.info(f"Migrating schema from v{from_version} to v{to_version}")

        # Migration logic here (similar to SQLite version)
        # For now, just update version
        cursor.execute(
            "UPDATE metadata SET value = %s WHERE key = 'schema_version'",
            (str(to_version),)
        )
        logger.info(f"Schema migration completed: {from_version} -> {to_version}")

    def insert_snapshot(self, clients: List[Dict[str, any]]) -> int:
        """Insert a new snapshot with client data."""
        timestamp = int(time.time())

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Insert snapshot
            cursor.execute(
                "INSERT INTO snapshots (timestamp, total_clients) VALUES (%s, %s) RETURNING id",
                (timestamp, len(clients))
            )
            snapshot_id = cursor.fetchone()['id']

            # Insert client data
            if clients:
                client_data = [
                    (
                        snapshot_id,
                        client.get('client_unique_identifier'),
                        client.get('client_nickname', 'Unknown'),
                        client.get('cid', 0),
                        client.get('client_idle_time'),
                        int(client.get('client_away', 0)),
                        client.get('client_away_message', ''),
                        int(client.get('client_is_talker', 0)),
                        int(client.get('client_input_muted', 0)),
                        int(client.get('client_output_muted', 0)),
                        int(client.get('client_is_recording', 0)),
                        client.get('client_servergroups', ''),
                        client.get('connection_connected_time'),
                        client.get('client_database_id')
                    )
                    for client in clients
                ]

                psycopg2.extras.execute_batch(
                    cursor,
                    """
                    INSERT INTO client_snapshots
                    (snapshot_id, client_uid, nickname, channel_id, idle_ms, is_away,
                     away_message, is_talking, input_muted, output_muted, is_recording,
                     server_groups, connected_time, client_database_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    client_data
                )

            logger.debug(f"Inserted snapshot {snapshot_id} with {len(clients)} clients")
            return snapshot_id

    def cleanup_old_data(self, retention_days: int) -> int:
        """Delete snapshots older than retention period."""
        cutoff_time = int(time.time()) - (retention_days * 86400)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM snapshots WHERE timestamp < %s",
                (cutoff_time,)
            )
            deleted = cursor.rowcount
            logger.info(f"Deleted {deleted} old snapshots (retention: {retention_days} days)")
            return deleted

    def get_database_stats(self) -> Dict[str, any]:
        """Get database statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get snapshot counts
            cursor.execute("SELECT COUNT(*) as count, MIN(timestamp) as first_ts, MAX(timestamp) as last_ts FROM snapshots")
            snapshot_stats = cursor.fetchone()

            # Get client snapshot count
            cursor.execute("SELECT COUNT(*) as count FROM client_snapshots")
            client_count = cursor.fetchone()['count']

            # Get unique clients
            cursor.execute("SELECT COUNT(DISTINCT client_uid) as count FROM client_snapshots")
            unique_clients = cursor.fetchone()['count']

            # Get database size (PostgreSQL-specific)
            cursor.execute("SELECT pg_database_size(current_database()) as size")
            db_size = cursor.fetchone()['size']

            # Get schema version
            schema_version = self._get_metadata('schema_version') or '0'

            return {
                'db_size_mb': round(db_size / (1024 * 1024), 2),
                'snapshot_count': snapshot_stats['count'],
                'client_snapshot_count': client_count,
                'unique_clients': unique_clients,
                'first_snapshot_timestamp': snapshot_stats['first_ts'],
                'last_snapshot_timestamp': snapshot_stats['last_ts'],
                'schema_version': schema_version
            }

    def _get_metadata(self, key: str) -> Optional[str]:
        """Get metadata value."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM metadata WHERE key = %s", (key,))
            row = cursor.fetchone()
            return row['value'] if row else None

    def set_metadata(self, key: str, value: str) -> None:
        """Set metadata value."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO metadata (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """,
                (key, value)
            )

    def upsert_channels(self, channels: List[Dict[str, any]]) -> int:
        """Insert or update channel metadata cache."""
        timestamp = int(time.time())

        with self.get_connection() as conn:
            cursor = conn.cursor()

            channel_data = [
                (
                    channel.get('cid'),
                    channel.get('channel_name', 'Unknown Channel'),
                    channel.get('pid', 0),
                    channel.get('channel_order', 0),
                    channel.get('total_clients', 0),
                    timestamp
                )
                for channel in channels
            ]

            psycopg2.extras.execute_batch(
                cursor,
                """
                INSERT INTO channels
                (channel_id, channel_name, parent_channel_id, channel_order, total_clients, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (channel_id) DO UPDATE SET
                    channel_name = EXCLUDED.channel_name,
                    parent_channel_id = EXCLUDED.parent_channel_id,
                    channel_order = EXCLUDED.channel_order,
                    total_clients = EXCLUDED.total_clients,
                    last_updated = EXCLUDED.last_updated
                """,
                channel_data
            )

            logger.debug(f"Updated {len(channels)} channels in cache")
            return len(channels)

    def get_channel_name(self, channel_id: int) -> Optional[str]:
        """Get channel name from cache."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT channel_name FROM channels WHERE channel_id = %s", (channel_id,))
            row = cursor.fetchone()
            return row['channel_name'] if row else None

    def get_all_channels(self) -> List[Dict[str, any]]:
        """Get all channels from cache."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT channel_id, channel_name, parent_channel_id, channel_order, total_clients, last_updated
                FROM channels
                ORDER BY channel_order
            """)

            return [
                {
                    'channel_id': row['channel_id'],
                    'channel_name': row['channel_name'],
                    'parent_channel_id': row['parent_channel_id'],
                    'channel_order': row['channel_order'],
                    'total_clients': row['total_clients'],
                    'last_updated': row['last_updated']
                }
                for row in cursor.fetchall()
            ]

    def update_user_aggregates(self, date: Optional[str] = None) -> int:
        """Update user aggregates for a specific date."""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        # Calculate start and end timestamps for the date
        start_time = int(datetime.strptime(date, '%Y-%m-%d').timestamp())
        end_time = start_time + 86400  # +24 hours

        poll_interval = int(self._get_metadata('poll_interval') or '60')

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Aggregate data from client_snapshots
            cursor.execute("""
                INSERT INTO user_aggregates
                (client_uid, date, nickname, total_samples, online_seconds, avg_idle_ms,
                 most_visited_channel_id, is_away_count, is_talking_count, input_muted_count,
                 output_muted_count, is_recording_count)
                SELECT
                    cs.client_uid,
                    %s as date,
                    MAX(cs.nickname) as nickname,
                    COUNT(*) as total_samples,
                    COUNT(*) * %s as online_seconds,
                    AVG(cs.idle_ms) as avg_idle_ms,
                    (
                        SELECT channel_id
                        FROM client_snapshots cs2
                        JOIN snapshots s2 ON cs2.snapshot_id = s2.id
                        WHERE cs2.client_uid = cs.client_uid
                          AND s2.timestamp BETWEEN %s AND %s
                        GROUP BY channel_id
                        ORDER BY COUNT(*) DESC
                        LIMIT 1
                    ) as most_visited_channel_id,
                    SUM(cs.is_away) as is_away_count,
                    SUM(cs.is_talking) as is_talking_count,
                    SUM(cs.input_muted) as input_muted_count,
                    SUM(cs.output_muted) as output_muted_count,
                    SUM(cs.is_recording) as is_recording_count
                FROM client_snapshots cs
                JOIN snapshots s ON cs.snapshot_id = s.id
                WHERE s.timestamp BETWEEN %s AND %s
                GROUP BY cs.client_uid
                ON CONFLICT (client_uid, date) DO UPDATE SET
                    nickname = EXCLUDED.nickname,
                    total_samples = EXCLUDED.total_samples,
                    online_seconds = EXCLUDED.online_seconds,
                    avg_idle_ms = EXCLUDED.avg_idle_ms,
                    most_visited_channel_id = EXCLUDED.most_visited_channel_id,
                    is_away_count = EXCLUDED.is_away_count,
                    is_talking_count = EXCLUDED.is_talking_count,
                    input_muted_count = EXCLUDED.input_muted_count,
                    output_muted_count = EXCLUDED.output_muted_count,
                    is_recording_count = EXCLUDED.is_recording_count
            """, (date, poll_interval, start_time, end_time, start_time, end_time))

            count = cursor.rowcount
            logger.info(f"Updated {count} user aggregates for {date}")
            return count

    def set_poll_interval(self, interval: int) -> None:
        """Set polling interval in metadata."""
        self.set_metadata('poll_interval', str(interval))

    def close(self) -> None:
        """Close all connections in the pool."""
        if self.pool:
            self.pool.closeall()
            logger.info("PostgreSQL connection pool closed")
