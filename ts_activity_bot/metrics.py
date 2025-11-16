"""
Prometheus metrics exporter for TS6 Activity Bot.

Exposes TeamSpeak statistics in Prometheus format for monitoring and alerting.

Copyright (C) 2025 Metroseksuaali
Licensed under GNU AGPL v3.0 - see LICENSE file for details.
"""

import logging
from typing import Dict

from prometheus_client import Counter, Gauge, Histogram, Info, generate_latest, CONTENT_TYPE_LATEST

from ts_activity_bot.config import get_config
from ts_activity_bot.stats import StatsCalculator

logger = logging.getLogger(__name__)

# Define Prometheus metrics

# Info metrics
ts_info = Info('ts_bot', 'TeamSpeak Activity Bot information')

# Gauge metrics (current values)
ts_users_total = Gauge('ts_users_total', 'Total unique users tracked')
ts_users_online = Gauge('ts_users_online', 'Currently online users')
ts_users_online_active = Gauge('ts_users_online_active', 'Currently online and active users (not idle/away)')
ts_peak_users = Gauge('ts_peak_users', 'Peak concurrent users (7 days)')
ts_avg_users_online = Gauge('ts_avg_users_online', 'Average users online (7 days)')

# LTV distribution
ts_ltv_power_users = Gauge('ts_ltv_power_users', 'Number of power users (LTV 80-100)')
ts_ltv_regular_users = Gauge('ts_ltv_regular_users', 'Number of regular users (LTV 50-79)')
ts_ltv_casual_users = Gauge('ts_ltv_casual_users', 'Number of casual users (LTV 0-49)')
ts_ltv_avg_score = Gauge('ts_ltv_avg_score', 'Average LTV score across all users')

# Channel metrics
ts_channels_total = Gauge('ts_channels_total', 'Total number of channels')
ts_channel_visits = Gauge('ts_channel_visits', 'Total visits to channel', ['channel_id', 'channel_name'])
ts_channel_unique_users = Gauge('ts_channel_unique_users', 'Unique users in channel', ['channel_id', 'channel_name'])

# Snapshot metrics
ts_snapshots_total = Counter('ts_snapshots_total', 'Total number of snapshots collected')
ts_snapshot_collection_seconds = Histogram('ts_snapshot_collection_seconds', 'Time spent collecting snapshot')

# Database metrics
ts_database_size_bytes = Gauge('ts_database_size_bytes', 'Database file size in bytes')


class MetricsCollector:
    """Collects and updates Prometheus metrics from TeamSpeak statistics."""

    def __init__(self, config=None):
        """
        Initialize metrics collector.

        Args:
            config: Bot configuration (if None, loads from get_config())
        """
        if config is None:
            config = get_config()

        self.config = config
        self.stats_calc = StatsCalculator(config.database.path, config.polling.interval_seconds)

        # Set static info
        ts_info.info({
            'version': '2.0.0',
            'server': config.teamspeak.base_url,
            'virtual_server_id': str(config.teamspeak.virtual_server_id)
        })

        logger.info("Prometheus metrics collector initialized")

    def update_metrics(self) -> None:
        """Update all Prometheus metrics with current data."""
        try:
            # Summary stats (7 days)
            summary = self.stats_calc.get_summary(days=7)
            ts_users_total.set(summary['unique_users'])
            ts_avg_users_online.set(summary['avg_users_online'])
            ts_peak_users.set(summary['max_users_online'])

            # Currently online users
            online_users = self.stats_calc.get_online_now()
            ts_users_online.set(len(online_users))

            # Count active users (not away and idle < 5 minutes)
            active_users = sum(
                1 for u in online_users
                if not u['is_away'] and u['idle_minutes'] < 5
            )
            ts_users_online_active.set(active_users)

            # LTV distribution
            ltv_summary = self.stats_calc.get_ltv_summary(days=None)  # All time
            ts_ltv_power_users.set(ltv_summary['power_users'])
            ts_ltv_regular_users.set(ltv_summary['regular_users'])
            ts_ltv_casual_users.set(ltv_summary['casual_users'])
            ts_ltv_avg_score.set(ltv_summary['avg_ltv_score'])

            # Channel statistics (7 days)
            channels = self.stats_calc.get_channel_stats(days=7)
            ts_channels_total.set(len(channels))

            # Update per-channel metrics
            for channel in channels[:20]:  # Limit to top 20 channels to avoid cardinality explosion
                channel_id = str(channel['channel_id'])
                channel_name = channel['channel_name']

                ts_channel_visits.labels(
                    channel_id=channel_id,
                    channel_name=channel_name
                ).set(channel['total_visits'])

                ts_channel_unique_users.labels(
                    channel_id=channel_id,
                    channel_name=channel_name
                ).set(channel['unique_users'])

            # Database size
            import os
            if os.path.exists(self.config.database.path):
                db_size = os.path.getsize(self.config.database.path)
                ts_database_size_bytes.set(db_size)

            # Snapshot count (from summary)
            ts_snapshots_total._value._value = summary['total_snapshots']  # Set counter value directly

            logger.debug("Prometheus metrics updated successfully")

        except Exception as e:
            logger.error(f"Failed to update Prometheus metrics: {e}", exc_info=True)

    def get_metrics(self) -> bytes:
        """
        Get current metrics in Prometheus text format.

        Returns:
            bytes: Prometheus metrics in text format
        """
        self.update_metrics()
        return generate_latest()


def create_metrics_collector(config=None) -> MetricsCollector:
    """
    Factory function to create metrics collector.

    Args:
        config: Bot configuration (if None, loads from get_config())

    Returns:
        MetricsCollector: Configured collector instance
    """
    return MetricsCollector(config)
