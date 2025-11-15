"""
Command-line interface for TS6 Activity Bot.

Provides commands to query and display statistics.

Copyright (C) 2025 Metroseksuaali
Licensed under GNU AGPL v3.0 - see LICENSE file for details.
"""

import sys
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table

from ts_activity_bot.config import get_config
from ts_activity_bot.stats import StatsCalculator

console = Console()


def format_timestamp(ts: int) -> str:
    """Format Unix timestamp to readable string."""
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')


def format_duration(hours: float) -> str:
    """Format hours into human-readable duration."""
    if hours < 1:
        return f"{hours * 60:.0f}m"
    elif hours < 24:
        return f"{hours:.1f}h"
    else:
        days = hours / 24
        return f"{days:.1f}d"


@click.group()
@click.option('--config', default='config.yaml', help='Path to config file')
@click.pass_context
def cli(ctx, config):
    """TeamSpeak 6 Activity Stats Bot - CLI Interface"""
    try:
        cfg = get_config(config)
        stats = StatsCalculator(cfg.database.path, cfg.polling.interval_seconds)
        ctx.obj = {'config': cfg, 'stats': stats}
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--days', default=7, help='Number of days to analyze')
@click.option('--limit', default=10, help='Number of users to show')
@click.pass_context
def top_users(ctx, days, limit):
    """Show top users by online time."""
    stats = ctx.obj['stats']

    console.print(f"\n[bold]Top {limit} Users - Last {days} Days[/bold]\n")

    try:
        users = stats.get_top_users(days=days, limit=limit)

        if not users:
            console.print("[yellow]No data available[/yellow]")
            return

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("Nickname")
        table.add_column("Online Time", justify="right")
        table.add_column("First Seen", justify="right")
        table.add_column("Last Seen", justify="right")

        for i, user in enumerate(users, 1):
            table.add_row(
                str(i),
                user['nickname'],
                format_duration(user['online_hours']),
                format_timestamp(user['first_seen']),
                format_timestamp(user['last_seen'])
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument('client_uid')
@click.option('--days', default=30, help='Number of days to analyze')
@click.pass_context
def user_stats(ctx, client_uid, days):
    """Show detailed statistics for a specific user."""
    stats = ctx.obj['stats']

    try:
        user = stats.get_user_stats(client_uid, days=days)

        if not user:
            console.print(f"[yellow]No data found for user: {client_uid}[/yellow]")
            return

        console.print(f"\n[bold]User Statistics - {user['nickname']}[/bold]\n")

        # Basic stats
        console.print(f"Client UID: {user['client_uid']}")
        console.print(f"Online Time: {format_duration(user['online_hours'])}")
        console.print(f"First Seen: {format_timestamp(user['first_seen'])}")
        console.print(f"Last Seen: {format_timestamp(user['last_seen'])}")
        console.print(f"Avg Idle Time: {user['avg_idle_ms'] / 60000:.1f} minutes")

        # Favorite channels
        if user['favorite_channels']:
            console.print("\n[bold]Favorite Channels:[/bold]")
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("Channel ID", justify="right")
            table.add_column("Visits", justify="right")

            for ch in user['favorite_channels']:
                table.add_row(str(ch['channel_id']), str(ch['visits']))

            console.print(table)

        # Activity by day of week
        if user['activity_by_day_of_week']:
            console.print("\n[bold]Activity by Day of Week:[/bold]")
            days_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
            for dow, count in user['activity_by_day_of_week'].items():
                console.print(f"  {days_names[dow]}: {count} samples")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--days', default=7, help='Number of days to analyze')
@click.pass_context
def hourly_heatmap(ctx, days):
    """Show hourly activity heatmap."""
    stats = ctx.obj['stats']

    console.print(f"\n[bold]Hourly Activity Heatmap - Last {days} Days[/bold]\n")

    try:
        heatmap = stats.get_hourly_heatmap(days=days)

        if not heatmap:
            console.print("[yellow]No data available[/yellow]")
            return

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Hour", justify="right")
        table.add_column("Avg Users", justify="right")
        table.add_column("Activity Bar")

        max_users = max(h['avg_clients'] for h in heatmap) if heatmap else 1

        for h in heatmap:
            hour_str = f"{h['hour']:02d}:00"
            avg_users = h['avg_clients']
            bar_length = int((avg_users / max_users) * 30) if max_users > 0 else 0
            bar = "█" * bar_length

            table.add_row(hour_str, f"{avg_users:.1f}", bar)

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--days', default=30, help='Number of days to analyze')
@click.pass_context
def daily_activity(ctx, days):
    """Show activity by day of week."""
    stats = ctx.obj['stats']

    console.print(f"\n[bold]Daily Activity - Last {days} Days[/bold]\n")

    try:
        activity = stats.get_daily_activity(days=days)

        if not activity:
            console.print("[yellow]No data available[/yellow]")
            return

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Day", width=12)
        table.add_column("Avg Users", justify="right")
        table.add_column("Activity Bar")

        max_users = max(d['avg_clients'] for d in activity) if activity else 1

        for d in activity:
            avg_users = d['avg_clients']
            bar_length = int((avg_users / max_users) * 30) if max_users > 0 else 0
            bar = "█" * bar_length

            table.add_row(d['day_name'], f"{avg_users:.1f}", bar)

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--days', default=7, help='Number of days to analyze')
@click.option('--limit', default=10, help='Number of users to show')
@click.pass_context
def top_idle(ctx, days, limit):
    """Show top idle users (AFK champions)."""
    stats = ctx.obj['stats']

    console.print(f"\n[bold]Top {limit} Idle Users - Last {days} Days[/bold]\n")

    try:
        users = stats.get_top_idle_users(days=days, limit=limit)

        if not users:
            console.print("[yellow]No data available[/yellow]")
            return

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("Nickname")
        table.add_column("Avg Idle Time", justify="right")

        for i, user in enumerate(users, 1):
            table.add_row(
                str(i),
                user['nickname'],
                f"{user['avg_idle_minutes']:.1f} min"
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--days', default=7, help='Number of days to analyze')
@click.option('--limit', default=10, help='Number of peak times to show')
@click.pass_context
def peak_times(ctx, days, limit):
    """Show server peak times."""
    stats = ctx.obj['stats']

    console.print(f"\n[bold]Top {limit} Peak Times - Last {days} Days[/bold]\n")

    try:
        peaks = stats.get_peak_times(days=days, limit=limit)

        if not peaks:
            console.print("[yellow]No data available[/yellow]")
            return

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("DateTime")
        table.add_column("Users Online", justify="right")

        for i, peak in enumerate(peaks, 1):
            table.add_row(
                str(i),
                format_timestamp(peak['timestamp']),
                str(peak['total_clients'])
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--days', default=7, help='Number of days to analyze')
@click.pass_context
def channel_stats(ctx, days):
    """Show channel popularity statistics."""
    stats = ctx.obj['stats']

    console.print(f"\n[bold]Channel Statistics - Last {days} Days[/bold]\n")

    try:
        channels = stats.get_channel_stats(days=days)

        if not channels:
            console.print("[yellow]No data available[/yellow]")
            return

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Channel ID", justify="right")
        table.add_column("Total Visits", justify="right")
        table.add_column("Unique Users", justify="right")
        table.add_column("Avg Idle (min)", justify="right")

        for ch in channels[:20]:  # Limit to top 20
            table.add_row(
                str(ch['channel_id']),
                str(ch['total_visits']),
                str(ch['unique_users']),
                f"{ch['avg_idle_ms'] / 60000:.1f}"
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--days', default=7, help='Number of days to analyze')
@click.pass_context
def growth(ctx, days):
    """Show growth metrics (new vs returning users)."""
    stats = ctx.obj['stats']

    console.print(f"\n[bold]Growth Metrics - Last {days} Days[/bold]\n")

    try:
        metrics = stats.get_growth_metrics(days=days)

        console.print(f"Total Unique Users: {metrics['total_unique_users']}")
        console.print(f"New Users: {metrics['new_users']} ({metrics['new_user_percentage']:.1f}%)")
        console.print(f"Returning Users: {metrics['returning_users']}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.pass_context
def online_now(ctx):
    """Show currently online users."""
    stats = ctx.obj['stats']

    console.print("\n[bold]Currently Online Users[/bold]\n")

    try:
        users = stats.get_online_now()

        if not users:
            console.print("[yellow]No users online (or no data yet)[/yellow]")
            return

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Nickname")
        table.add_column("Channel", justify="right")
        table.add_column("Idle Time", justify="right")

        for user in users:
            table.add_row(
                user['nickname'],
                str(user['channel_id']),
                f"{user['idle_minutes']:.1f} min"
            )

        console.print(table)
        console.print(f"\n[dim]Snapshot time: {format_timestamp(users[0]['snapshot_time'])}[/dim]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--days', default=7, help='Number of days for summary')
@click.pass_context
def summary(ctx, days):
    """Show overall statistics summary."""
    stats = ctx.obj['stats']

    console.print(f"\n[bold]Statistics Summary - Last {days} Days[/bold]\n")

    try:
        summary = stats.get_summary(days=days)

        console.print(f"Total Snapshots: {summary['total_snapshots']}")
        console.print(f"Average Users Online: {summary['avg_users_online']:.1f}")
        console.print(f"Max Users Online: {summary['max_users_online']}")
        console.print(f"Unique Users: {summary['unique_users']}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.pass_context
def db_stats(ctx):
    """Show database statistics."""
    from ts_activity_bot.db import Database

    config = ctx.obj['config']
    db = Database(config.database.path)

    console.print("\n[bold]Database Statistics[/bold]\n")

    try:
        stats = db.get_database_stats()

        console.print(f"Database Size: {stats['db_size_mb']:.2f} MB")
        console.print(f"Total Snapshots: {stats['snapshot_count']}")
        console.print(f"Total Client Snapshots: {stats['client_snapshot_count']}")
        console.print(f"Unique Clients: {stats['unique_clients']}")

        if stats['first_snapshot_timestamp']:
            console.print(f"First Snapshot: {format_timestamp(stats['first_snapshot_timestamp'])}")
        if stats['last_snapshot_timestamp']:
            console.print(f"Last Snapshot: {format_timestamp(stats['last_snapshot_timestamp'])}")

        console.print(f"Schema Version: {stats['schema_version']}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    cli()
