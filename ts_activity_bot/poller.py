"""
Polling service for TS6 Activity Bot.

Periodically queries TeamSpeak server and stores activity data.

Copyright (C) 2025 Metroseksuaali
Licensed under GNU AGPL v3.0 - see LICENSE file for details.
"""

import logging
import signal
import sys
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ts_activity_bot.config import get_config
from ts_activity_bot.db import Database
from ts_activity_bot.query_client import create_client

# Global flag for graceful shutdown
shutdown_requested = False


def setup_logging(config) -> None:
    """
    Setup logging configuration.

    Args:
        config: Logging configuration
    """
    log_level = getattr(logging, config.logging.level)
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    handlers = []

    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))
    handlers.append(console_handler)

    # File handler (if configured)
    if config.logging.file:
        log_file = Path(config.logging.file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            config.logging.file,
            maxBytes=config.logging.max_bytes,
            backupCount=config.logging.backup_count
        )
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True
    )

    # Reduce noise from httpx
    logging.getLogger('httpx').setLevel(logging.WARNING)


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    signal_name = signal.Signals(signum).name
    logging.info(f"Received signal {signal_name}, initiating graceful shutdown...")
    shutdown_requested = True


def exponential_backoff(attempt: int, base: int = 2) -> int:
    """
    Calculate exponential backoff delay.

    Args:
        attempt: Retry attempt number (0-indexed)
        base: Base delay in seconds

    Returns:
        int: Delay in seconds
    """
    return base ** attempt


def poll_once(client, db, logger) -> bool:
    """
    Execute one polling iteration.

    Args:
        client: TeamSpeak query client
        db: Database instance
        logger: Logger instance

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Fetch current clients
        clients = client.fetch_clientlist()

        # Insert snapshot into database
        snapshot_id = db.insert_snapshot(clients)

        logger.info(f"Snapshot {snapshot_id}: {len(clients)} clients online")
        return True

    except Exception as e:
        logger.error(f"Poll failed: {e}", exc_info=True)
        return False


def cleanup_old_data(db, retention_days: int, logger) -> None:
    """
    Clean up old data based on retention policy.

    Args:
        db: Database instance
        retention_days: Days to keep
        logger: Logger instance
    """
    try:
        deleted = db.cleanup_old_data(retention_days)
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old snapshots (retention: {retention_days} days)")
    except Exception as e:
        logger.error(f"Data cleanup failed: {e}", exc_info=True)


def update_channel_cache(client, db, logger) -> None:
    """
    Update channel name cache from TeamSpeak server.

    Args:
        client: TeamSpeak query client
        db: Database instance
        logger: Logger instance
    """
    try:
        channels = client.fetch_channellist()
        count = db.upsert_channels(channels)
        logger.info(f"Updated channel cache: {count} channels")
    except Exception as e:
        logger.error(f"Channel cache update failed: {e}", exc_info=True)


def update_aggregates(db, logger) -> None:
    """
    Update user aggregates for yesterday's data.

    Args:
        db: Database instance
        logger: Logger instance
    """
    try:
        from datetime import datetime, timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        count = db.update_user_aggregates(yesterday)
        logger.info(f"Updated user aggregates for {yesterday}: {count} users")
    except Exception as e:
        logger.error(f"User aggregates update failed: {e}", exc_info=True)


def main():
    """Main polling loop."""
    global shutdown_requested

    # Load configuration
    try:
        config = get_config()
    except Exception as e:
        print(f"Failed to load configuration: {e}", file=sys.stderr)
        sys.exit(1)

    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("TeamSpeak 6 Activity Stats Bot - Poller Service")
    logger.info("=" * 60)
    logger.info(f"Server: {config.teamspeak.base_url}")
    logger.info(f"Virtual Server ID: {config.teamspeak.virtual_server_id}")
    logger.info(f"Poll interval: {config.polling.interval_seconds}s")
    logger.info(f"Database: {config.database.path}")
    logger.info(f"Data retention: {config.database.retention_days or 'unlimited'} days")
    logger.info("=" * 60)

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize database
    try:
        db = Database(config.database.path)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        sys.exit(1)

    # Initialize TeamSpeak client
    try:
        client = create_client(config.teamspeak)
        logger.info("TeamSpeak client created")

        # Test connection
        if client.test_connection():
            logger.info("TeamSpeak server connection verified")
        else:
            logger.warning("TeamSpeak server connection test failed, but continuing...")

    except Exception as e:
        logger.error(f"Failed to create TeamSpeak client: {e}", exc_info=True)
        sys.exit(1)

    # Track last maintenance times
    last_cleanup = datetime.now()
    last_channel_update = datetime.now()
    last_aggregate_update = datetime.now()
    cleanup_interval = timedelta(hours=24)  # Run cleanup daily
    channel_update_interval = timedelta(hours=1)  # Update channels hourly
    aggregate_update_interval = timedelta(hours=6)  # Update aggregates every 6 hours

    # Store poll interval in metadata for aggregation calculations
    db.set_poll_interval(config.polling.interval_seconds)

    # Initial channel cache update
    logger.info("Performing initial channel cache update...")
    update_channel_cache(client, db, logger)

    logger.info("Starting polling loop...")
    consecutive_failures = 0
    max_consecutive_failures = 10

    try:
        while not shutdown_requested:
            poll_start = time.time()

            # Execute poll
            success = poll_once(client, db, logger)

            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1

                # If too many consecutive failures, try to reconnect
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(f"Too many consecutive failures ({consecutive_failures}), attempting to reconnect...")
                    try:
                        client.close()
                        client = create_client(config.teamspeak)
                        consecutive_failures = 0
                        logger.info("Reconnected to TeamSpeak server")
                    except Exception as e:
                        logger.error(f"Reconnection failed: {e}")

                # Exponential backoff on failures
                if consecutive_failures > 0 and consecutive_failures <= config.polling.max_retries:
                    backoff_delay = exponential_backoff(
                        consecutive_failures - 1,
                        config.polling.retry_backoff_base
                    )
                    logger.warning(f"Retrying in {backoff_delay}s (attempt {consecutive_failures})")
                    time.sleep(backoff_delay)
                    continue

            # Run periodic maintenance tasks
            now = datetime.now()

            # Data cleanup (if retention policy is set)
            if config.database.retention_days:
                if now - last_cleanup >= cleanup_interval:
                    cleanup_old_data(db, config.database.retention_days, logger)
                    last_cleanup = now

            # Channel cache update
            if now - last_channel_update >= channel_update_interval:
                update_channel_cache(client, db, logger)
                last_channel_update = now

            # User aggregates update
            if now - last_aggregate_update >= aggregate_update_interval:
                update_aggregates(db, logger)
                last_aggregate_update = now

            # Sleep until next poll
            poll_duration = time.time() - poll_start
            sleep_time = max(0, config.polling.interval_seconds - poll_duration)

            if sleep_time > 0:
                logger.debug(f"Sleeping for {sleep_time:.1f}s until next poll")
                time.sleep(sleep_time)

    except Exception as e:
        logger.error(f"Unexpected error in polling loop: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Cleanup
        logger.info("Shutting down gracefully...")
        try:
            client.close()
            logger.info("TeamSpeak client closed")
        except Exception as e:
            logger.error(f"Error closing client: {e}")

        logger.info("Poller service stopped")


if __name__ == "__main__":
    main()
