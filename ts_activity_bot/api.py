"""
FastAPI web server for TS6 Activity Bot.

Provides REST API for querying statistics.

Copyright (C) 2025 Metroseksuaali
Licensed under GNU AGPL v3.0 - see LICENSE file for details.
"""

import logging
import sys
from datetime import datetime
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Response, Security
from fastapi.security import APIKeyHeader, APIKeyQuery
from pydantic import BaseModel

from ts_activity_bot.config import get_config
from ts_activity_bot.db import create_database
from ts_activity_bot.stats import StatsCalculator
from ts_activity_bot.graphql_schema import create_graphql_router, set_stats_calculator
from ts_activity_bot.metrics import create_metrics_collector

# Initialize config and stats
try:
    config = get_config()
except Exception as e:
    print(f"Failed to load configuration: {e}", file=sys.stderr)
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.logging.level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize database backend (SQLite or PostgreSQL based on config)
db = create_database(config)

# Initialize stats calculator (always points at the SQLite analytics file)
stats_calc: StatsCalculator = StatsCalculator(
    config.database.path,
    config.polling.interval_seconds,
)
if config.database.backend != "sqlite":
    logger.warning(
        "Analytics endpoints still read from the SQLite database at %s while backend=%s. "
        "Keep that file in sync (or provide a replica) if you need fresh stats.",
        config.database.path,
        config.database.backend,
    )

set_stats_calculator(stats_calc)

# Initialize Prometheus metrics collector
metrics_collector = create_metrics_collector(config)

# Initialize FastAPI
app = FastAPI(
    title="TeamSpeak Activity Stats API",
    description="REST API for querying TeamSpeak 3 (3.13+) and TeamSpeak 6 server activity statistics",
    version="2.0.0",
    docs_url="/docs" if config.api.docs_enabled else None,
    redoc_url="/redoc" if config.api.docs_enabled else None
)

# Mount GraphQL router when analytics backend is available
graphql_router = create_graphql_router()
if graphql_router is not None:
    app.include_router(graphql_router, prefix="")
else:
    logger.info("GraphQL API is disabled because analytics requires a SQLite backend")

# API Key authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)


async def verify_api_key(
    api_key_header: str = Security(api_key_header),
    api_key_query: str = Security(api_key_query)
):
    """Verify API key from header or query parameter."""
    api_key = api_key_header or api_key_query

    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    if api_key != config.api.get_auth_token():
        raise HTTPException(status_code=403, detail="Invalid API key")

    return api_key


# Response models
class HealthResponse(BaseModel):
    status: str
    database: str
    last_snapshot: Optional[int] = None


class UserStat(BaseModel):
    client_uid: str
    nickname: str
    online_hours: float
    first_seen: int
    last_seen: int


class HourlyHeatmap(BaseModel):
    hour: int
    avg_clients: float
    sample_count: int


class DailyActivity(BaseModel):
    day_of_week: int
    day_name: str
    avg_clients: float
    sample_count: int


class IdleUser(BaseModel):
    client_uid: str
    nickname: str
    avg_idle_ms: int
    avg_idle_minutes: float


class PeakTime(BaseModel):
    timestamp: int
    datetime: str
    total_clients: int


class ChannelStat(BaseModel):
    channel_id: int
    channel_name: str
    total_visits: int
    unique_users: int
    avg_idle_ms: int


class GrowthMetrics(BaseModel):
    period_days: int
    total_unique_users: int
    new_users: int
    returning_users: int
    new_user_percentage: float


class OnlineUser(BaseModel):
    client_uid: str
    nickname: str
    channel_id: int
    channel_name: str
    idle_ms: Optional[int]
    idle_minutes: float
    is_away: bool
    away_message: str
    is_talking: bool
    input_muted: bool
    output_muted: bool
    is_recording: bool
    server_groups: list[str]
    connected_time: Optional[int]
    connected_hours: float


class Summary(BaseModel):
    period_days: Optional[int]
    total_snapshots: int
    avg_users_online: float
    max_users_online: int
    unique_users: int


class DatabaseStats(BaseModel):
    db_size_mb: float
    snapshot_count: int
    client_snapshot_count: int
    unique_clients: int
    first_snapshot_timestamp: Optional[int]
    last_snapshot_timestamp: Optional[int]
    schema_version: str


class AwayUser(BaseModel):
    client_uid: str
    nickname: str
    total_samples: int
    away_count: int
    away_percentage: float
    last_away_message: str


class AwayStats(BaseModel):
    period_days: Optional[int]
    total_samples: int
    away_samples: int
    away_percentage: float
    top_away_users: list[AwayUser]


class TopRecorder(BaseModel):
    client_uid: str
    nickname: str
    recording_count: int
    recording_percentage: float


class MuteStats(BaseModel):
    period_days: Optional[int]
    total_samples: int
    mic_muted_percentage: float
    speaker_muted_percentage: float
    recording_percentage: float
    talking_percentage: float
    top_recorders: list[TopRecorder]


class ServerGroup(BaseModel):
    group_id: str
    unique_members: int
    total_samples: int


class ChannelHopper(BaseModel):
    client_uid: str
    nickname: str
    total_samples: int
    channel_switches: int
    switches_per_hour: float


class Reconnector(BaseModel):
    client_uid: str
    nickname: str
    session_count: int
    avg_session_length_minutes: float


class ConnectionPatterns(BaseModel):
    period_days: Optional[int]
    total_users: int
    avg_online_time_hours: float
    top_reconnectors: list[Reconnector]


class LTVUser(BaseModel):
    client_uid: str
    nickname: str
    ltv_score: int
    category: str
    category_label: str
    online_hours: float
    days_active: int
    activity_frequency_percent: float
    channels_visited: int
    talking_percentage: float
    avg_idle_minutes: float
    session_count: int
    avg_session_length_hours: float
    first_seen: int
    last_seen: int


class LTVSummary(BaseModel):
    period_days: Optional[int]
    total_users: int
    avg_ltv_score: float
    power_users: int
    power_users_percent: float
    regular_users: int
    regular_users_percent: float
    casual_users: int
    casual_users_percent: float


# Endpoints


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint (no authentication required)."""
    try:
        db_stats = db.get_database_stats()
        return {
            "status": "healthy",
            "database": "connected",
            "last_snapshot": db_stats.get('last_snapshot_timestamp')
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "error",
            "last_snapshot": None
        }


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint (no authentication required).

    Exposes TeamSpeak statistics in Prometheus format for monitoring and alerting.
    Configure your Prometheus instance to scrape this endpoint.

    Example Prometheus scrape config:
    ```yaml
    scrape_configs:
      - job_name: 'teamspeak-stats'
        static_configs:
          - targets: ['localhost:8000']
    ```
    """
    try:
        from prometheus_client import CONTENT_TYPE_LATEST
        metrics_data = metrics_collector.get_metrics()
        return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/summary", response_model=Summary)
async def get_summary(
    days: Optional[int] = Query(7, description="Number of days to analyze (null = all time)"),
    api_key: str = Depends(verify_api_key)
):
    """Get overall statistics summary."""
    try:
        stats = stats_calc
        return stats.get_summary(days=days)
    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/top-users", response_model=list[UserStat])
async def get_top_users(
    days: Optional[int] = Query(7, description="Number of days to analyze"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of users"),
    api_key: str = Depends(verify_api_key)
):
    """Get top users by online time."""
    try:
        stats = stats_calc
        users = stats.get_top_users(days=days, limit=limit)
        return [
            {
                'client_uid': u['client_uid'],
                'nickname': u['nickname'],
                'online_hours': u['online_hours'],
                'first_seen': u['first_seen'],
                'last_seen': u['last_seen']
            }
            for u in users
        ]
    except Exception as e:
        logger.error(f"Error getting top users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/user/{client_uid}")
async def get_user_stats(
    client_uid: str,
    days: Optional[int] = Query(30, description="Number of days to analyze"),
    api_key: str = Depends(verify_api_key)
):
    """Get detailed statistics for a specific user."""
    try:
        stats = stats_calc
        user = stats.get_user_stats(client_uid, days=days)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/hourly-heatmap", response_model=list[HourlyHeatmap])
async def get_hourly_heatmap(
    days: Optional[int] = Query(7, description="Number of days to analyze"),
    api_key: str = Depends(verify_api_key)
):
    """Get average user count by hour of day."""
    try:
        stats = stats_calc
        return stats.get_hourly_heatmap(days=days)
    except Exception as e:
        logger.error(f"Error getting hourly heatmap: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/daily-activity", response_model=list[DailyActivity])
async def get_daily_activity(
    days: Optional[int] = Query(30, description="Number of days to analyze"),
    api_key: str = Depends(verify_api_key)
):
    """Get average user count by day of week."""
    try:
        stats = stats_calc
        return stats.get_daily_activity(days=days)
    except Exception as e:
        logger.error(f"Error getting daily activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/top-idle", response_model=list[IdleUser])
async def get_top_idle(
    days: Optional[int] = Query(7, description="Number of days to analyze"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of users"),
    api_key: str = Depends(verify_api_key)
):
    """Get users with highest average idle time."""
    try:
        stats = stats_calc
        return stats.get_top_idle_users(days=days, limit=limit)
    except Exception as e:
        logger.error(f"Error getting top idle users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/peak-times", response_model=list[PeakTime])
async def get_peak_times(
    days: Optional[int] = Query(7, description="Number of days to analyze"),
    limit: int = Query(10, ge=1, le=100, description="Number of peak times"),
    api_key: str = Depends(verify_api_key)
):
    """Get times when server had most users online."""
    try:
        stats = stats_calc
        return stats.get_peak_times(days=days, limit=limit)
    except Exception as e:
        logger.error(f"Error getting peak times: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/channels", response_model=list[ChannelStat])
async def get_channel_stats(
    days: Optional[int] = Query(7, description="Number of days to analyze"),
    api_key: str = Depends(verify_api_key)
):
    """Get channel popularity statistics."""
    try:
        stats = stats_calc
        return stats.get_channel_stats(days=days)
    except Exception as e:
        logger.error(f"Error getting channel stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/growth", response_model=GrowthMetrics)
async def get_growth(
    days: int = Query(7, ge=1, description="Number of days to analyze"),
    api_key: str = Depends(verify_api_key)
):
    """Get growth metrics (new vs returning users)."""
    try:
        stats = stats_calc
        return stats.get_growth_metrics(days=days)
    except Exception as e:
        logger.error(f"Error getting growth metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/online-now", response_model=list[OnlineUser])
async def get_online_now(
    api_key: str = Depends(verify_api_key)
):
    """Get currently online users (from last snapshot)."""
    try:
        stats = stats_calc
        return stats.get_online_now()
    except Exception as e:
        logger.error(f"Error getting online users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/database", response_model=DatabaseStats)
async def get_database_stats(
    api_key: str = Depends(verify_api_key)
):
    """Get database statistics."""
    try:
        return db.get_database_stats()
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/away", response_model=AwayStats)
async def get_away_stats(
    days: Optional[int] = Query(7, description="Number of days to analyze"),
    limit: int = Query(10, ge=1, le=100, description="Number of users to show"),
    api_key: str = Depends(verify_api_key)
):
    """Get AFK/Away status statistics."""
    try:
        stats = stats_calc
        return stats.get_away_stats(days=days, limit=limit)
    except Exception as e:
        logger.error(f"Error getting away stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/mute", response_model=MuteStats)
async def get_mute_stats(
    days: Optional[int] = Query(7, description="Number of days to analyze"),
    api_key: str = Depends(verify_api_key)
):
    """Get microphone/speaker mute and recording statistics."""
    try:
        stats = stats_calc
        return stats.get_mute_stats(days=days)
    except Exception as e:
        logger.error(f"Error getting mute stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/server-groups", response_model=list[ServerGroup])
async def get_server_groups(
    days: Optional[int] = Query(7, description="Number of days to analyze"),
    api_key: str = Depends(verify_api_key)
):
    """Get server group membership statistics."""
    try:
        stats = stats_calc
        return stats.get_server_group_stats(days=days)
    except Exception as e:
        logger.error(f"Error getting server group stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/channel-hoppers", response_model=list[ChannelHopper])
async def get_channel_hoppers(
    days: Optional[int] = Query(7, description="Number of days to analyze"),
    limit: int = Query(10, ge=1, le=100, description="Number of users to show"),
    api_key: str = Depends(verify_api_key)
):
    """Get users who switch channels most frequently."""
    try:
        stats = stats_calc
        return stats.get_channel_switches(days=days, limit=limit)
    except Exception as e:
        logger.error(f"Error getting channel hoppers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/connection-patterns", response_model=ConnectionPatterns)
async def get_connection_patterns(
    days: Optional[int] = Query(7, description="Number of days to analyze"),
    limit: int = Query(10, ge=1, le=100, description="Number of users to show"),
    api_key: str = Depends(verify_api_key)
):
    """Get connection/disconnection patterns and session statistics."""
    try:
        stats = stats_calc
        return stats.get_connection_patterns(days=days, limit=limit)
    except Exception as e:
        logger.error(f"Error getting connection patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/lifetime-value", response_model=list[LTVUser])
async def get_lifetime_value(
    days: Optional[int] = Query(None, description="Number of days to analyze (null = all time)"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of users"),
    api_key: str = Depends(verify_api_key)
):
    """
    Get User Lifetime Value (LTV) rankings.

    LTV score is calculated based on:
    - Online time (40% weight)
    - Activity consistency (30% weight)
    - Engagement/talking time (20% weight)
    - Channel diversity (10% weight)

    Users are categorized as:
    - Power User (80-100 score)
    - Regular User (50-79 score)
    - Casual User (0-49 score)
    """
    try:
        stats = stats_calc
        return stats.get_user_lifetime_value(days=days, limit=limit)
    except Exception as e:
        logger.error(f"Error getting LTV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/lifetime-value/summary", response_model=LTVSummary)
async def get_ltv_summary(
    days: Optional[int] = Query(None, description="Number of days to analyze (null = all time)"),
    api_key: str = Depends(verify_api_key)
):
    """Get User Lifetime Value distribution summary."""
    try:
        stats = stats_calc
        return stats.get_ltv_summary(days=days)
    except Exception as e:
        logger.error(f"Error getting LTV summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Run the API server."""
    logger.info("=" * 60)
    logger.info("TeamSpeak Activity Stats Bot - API Server")
    logger.info("=" * 60)
    logger.info(f"Host: {config.api.host}")
    logger.info(f"Port: {config.api.port}")
    logger.info(f"Docs: {'/docs' if config.api.docs_enabled else 'disabled'}")
    logger.info("=" * 60)

    uvicorn.run(
        app,
        host=config.api.host,
        port=config.api.port,
        log_level=config.logging.level.lower()
    )


if __name__ == "__main__":
    main()
