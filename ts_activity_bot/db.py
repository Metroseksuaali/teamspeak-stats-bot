"""
Database management for TS6 Activity Bot.

Handles SQLite schema creation, migrations, and data operations.

Copyright (C) 2025 Metroseksuaali
Licensed under GNU AGPL v3.0 - see LICENSE file for details.
"""

import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


SCHEMA_VERSION = 2

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

-- Metadata table for versioning and settings
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class Database:
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
