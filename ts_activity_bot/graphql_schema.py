"""
GraphQL schema for TS6 Activity Bot.

Provides GraphQL API for flexible querying of statistics.

Copyright (C) 2025 Metroseksuaali
Licensed under GNU AGPL v3.0 - see LICENSE file for details.
"""

from typing import List, Optional

import strawberry
from strawberry.fastapi import GraphQLRouter

from ts_activity_bot.config import get_config
from ts_activity_bot.stats import StatsCalculator


# Load config and initialize stats
config = get_config()
stats_calc = StatsCalculator(config.database.path, config.polling.interval_seconds)


# GraphQL Types

@strawberry.type
class User:
    """Basic user information"""
    client_uid: str
    nickname: str
    online_hours: float
    first_seen: int
    last_seen: int


@strawberry.type
class FavoriteChannel:
    """Favorite channel information"""
    channel_id: int
    channel_name: str
    visits: int


@strawberry.type
class UserDetailed:
    """Detailed user statistics"""
    client_uid: str
    nickname: str
    sample_count: int
    online_seconds: int
    online_hours: float
    first_seen: int
    last_seen: int
    avg_idle_ms: int
    favorite_channels: List[FavoriteChannel]


@strawberry.type
class Channel:
    """Channel statistics"""
    channel_id: int
    channel_name: str
    total_visits: int
    unique_users: int
    avg_idle_ms: int


@strawberry.type
class HourlyData:
    """Hourly activity data"""
    hour: int
    avg_clients: float
    sample_count: int


@strawberry.type
class DailyData:
    """Daily activity data"""
    day_of_week: int
    day_name: str
    avg_clients: float
    sample_count: int


@strawberry.type
class Summary:
    """Overall statistics summary"""
    period_days: Optional[int]
    total_snapshots: int
    avg_users_online: float
    max_users_online: int
    unique_users: int


@strawberry.type
class PeakTime:
    """Peak activity time"""
    timestamp: int
    datetime: str
    total_clients: int


@strawberry.type
class OnlineUser:
    """Currently online user"""
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
    connected_time: Optional[int]
    connected_hours: float


@strawberry.type
class LTVUser:
    """User Lifetime Value information"""
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


@strawberry.type
class LTVSummary:
    """User Lifetime Value distribution summary"""
    period_days: Optional[int]
    total_users: int
    avg_ltv_score: float
    power_users: int
    power_users_percent: float
    regular_users: int
    regular_users_percent: float
    casual_users: int
    casual_users_percent: float


@strawberry.type
class GrowthMetrics:
    """User growth metrics"""
    period_days: int
    total_unique_users: int
    new_users: int
    returning_users: int
    new_user_percentage: float


# GraphQL Queries

@strawberry.type
class Query:
    """Root query type"""

    @strawberry.field
    def top_users(
        self,
        days: Optional[int] = 7,
        limit: int = 10
    ) -> List[User]:
        """Get top users by online time"""
        users = stats_calc.get_top_users(days=days, limit=limit)
        return [
            User(
                client_uid=u['client_uid'],
                nickname=u['nickname'],
                online_hours=u['online_hours'],
                first_seen=u['first_seen'],
                last_seen=u['last_seen']
            )
            for u in users
        ]

    @strawberry.field
    def user_stats(
        self,
        client_uid: str,
        days: Optional[int] = 30
    ) -> Optional[UserDetailed]:
        """Get detailed statistics for a specific user"""
        user = stats_calc.get_user_stats(client_uid, days=days)
        if not user:
            return None

        return UserDetailed(
            client_uid=user['client_uid'],
            nickname=user['nickname'],
            sample_count=user['sample_count'],
            online_seconds=user['online_seconds'],
            online_hours=user['online_hours'],
            first_seen=user['first_seen'],
            last_seen=user['last_seen'],
            avg_idle_ms=user['avg_idle_ms'],
            favorite_channels=[
                FavoriteChannel(
                    channel_id=ch['channel_id'],
                    channel_name=ch['channel_name'],
                    visits=ch['visits']
                )
                for ch in user['favorite_channels']
            ]
        )

    @strawberry.field
    def channels(self, days: Optional[int] = 7) -> List[Channel]:
        """Get channel statistics"""
        channels = stats_calc.get_channel_stats(days=days)
        return [
            Channel(
                channel_id=ch['channel_id'],
                channel_name=ch['channel_name'],
                total_visits=ch['total_visits'],
                unique_users=ch['unique_users'],
                avg_idle_ms=ch['avg_idle_ms']
            )
            for ch in channels
        ]

    @strawberry.field
    def hourly_heatmap(self, days: Optional[int] = 7) -> List[HourlyData]:
        """Get hourly activity heatmap"""
        data = stats_calc.get_hourly_heatmap(days=days)
        return [
            HourlyData(
                hour=h['hour'],
                avg_clients=h['avg_clients'],
                sample_count=h['sample_count']
            )
            for h in data
        ]

    @strawberry.field
    def daily_activity(self, days: Optional[int] = 30) -> List[DailyData]:
        """Get daily activity by day of week"""
        data = stats_calc.get_daily_activity(days=days)
        return [
            DailyData(
                day_of_week=d['day_of_week'],
                day_name=d['day_name'],
                avg_clients=d['avg_clients'],
                sample_count=d['sample_count']
            )
            for d in data
        ]

    @strawberry.field
    def summary(self, days: Optional[int] = 7) -> Summary:
        """Get overall statistics summary"""
        data = stats_calc.get_summary(days=days)
        return Summary(
            period_days=data['period_days'],
            total_snapshots=data['total_snapshots'],
            avg_users_online=data['avg_users_online'],
            max_users_online=data['max_users_online'],
            unique_users=data['unique_users']
        )

    @strawberry.field
    def peak_times(
        self,
        days: Optional[int] = 7,
        limit: int = 10
    ) -> List[PeakTime]:
        """Get peak activity times"""
        peaks = stats_calc.get_peak_times(days=days, limit=limit)
        return [
            PeakTime(
                timestamp=p['timestamp'],
                datetime=p['datetime'],
                total_clients=p['total_clients']
            )
            for p in peaks
        ]

    @strawberry.field
    def online_now(self) -> List[OnlineUser]:
        """Get currently online users"""
        users = stats_calc.get_online_now()
        return [
            OnlineUser(
                client_uid=u['client_uid'],
                nickname=u['nickname'],
                channel_id=u['channel_id'],
                channel_name=u['channel_name'],
                idle_ms=u['idle_ms'],
                idle_minutes=u['idle_minutes'],
                is_away=u['is_away'],
                away_message=u['away_message'],
                is_talking=u['is_talking'],
                input_muted=u['input_muted'],
                output_muted=u['output_muted'],
                is_recording=u['is_recording'],
                connected_time=u['connected_time'],
                connected_hours=u['connected_hours']
            )
            for u in users
        ]

    @strawberry.field
    def lifetime_value(
        self,
        days: Optional[int] = None,
        limit: int = 50
    ) -> List[LTVUser]:
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
        users = stats_calc.get_user_lifetime_value(days=days, limit=limit)
        return [
            LTVUser(
                client_uid=u['client_uid'],
                nickname=u['nickname'],
                ltv_score=u['ltv_score'],
                category=u['category'],
                category_label=u['category_label'],
                online_hours=u['online_hours'],
                days_active=u['days_active'],
                activity_frequency_percent=u['activity_frequency_percent'],
                channels_visited=u['channels_visited'],
                talking_percentage=u['talking_percentage'],
                avg_idle_minutes=u['avg_idle_minutes'],
                session_count=u['session_count'],
                avg_session_length_hours=u['avg_session_length_hours'],
                first_seen=u['first_seen'],
                last_seen=u['last_seen']
            )
            for u in users
        ]

    @strawberry.field
    def ltv_summary(self, days: Optional[int] = None) -> LTVSummary:
        """Get User Lifetime Value distribution summary"""
        data = stats_calc.get_ltv_summary(days=days)
        return LTVSummary(
            period_days=data['period_days'],
            total_users=data['total_users'],
            avg_ltv_score=data['avg_ltv_score'],
            power_users=data['power_users'],
            power_users_percent=data['power_users_percent'],
            regular_users=data['regular_users'],
            regular_users_percent=data['regular_users_percent'],
            casual_users=data['casual_users'],
            casual_users_percent=data['casual_users_percent']
        )

    @strawberry.field
    def growth_metrics(self, days: int = 7) -> GrowthMetrics:
        """Get user growth metrics"""
        data = stats_calc.get_growth_metrics(days=days)
        return GrowthMetrics(
            period_days=data['period_days'],
            total_unique_users=data['total_unique_users'],
            new_users=data['new_users'],
            returning_users=data['returning_users'],
            new_user_percentage=data['new_user_percentage']
        )


# Create GraphQL schema
schema = strawberry.Schema(query=Query)


def create_graphql_router() -> GraphQLRouter:
    """Create GraphQL router for FastAPI integration"""
    return GraphQLRouter(schema, path="/graphql")
