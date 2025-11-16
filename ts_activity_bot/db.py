"""
Database management for TS6 Activity Bot.

Handles SQLite schema creation, migrations, and data operations.
Provides factory function for multi-backend support (SQLite, PostgreSQL).

Copyright (C) 2025 Metroseksuaali
Licensed under GNU AGPL v3.0 - see LICENSE file for details.
"""

import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ts_activity_bot.db_base import DatabaseBackend

logger = logging.getLogger(__name__)


SCHEMA_VERSION = 3

SCHEMA_SQL = """
-- Main snapshots table (one row per poll)
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    total_clients INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp);

-- Client presence in each snapshot
CREATE TABLE IF NOT EXISTS client_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    client_uid TEXT NOT NULL,
    client_database_id INTEGER,
    nickname TEXT NOT NULL,
    channel_id INTEGER NOT NULL,
    idle_ms INTEGER,
    -- Away status tracking
    is_away INTEGER DEFAULT 0,
    away_message TEXT,
    -- Voice/mute status tracking
    is_talking INTEGER DEFAULT 0,
    input_muted INTEGER DEFAULT 0,
    output_muted INTEGER DEFAULT 0,
    is_recording INTEGER DEFAULT 0,
    -- Server groups (comma-separated IDs)
    server_groups TEXT,
    -- Connection info
    connected_time INTEGER,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
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
    last_updated INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_channels_parent ON channels(parent_channel_id);

-- User daily aggregates for faster queries
CREATE TABLE IF NOT EXISTS user_aggregates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_uid TEXT NOT NULL,
    date TEXT NOT NULL, -- YYYY-MM-DD format
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


class Database(DatabaseBackend):
    """SQLite database manager for TS6 activity tracking."""

    def __init__(self, db_path: str):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_directory()
        self._init_schema()

    def _ensure_directory(self) -> None:
        """Ensure database directory exists."""
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.

        Yields:
            sqlite3.Connection: Database connection

        Example:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM snapshots")
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize_schema(self) -> None:
        """Initialize database schema and run migrations if needed."""
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema if not exists."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Create tables
            cursor.executescript(SCHEMA_SQL)

            # Check schema version
            cursor.execute("SELECT value FROM metadata WHERE key = 'schema_version'")
            row = cursor.fetchone()

            if row is None:
                # First time setup
                cursor.execute(
                    "INSERT INTO metadata (key, value) VALUES ('schema_version', ?)",
                    (str(SCHEMA_VERSION),)
                )
                logger.info(f"Database initialized with schema version {SCHEMA_VERSION}")
            else:
                current_version = int(row[0])
                if current_version < SCHEMA_VERSION:
                    logger.info(f"Migrating database from version {current_version} to {SCHEMA_VERSION}")
                    self._migrate_schema(conn, current_version, SCHEMA_VERSION)

    def _migrate_schema(self, conn: sqlite3.Connection, from_version: int, to_version: int) -> None:
        """
        Migrate database schema between versions.

        Args:
            conn: Database connection
            from_version: Current schema version
            to_version: Target schema version
        """
        cursor = conn.cursor()

        # Migration from version 1 to 2: Add new tracking fields
        if from_version < 2:
            logger.info("Migrating schema v1 -> v2: Adding away/voice/groups tracking")

            # Add new columns to client_snapshots
            cursor.execute("ALTER TABLE client_snapshots ADD COLUMN is_away INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE client_snapshots ADD COLUMN away_message TEXT")
            cursor.execute("ALTER TABLE client_snapshots ADD COLUMN is_talking INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE client_snapshots ADD COLUMN input_muted INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE client_snapshots ADD COLUMN output_muted INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE client_snapshots ADD COLUMN is_recording INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE client_snapshots ADD COLUMN server_groups TEXT")
            cursor.execute("ALTER TABLE client_snapshots ADD COLUMN connected_time INTEGER")

            # Add index for channel_id
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel_id ON client_snapshots(channel_id)")

            # Update schema version
            cursor.execute("UPDATE metadata SET value = '2' WHERE key = 'schema_version'")
            logger.info("Schema migration v1 -> v2 completed")

        # Migration from version 2 to 3: Add channels cache and user aggregates
        if from_version < 3:
            logger.info("Migrating schema v2 -> v3: Adding channels cache and user aggregates")

            # Create channels table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id INTEGER PRIMARY KEY,
                    channel_name TEXT NOT NULL,
                    parent_channel_id INTEGER,
                    channel_order INTEGER,
                    total_clients INTEGER DEFAULT 0,
                    last_updated INTEGER NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channels_parent ON channels(parent_channel_id)")

            # Create user_aggregates table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_aggregates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_aggregates_uid ON user_aggregates(client_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_aggregates_date ON user_aggregates(date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_aggregates_uid_date ON user_aggregates(client_uid, date)")

            # Update schema version
            cursor.execute("UPDATE metadata SET value = '3' WHERE key = 'schema_version'")
            logger.info("Schema migration v2 -> v3 completed")

        logger.info(f"Schema migration completed: {from_version} -> {to_version}")

    def insert_snapshot(self, clients: List[Dict[str, any]]) -> int:
        """
        Insert a new snapshot with client data.

        Args:
            clients: List of client dictionaries from TeamSpeak

        Returns:
            int: Snapshot ID

        Example:
            snapshot_id = db.insert_snapshot([
                {
                    'client_unique_identifier': 'abc123',
                    'client_database_id': 5,
                    'client_nickname': 'User1',
                    'cid': 1,
                    'client_idle_time': 1000
                }
            ])
        """
        timestamp = int(time.time())
        total_clients = len(clients)

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Insert snapshot
            cursor.execute(
                "INSERT INTO snapshots (timestamp, total_clients) VALUES (?, ?)",
                (timestamp, total_clients)
            )
            snapshot_id = cursor.lastrowid

            # Insert client snapshots
            client_data = [
                (
                    snapshot_id,
                    client.get('client_unique_identifier', 'unknown'),
                    client.get('client_database_id'),
                    client.get('client_nickname', 'Unknown'),
                    client.get('cid', 0),
                    client.get('client_idle_time'),
                    # Away status
                    1 if client.get('client_away', 0) == 1 else 0,
                    client.get('client_away_message', ''),
                    # Voice/mute status
                    1 if client.get('client_is_talker', 0) == 1 else 0,
                    1 if client.get('client_input_muted', 0) == 1 else 0,
                    1 if client.get('client_output_muted', 0) == 1 else 0,
                    1 if client.get('client_is_recording', 0) == 1 else 0,
                    # Server groups (comma-separated)
                    client.get('client_servergroups', ''),
                    # Connection time
                    client.get('connection_connected_time')
                )
                for client in clients
            ]

            cursor.executemany(
                """
                INSERT INTO client_snapshots
                (snapshot_id, client_uid, client_database_id, nickname, channel_id, idle_ms,
                 is_away, away_message, is_talking, input_muted, output_muted, is_recording,
                 server_groups, connected_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                client_data
            )

            logger.debug(f"Inserted snapshot {snapshot_id} with {total_clients} clients")
            return snapshot_id

    def cleanup_old_data(self, retention_days: int) -> int:
        """
        Delete data older than retention period.

        Args:
            retention_days: Number of days to keep

        Returns:
            int: Number of snapshots deleted
        """
        cutoff_timestamp = int(time.time()) - (retention_days * 86400)

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get count before deletion
            cursor.execute("SELECT COUNT(*) FROM snapshots WHERE timestamp < ?", (cutoff_timestamp,))
            count = cursor.fetchone()[0]

            if count > 0:
                # Delete old snapshots (CASCADE will delete client_snapshots)
                cursor.execute("DELETE FROM snapshots WHERE timestamp < ?", (cutoff_timestamp,))
                logger.info(f"Cleaned up {count} snapshots older than {retention_days} days")

            return count

    def get_database_stats(self) -> Dict[str, any]:
        """
        Get database statistics.

        Returns:
            dict: Database stats including size, row counts, date range
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # File size
            db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0

            # Row counts
            cursor.execute("SELECT COUNT(*) FROM snapshots")
            snapshot_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM client_snapshots")
            client_snapshot_count = cursor.fetchone()[0]

            # Date range
            cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM snapshots")
            row = cursor.fetchone()
            first_snapshot = row[0] if row[0] else None
            last_snapshot = row[1] if row[1] else None

            # Unique clients
            cursor.execute("SELECT COUNT(DISTINCT client_uid) FROM client_snapshots")
            unique_clients = cursor.fetchone()[0]

            return {
                'db_size_bytes': db_size,
                'db_size_mb': round(db_size / 1024 / 1024, 2),
                'snapshot_count': snapshot_count,
                'client_snapshot_count': client_snapshot_count,
                'unique_clients': unique_clients,
                'first_snapshot_timestamp': first_snapshot,
                'last_snapshot_timestamp': last_snapshot,
                'schema_version': self._get_metadata('schema_version')
            }

    def _get_metadata(self, key: str) -> Optional[str]:
        """Get metadata value by key."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM metadata WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None

    def set_metadata(self, key: str, value: str) -> None:
        """Set metadata value."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                (key, value)
            )

    def upsert_channels(self, channels: List[Dict[str, any]]) -> int:
        """
        Insert or update channel metadata cache.

        Args:
            channels: List of channel dictionaries from TeamSpeak

        Returns:
            int: Number of channels updated

        Example:
            db.upsert_channels([
                {
                    'cid': 1,
                    'channel_name': 'Lobby',
                    'pid': 0,
                    'channel_order': 0,
                    'total_clients': 5
                }
            ])
        """
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

            cursor.executemany(
                """
                INSERT OR REPLACE INTO channels
                (channel_id, channel_name, parent_channel_id, channel_order, total_clients, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                channel_data
            )

            logger.debug(f"Updated {len(channels)} channels in cache")
            return len(channels)

    def get_channel_name(self, channel_id: int) -> Optional[str]:
        """
        Get channel name from cache.

        Args:
            channel_id: Channel ID

        Returns:
            str: Channel name or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT channel_name FROM channels WHERE channel_id = ?", (channel_id,))
            row = cursor.fetchone()
            return row[0] if row else None

    def get_all_channels(self) -> List[Dict[str, any]]:
        """
        Get all channels from cache.

        Returns:
            list: List of channel dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT channel_id, channel_name, parent_channel_id, channel_order, total_clients, last_updated
                FROM channels
                ORDER BY channel_order
            """)

            channels = []
            for row in cursor.fetchall():
                channels.append({
                    'channel_id': row[0],
                    'channel_name': row[1],
                    'parent_channel_id': row[2],
                    'channel_order': row[3],
                    'total_clients': row[4],
                    'last_updated': row[5]
                })

            return channels

    def update_user_aggregates(self, date: Optional[str] = None) -> int:
        """
        Update user aggregates for a specific date.
        Aggregates data from client_snapshots into daily summaries.

        Args:
            date: Date in YYYY-MM-DD format (default: today)

        Returns:
            int: Number of user aggregates updated
        """
        from datetime import datetime

        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        # Calculate start and end timestamps for the date
        start_time = int(datetime.strptime(date, '%Y-%m-%d').timestamp())
        end_time = start_time + 86400  # +24 hours

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Aggregate data from client_snapshots
            cursor.execute("""
                INSERT OR REPLACE INTO user_aggregates
                (client_uid, date, nickname, total_samples, online_seconds, avg_idle_ms,
                 most_visited_channel_id, is_away_count, is_talking_count, input_muted_count,
                 output_muted_count, is_recording_count)
                SELECT
                    cs.client_uid,
                    ? as date,
                    MAX(cs.nickname) as nickname,
                    COUNT(*) as total_samples,
                    COUNT(*) * ? as online_seconds,
                    AVG(cs.idle_ms) as avg_idle_ms,
                    (
                        SELECT channel_id
                        FROM client_snapshots cs2
                        WHERE cs2.client_uid = cs.client_uid
                          AND s2.timestamp BETWEEN ? AND ?
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
                LEFT JOIN snapshots s2 ON s2.id = cs.snapshot_id
                WHERE s.timestamp BETWEEN ? AND ?
                GROUP BY cs.client_uid
            """, (date, self._get_poll_interval(), start_time, end_time, start_time, end_time))

            count = cursor.rowcount
            logger.info(f"Updated {count} user aggregates for {date}")
            return count

    def _get_poll_interval(self) -> int:
        """
        Get polling interval from metadata or use default.

        Returns:
            int: Polling interval in seconds
        """
        interval_str = self._get_metadata('poll_interval')
        return int(interval_str) if interval_str else 60  # Default 60 seconds

    def set_poll_interval(self, interval: int) -> None:
        """
        Set polling interval in metadata.

        Args:
            interval: Polling interval in seconds
        """
        self.set_metadata('poll_interval', str(interval))


def create_database(config) -> DatabaseBackend:
    """
    Factory function to create database backend based on configuration.

    Args:
        config: DatabaseConfig or full Config object

    Returns:
        DatabaseBackend: Database backend instance (SQLite or PostgreSQL)

    Raises:
        ValueError: If backend type is not supported
        ImportError: If required database driver is not installed
    """
    # Extract database config if full config object is passed
    db_config = getattr(config, 'database', config)

    backend = db_config.backend.lower()

    if backend == 'sqlite':
        logger.info(f"Using SQLite database backend: {db_config.path}")
        return Database(db_config.path)

    elif backend == 'postgresql':
        if not db_config.connection_string:
            raise ValueError("PostgreSQL backend requires connection_string in config")

        try:
            from ts_activity_bot.db_postgres import PostgreSQLBackend
        except ImportError as e:
            raise ImportError(
                "PostgreSQL support requires psycopg2. Install with: pip install psycopg2-binary"
            ) from e

        logger.info(f"Using PostgreSQL database backend")
        return PostgreSQLBackend(db_config.connection_string)

    else:
        raise ValueError(f"Unsupported database backend: {backend}")
