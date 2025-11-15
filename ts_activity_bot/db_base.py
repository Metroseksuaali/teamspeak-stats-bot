"""
Abstract database interface for TS6 Activity Bot.

Defines the interface that all database backends must implement.

Copyright (C) 2025 Metroseksuaali
Licensed under GNU AGPL v3.0 - see LICENSE file for details.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple


class DatabaseBackend(ABC):
    """Abstract base class for database backends."""

    @abstractmethod
    def __init__(self, connection_string: str):
        """
        Initialize database backend.

        Args:
            connection_string: Database connection string (path for SQLite, URI for PostgreSQL)
        """
        pass

    @abstractmethod
    def initialize_schema(self) -> None:
        """Initialize database schema and run migrations if needed."""
        pass

    @abstractmethod
    @contextmanager
    def get_connection(self):
        """
        Get database connection context manager.

        Yields:
            Connection object (type depends on backend)
        """
        pass

    @abstractmethod
    def insert_snapshot(self, clients: List[Dict[str, any]]) -> int:
        """
        Insert a new snapshot with client data.

        Args:
            clients: List of client dictionaries from TeamSpeak

        Returns:
            int: Snapshot ID
        """
        pass

    @abstractmethod
    def cleanup_old_data(self, retention_days: int) -> int:
        """
        Delete snapshots older than retention period.

        Args:
            retention_days: Number of days to keep

        Returns:
            int: Number of snapshots deleted
        """
        pass

    @abstractmethod
    def get_database_stats(self) -> Dict[str, any]:
        """
        Get database statistics.

        Returns:
            dict: Database statistics including size, counts, etc.
        """
        pass

    @abstractmethod
    def _get_metadata(self, key: str) -> Optional[str]:
        """
        Get metadata value.

        Args:
            key: Metadata key

        Returns:
            str: Metadata value or None if not found
        """
        pass

    @abstractmethod
    def set_metadata(self, key: str, value: str) -> None:
        """
        Set metadata value.

        Args:
            key: Metadata key
            value: Metadata value
        """
        pass

    @abstractmethod
    def upsert_channels(self, channels: List[Dict[str, any]]) -> int:
        """
        Insert or update channel metadata cache.

        Args:
            channels: List of channel dictionaries from TeamSpeak

        Returns:
            int: Number of channels updated
        """
        pass

    @abstractmethod
    def get_channel_name(self, channel_id: int) -> Optional[str]:
        """
        Get channel name from cache.

        Args:
            channel_id: Channel ID

        Returns:
            str: Channel name or None if not found
        """
        pass

    @abstractmethod
    def get_all_channels(self) -> List[Dict[str, any]]:
        """
        Get all channels from cache.

        Returns:
            list: List of channel dictionaries
        """
        pass

    @abstractmethod
    def update_user_aggregates(self, date: Optional[str] = None) -> int:
        """
        Update user aggregates for a specific date.

        Args:
            date: Date in YYYY-MM-DD format (default: today)

        Returns:
            int: Number of user aggregates updated
        """
        pass

    @abstractmethod
    def set_poll_interval(self, interval: int) -> None:
        """
        Set polling interval in metadata.

        Args:
            interval: Polling interval in seconds
        """
        pass

    def close(self) -> None:
        """Close database connections and cleanup resources (optional)."""
        pass
