# TeamSpeak Activity Stats Bot

A production-ready Python bot for tracking and analyzing user activity on **TeamSpeak 3** (3.13+) and **TeamSpeak 6** servers. Collect time-series data, generate insights, and monitor server usage patterns via WebQuery HTTP API.

> **✅ Works with both TeamSpeak 3 (3.13.0+) and TeamSpeak 6!**

## Features

### 📊 **Comprehensive Statistics**
- **Top Users**: Track online time, first/last seen
- **Hourly Heatmap**: Discover peak activity hours
- **Daily Activity**: Analyze usage by day of week
- **Idle Time Tracking**: Identify AFK users
- **Channel Analytics**: Most popular channels with **channel names**
- **Growth Metrics**: New vs returning users
- **Real-time Monitoring**: Currently online users
- **User Lifetime Value (LTV)**: Score and categorize users (Power/Regular/Casual) based on engagement
- **Away/Mute Statistics**: Track AFK status, mute patterns, and recording activity
- **Channel Hopping**: Identify users who frequently switch channels
- **Connection Patterns**: Analyze session frequency and duration

### 🛠️ **Triple Interface**
- **CLI**: Beautiful terminal interface with rich formatting (19 commands)
- **REST API**: FastAPI-powered JSON endpoints with OpenAPI docs (17 endpoints)
- **GraphQL API**: Flexible querying at `/graphql` with interactive playground

### 🐳 **Production Ready**
- Docker & docker-compose support
- Graceful shutdown handling
- Exponential backoff retry logic
- Health checks & monitoring
- Configurable data retention
- **Multi-database support**: SQLite (default) or PostgreSQL for large-scale deployments
- **Prometheus metrics endpoint** for monitoring and alerting
- Automatic schema migration (v3)
- Channel name caching for improved performance
- User aggregates for faster historical queries

### 🔒 **Security**
- API key authentication
- SSL/TLS support (with self-signed cert option)
- Read-only API database access
- Configurable query client filtering

---

## Quick Start

### Option 1: Docker (Recommended)

1. **Clone and configure**:
   ```bash
   git clone https://github.com/Metroseksuaali/teamspeak6-activity
   cd teamspeak6-activity
   cp config.example.yaml config.yaml
   ```

2. **Edit `config.yaml`**:
   ```yaml
   teamspeak:
     base_url: "https://your-ts-server.com:10443"
     api_key: "YOUR_TEAMSPEAK_API_KEY"

   api:
     api_key: "YOUR_SECRET_API_KEY"  # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. **Start services**:
   ```bash
   docker-compose up -d
   ```

4. **View logs**:
   ```bash
   docker-compose logs -f
   ```

5. **Access API**:
   ```bash
   curl -H "X-API-Key: YOUR_SECRET_API_KEY" http://localhost:8080/stats/summary?days=7
   ```

6. **Use CLI**:
   ```bash
   docker-compose exec poller python -m ts_activity_bot.cli top-users --days 7
   ```

---

### Option 2: Manual Installation

1. **Requirements**:
   - Python 3.11+
   - pip

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure**:
   ```bash
   cp config.example.yaml config.yaml
   # Edit config.yaml with your settings
   ```

4. **Run poller**:
   ```bash
   python -m ts_activity_bot.poller
   ```

5. **Run API** (in separate terminal):
   ```bash
   python -m ts_activity_bot.api
   ```

6. **Use CLI**:
   ```bash
   python -m ts_activity_bot.cli top-users --days 7
   ```

---

## Configuration

### TeamSpeak WebQuery Setup

This bot works with both **TeamSpeak 3 (3.13.0+)** and **TeamSpeak 6** via the WebQuery HTTP API.

#### 1. **Verify WebQuery is Enabled**

WebQuery is usually enabled by default on both TS3 and TS6:
- **HTTP**: Port `10080`
- **HTTPS**: Port `10443`

#### 2. **Generate API Key**

**For TeamSpeak 3 (3.13.0+):**
```bash
# Option A: Via SSH ServerQuery (port 10022)
ssh serveradmin@your-server.com -p 10022
# After connecting, run:
use sid=1
apikeyadd scope=manage
# Copy the generated API key (long alphanumeric string)

# Option B: Via Raw ServerQuery (telnet, port 10011)
telnet your-server.com 10011
login serveradmin YOUR_PASSWORD
use sid=1
apikeyadd scope=manage
quit
```

**For TeamSpeak 6:**
```bash
# Via SSH ServerQuery
ssh serveradmin@your-server.com -p 10022
use sid=1
apikeyadd scope=manage

# Or use TS6 Web Admin Panel (if available)
```

**Important:** The API key is a long string like `BAB4hHBG-Rsfa...`, **NOT** a simple password!

#### 3. **Update `config.yaml`**

```yaml
teamspeak:
  base_url: "http://your-server.com:10080"  # Use your server address
  api_key: "PASTE_YOUR_LONG_API_KEY_HERE"   # From step 2
  virtual_server_id: 1                       # Usually 1
```

### Configuration Options

See `config.example.yaml` for all options with detailed comments. Key settings:

```yaml
teamspeak:
  base_url: "https://your-server.com:10443"  # Your TS6 server
  api_key: "YOUR_API_KEY"                     # WebQuery API key
  verify_ssl: true                            # false for self-signed certs

polling:
  interval_seconds: 30                        # Poll every 30 seconds

database:
  backend: sqlite                             # sqlite or postgresql
  path: ./data/ts_activity.sqlite             # SQLite database path
  # connection_string: postgresql://user:pass@host:5432/dbname  # For PostgreSQL
  retention_days: null                        # null = keep forever, or set days

api:
  api_key: "SECRET_KEY"                       # Protect your stats!
  port: 8080
```

#### Database Backends

**SQLite** (default) - Simple, file-based, perfect for most deployments:
```yaml
database:
  backend: sqlite
  path: ./data/ts_activity.sqlite
```

**PostgreSQL** - For large-scale data collection with high write throughput:
```yaml
database:
  backend: postgresql
  connection_string: postgresql://user:password@localhost:5432/teamspeak_stats
  path: ./data/ts_activity.sqlite  # Still needed for analytics queries
```

PostgreSQL configuration:
- Install psycopg2: `pip install psycopg2-binary`
- Supports connection pooling for better write performance
- Recommended for >100k snapshots or >10 snapshots/second

**Current limitation**: Analytics/stats queries currently require SQLite. When using PostgreSQL:
- ✅ Data collection (poller) writes to PostgreSQL
- ✅ Basic endpoints (`/health`, `/database`) use PostgreSQL
- ⚠️ Stats/analytics endpoints (`/stats/*`, GraphQL) read from SQLite
- For full PostgreSQL support, keep both databases or sync PostgreSQL → SQLite periodically

---

## CLI Commands

### User Statistics
```bash
# Top users by online time
python -m ts_activity_bot.cli top-users --days 7 --limit 10

# Detailed user profile (with favorite channel names)
python -m ts_activity_bot.cli user-stats <client_uid> --days 30

# Top idle users
python -m ts_activity_bot.cli top-idle --days 7

# User Lifetime Value rankings (NEW!)
python -m ts_activity_bot.cli lifetime-value --days 30 --limit 20

# LTV distribution summary (NEW!)
python -m ts_activity_bot.cli ltv-summary --days 30
```

### Server Analytics
```bash
# Hourly activity heatmap
python -m ts_activity_bot.cli hourly-heatmap --days 7

# Daily activity by day of week
python -m ts_activity_bot.cli daily-activity --days 30

# Peak times
python -m ts_activity_bot.cli peak-times --days 7

# Channel statistics (with channel names)
python -m ts_activity_bot.cli channel-stats --days 7
```

### Advanced Analytics
```bash
# Away/AFK statistics (NEW!)
python -m ts_activity_bot.cli away-stats --days 7

# Mute and recording statistics (NEW!)
python -m ts_activity_bot.cli mute-stats --days 7

# Server group membership (NEW!)
python -m ts_activity_bot.cli server-groups --days 7

# Channel hoppers (NEW!)
python -m ts_activity_bot.cli channel-hoppers --days 7 --limit 10

# Connection patterns (NEW!)
python -m ts_activity_bot.cli connection-patterns --days 7 --limit 10
```

### Growth & Monitoring
```bash
# Growth metrics
python -m ts_activity_bot.cli growth --days 7

# Currently online users (with channel names)
python -m ts_activity_bot.cli online-now --detailed

# Overall summary
python -m ts_activity_bot.cli summary --days 7

# Database statistics
python -m ts_activity_bot.cli db-stats
```

**All CLI commands support `--help` for more options.**

---

## API Endpoints

### Authentication

All endpoints (except `/health`) require API key authentication:

```bash
# Via header (recommended)
curl -H "X-API-Key: YOUR_API_KEY" http://localhost:8080/stats/summary

# Via query parameter
curl http://localhost:8080/stats/summary?api_key=YOUR_API_KEY
```

### Available Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check (no auth required) |
| `GET /metrics` | **Prometheus metrics (no auth required)** |
| `GET /stats/summary?days=7` | Overall statistics summary |
| `GET /stats/top-users?days=7&limit=10` | Top users by online time |
| `GET /stats/user/{uid}?days=30` | Detailed user statistics with favorite channels |
| `GET /stats/hourly-heatmap?days=7` | Average users by hour |
| `GET /stats/daily-activity?days=30` | Average users by day of week |
| `GET /stats/top-idle?days=7&limit=10` | Users with highest idle time |
| `GET /stats/peak-times?days=7&limit=10` | Server peak times |
| `GET /stats/channels?days=7` | **Channel popularity with names** |
| `GET /stats/growth?days=7` | New vs returning users |
| `GET /stats/online-now` | **Currently online users with channel names** |
| `GET /stats/database` | Database statistics |
| `GET /stats/away?days=7&limit=10` | Away/AFK statistics |
| `GET /stats/mute?days=7` | Mute and recording statistics |
| `GET /stats/server-groups?days=7` | Server group membership |
| `GET /stats/channel-hoppers?days=7&limit=10` | Users who switch channels frequently |
| `GET /stats/connection-patterns?days=7&limit=10` | Session patterns and reconnection frequency |
| **`GET /stats/lifetime-value?days=&limit=50`** | **User Lifetime Value (LTV) rankings** |
| **`GET /stats/lifetime-value/summary?days=`** | **LTV distribution summary** |

### GraphQL API

Access the GraphQL playground at: **http://localhost:8080/graphql**

**Example query:**
```graphql
query {
  topUsers(days: 7, limit: 5) {
    nickname
    onlineHours
  }
  lifetimeValue(days: null, limit: 10) {
    nickname
    ltvScore
    categoryLabel
    onlineHours
    daysActive
    channelsVisited
  }
  channels(days: 7) {
    channelName
    totalVisits
    uniqueUsers
  }
}
```

**All available queries:**
- `topUsers`, `userStats`, `channels`, `hourlyHeatmap`, `dailyActivity`
- `summary`, `peakTimes`, `onlineNow`, `growthMetrics`
- `lifetimeValue`, `ltvSummary`

### API Documentation

When `api.docs_enabled: true` in config:
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc
- **GraphQL Playground**: http://localhost:8080/graphql

---

## Prometheus Metrics

**Endpoint**: `GET /metrics` (no authentication required)

Export TeamSpeak statistics in Prometheus format for monitoring and alerting. The `/metrics` endpoint provides real-time metrics compatible with Prometheus scraping.

### Available Metrics

**User Metrics:**
- `ts_users_total` - Total unique users tracked
- `ts_users_online` - Currently online users
- `ts_users_online_active` - Online and active users (not idle/away)
- `ts_peak_users` - Peak concurrent users (7 days)
- `ts_avg_users_online` - Average users online (7 days)

**User Lifetime Value:**
- `ts_ltv_power_users` - Number of power users (LTV 80-100)
- `ts_ltv_regular_users` - Number of regular users (LTV 50-79)
- `ts_ltv_casual_users` - Number of casual users (LTV 0-49)
- `ts_ltv_avg_score` - Average LTV score across all users

**Channel Metrics:**
- `ts_channels_total` - Total number of channels
- `ts_channel_visits{channel_id, channel_name}` - Visits per channel
- `ts_channel_unique_users{channel_id, channel_name}` - Unique users per channel

**System Metrics:**
- `ts_database_size_bytes` - Database file size
- `ts_snapshots_total` - Total snapshots collected

### Prometheus Configuration

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'teamspeak-stats'
    static_configs:
      - targets: ['localhost:8080']
    scrape_interval: 60s
```

### Example Grafana Alerts

**Low activity alert:**
```yaml
- alert: TeamSpeakLowActivity
  expr: ts_users_online < 2
  for: 1h
  annotations:
    summary: "TeamSpeak server has low activity"
```

**Power user growth:**
```yaml
- alert: PowerUserGrowth
  expr: rate(ts_ltv_power_users[1d]) > 5
  annotations:
    summary: "Significant growth in power users"
```

---

## Docker Usage

### Services

- **`poller`**: Polls TeamSpeak server every N seconds, stores data
- **`api`**: FastAPI web server for querying statistics

### Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f poller
docker-compose logs -f api

# Restart services
docker-compose restart

# Stop services
docker-compose down

# Execute CLI inside container
docker-compose exec poller python -m ts_activity_bot.cli top-users

# Rebuild after code changes
docker-compose build
docker-compose up -d
```

### Volumes

Data is persisted in:
- `./config.yaml` - Configuration (read-only in containers)
- `./data/` - SQLite database
- `./logs/` - Log files (if file logging enabled)

---

## Database Schema

### Tables

**`snapshots`**: One row per poll
- `id`: Primary key
- `timestamp`: Unix epoch (UTC)
- `total_clients`: Client count

**`client_snapshots`**: Client presence per snapshot
- `snapshot_id`: FK to snapshots
- `client_uid`: Unique identifier
- `nickname`: Display name
- `channel_id`: Current channel
- `idle_ms`: Idle time (milliseconds)

**`metadata`**: Schema version and settings

### Querying Directly

```bash
sqlite3 data/ts_activity.sqlite

# Example queries
SELECT COUNT(*) FROM snapshots;
SELECT client_uid, nickname, COUNT(*) as visits FROM client_snapshots GROUP BY client_uid ORDER BY visits DESC LIMIT 10;
```

---

## Troubleshooting

### Connection Issues

**Problem**: "Failed to connect to TeamSpeak server"

**Solutions**:
1. Verify `base_url` is correct (check port: 10080 for HTTP, 10443 for HTTPS)
2. Check API key is valid: `curl -H "x-api-key: YOUR_KEY" https://your-server:10443/1/serverinfo`
3. If using self-signed cert, set `verify_ssl: false`
4. Check firewall allows outbound connections to TS server

### SSL Certificate Errors

**Problem**: "SSL: CERTIFICATE_VERIFY_FAILED"

**Solution**: Set `verify_ssl: false` in config (only for self-signed certs)

### Permission Errors

**Problem**: "Permission denied: /app/data/ts_activity.sqlite"

**Solution**: Ensure `./data` directory is writable:
```bash
chmod -R 755 ./data
```

### API Returns 401/403

**Problem**: "Unauthorized" or "Forbidden"

**Solution**: Check `X-API-Key` header matches `api.api_key` in config

### No Data in Statistics

**Problem**: CLI/API returns empty results

**Causes**:
1. Poller hasn't run yet (wait at least one poll interval)
2. No users were online during polling
3. Database file doesn't exist (check `data/` directory)

**Check**:
```bash
# Verify database exists and has data
docker-compose exec poller python -m ts_activity_bot.cli db-stats
```

---

## Production Deployment

### Recommendations

1. **Use HTTPS** for TeamSpeak WebQuery (port 10443)
2. **Generate strong API key**:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
3. **Enable log rotation** (configure in `config.yaml`)
4. **Set data retention** to prevent unbounded database growth
5. **Use reverse proxy** (nginx/traefik) for API with SSL
6. **Monitor health endpoints** with Prometheus/monitoring tools
7. **Backup database** regularly:
   ```bash
   # Backup
   cp data/ts_activity.sqlite backups/ts_activity_$(date +%Y%m%d).sqlite

   # Restore
   cp backups/ts_activity_20250115.sqlite data/ts_activity.sqlite
   ```

### Resource Requirements

- **CPU**: Minimal (<5% on modern hardware)
- **RAM**: ~50MB for poller, ~100MB for API
- **Disk**: ~1MB/day for typical server (varies with user count and poll interval)
- **Network**: ~1KB per poll (negligible)

### Systemd Service (Alternative to Docker)

```ini
# /etc/systemd/system/ts6-activity.service
[Unit]
Description=TeamSpeak 6 Activity Stats Bot
After=network.target

[Service]
Type=simple
User=ts6bot
WorkingDirectory=/opt/ts6-activity
ExecStart=/usr/bin/python3 -m ts_activity_bot.poller
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable ts6-activity
sudo systemctl start ts6-activity
```

---

## Development

### Project Structure

```
teamspeak6-activity/
├── ts_activity_bot/
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   ├── db.py              # Database operations
│   ├── query_client.py    # TS6 WebQuery client
│   ├── stats.py           # Statistics calculations
│   ├── poller.py          # Polling service
│   ├── cli.py             # CLI interface
│   └── api.py             # FastAPI server
├── data/                  # SQLite database (auto-created)
├── logs/                  # Log files
├── config.example.yaml    # Example configuration
├── requirements.txt       # Python dependencies
├── Dockerfile             # Docker image
├── docker-compose.yml     # Docker services
└── README.md              # This file
```

### Adding New Statistics

1. Add query function in `stats.py`:
   ```python
   def get_my_stat(self, days: Optional[int] = 7) -> List[Dict]:
       query = "SELECT ..."
       # ...
       return results
   ```

2. Add CLI command in `cli.py`:
   ```python
   @cli.command()
   def my_stat(ctx, days):
       stats = ctx.obj['stats']
       results = stats.get_my_stat(days=days)
       # Display results
   ```

3. Add API endpoint in `api.py`:
   ```python
   @app.get("/stats/my-stat")
   async def get_my_stat(days: int = 7, api_key: str = Depends(verify_api_key)):
       return stats_calc.get_my_stat(days=days)
   ```

---

## FAQ

**Q: Does this work with TeamSpeak 3?**
A: **Yes!** Fully tested and working with TeamSpeak 3.13.0+. The WebQuery API is identical between TS3 (3.13+) and TS6. Just make sure you have WebQuery enabled (default on port 10080/10443) and create an API key via ServerQuery.

**Q: What's the difference between TS3 and TS6 for this bot?**
A: None! Both versions use the same WebQuery HTTP API. The bot works identically on both. The only difference is the server version number displayed in responses.

**Q: Can I use SSH ServerQuery instead of WebQuery?**
A: Not directly. This bot uses the WebQuery **HTTP API** (port 10080/10443). However, you use SSH ServerQuery (port 10022) or Raw ServerQuery (port 10011) to **create the API key** that the bot then uses for HTTP requests.

**Q: How much data will be stored?**
A: Depends on poll interval and user count. Example: 10 users, 30s polls = ~1MB/day. Use `retention_days` to auto-delete old data.

**Q: Can I run multiple pollers for redundancy?**
A: No, multiple pollers will create duplicate data. Run one poller, but you can run multiple API instances.

**Q: Is the API read-only?**
A: Yes, API has read-only database access. Only poller writes data.

**Q: Can I export data for analysis?**
A: Yes, SQLite database can be queried directly or export via API endpoints. Also supports tools like Grafana with SQLite plugins.

---

## License

This project is licensed under the **GNU Affero General Public License v3.0** (AGPL-3.0).

**What this means:**
- ✅ **Free to use and modify** - Anyone can use this bot for free
- ✅ **Open source forever** - If you modify and deploy (even as a web service), you must share your changes
- ✅ **Commercial use allowed** - But the code must remain open source
- ❌ **No closed-source versions** - You cannot create proprietary forks

See the [LICENSE](LICENSE) file for full details.

## 💝 Support the Project

If you find this bot useful and want to support its development:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/metroseksuaali)

Your support helps maintain and improve this project! All donations are appreciated but never required.

## Contributing

Contributions are welcome! Please feel free to:
- 🐛 Report bugs via [GitHub Issues](https://github.com/Metroseksuaali/teamspeak6-activity/issues)
- 💡 Suggest new features
- 🔧 Submit pull requests

All contributions will be licensed under AGPL-3.0.

## Support & Community

- **Issues**: [GitHub Issues](https://github.com/Metroseksuaali/teamspeak6-activity/issues)
- **TeamSpeak Community**: [community.teamspeak.com](https://community.teamspeak.com)
- **Documentation**: See `config.example.yaml` for detailed configuration options

---

## Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [httpx](https://www.python-httpx.org/) - HTTP client
- [Click](https://click.palletsprojects.com/) - CLI framework
- [Rich](https://rich.readthedocs.io/) - Terminal formatting
- [Pydantic](https://docs.pydantic.dev/) - Data validation

---

**Enjoy tracking your TeamSpeak 6 server activity! 📊🎮**
