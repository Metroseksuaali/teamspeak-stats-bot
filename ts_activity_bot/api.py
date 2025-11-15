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
from fastapi import Depends, FastAPI, HTTPException, Query, Security
from fastapi.security import APIKeyHeader, APIKeyQuery
from pydantic import BaseModel

from ts_activity_bot.config import get_config
from ts_activity_bot.db import Database
from ts_activity_bot.stats import StatsCalculator

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

# Initialize stats calculator
stats_calc = StatsCalculator(config.database.path, config.polling.interval_seconds)
db = Database(config.database.path)

# Initialize FastAPI
app = FastAPI(
    title="TeamSpeak 6 Activity Stats API",
    description="REST API for querying TeamSpeak 6 server activity statistics",
    version="1.0.0",
    docs_url="/docs" if config.api.docs_enabled else None,
    redoc_url="/redoc" if config.api.docs_enabled else None
)

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

    if api_key != config.api.api_key:
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
    idle_ms: Optional[int]
    idle_minutes: float


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


@app.get("/stats/summary", response_model=Summary)
async def get_summary(
    days: Optional[int] = Query(7, description="Number of days to analyze (null = all time)"),
    api_key: str = Depends(verify_api_key)
):
    """Get overall statistics summary."""
    try:
        return stats_calc.get_summary(days=days)
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
        users = stats_calc.get_top_users(days=days, limit=limit)
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
        user = stats_calc.get_user_stats(client_uid, days=days)
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
        return stats_calc.get_hourly_heatmap(days=days)
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
        return stats_calc.get_daily_activity(days=days)
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
        return stats_calc.get_top_idle_users(days=days, limit=limit)
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
        return stats_calc.get_peak_times(days=days, limit=limit)
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
        return stats_calc.get_channel_stats(days=days)
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
        return stats_calc.get_growth_metrics(days=days)
    except Exception as e:
        logger.error(f"Error getting growth metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/online-now", response_model=list[OnlineUser])
async def get_online_now(
    api_key: str = Depends(verify_api_key)
):
    """Get currently online users (from last snapshot)."""
    try:
        return stats_calc.get_online_now()
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


def main():
    """Run the API server."""
    logger.info("=" * 60)
    logger.info("TeamSpeak 6 Activity Stats Bot - API Server")
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
