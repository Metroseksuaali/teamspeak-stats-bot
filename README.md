# TeamSpeak 6 Activity Stats Bot

A production-ready Python bot for tracking and analyzing user activity on TeamSpeak 6 servers. Collect time-series data, generate insights, and monitor server usage patterns.

## Features

### 📊 **Comprehensive Statistics**
- **Top Users**: Track online time, first/last seen
- **Hourly Heatmap**: Discover peak activity hours
- **Daily Activity**: Analyze usage by day of week
- **Idle Time Tracking**: Identify AFK users
- **Channel Analytics**: Most popular channels
- **Growth Metrics**: New vs returning users
- **Real-time Monitoring**: Currently online users

### 🛠️ **Dual Interface**
- **CLI**: Beautiful terminal interface with rich formatting
- **REST API**: FastAPI-powered JSON endpoints with OpenAPI docs

### 🐳 **Production Ready**
- Docker & docker-compose support
- Graceful shutdown handling
- Exponential backoff retry logic
- Health checks & monitoring
- Configurable data retention
- SQLite database with future-proof schema

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
   git clone <your-repo-url>
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

### TeamSpeak 6 WebQuery Setup

1. **Enable WebQuery** on your TS6 server (usually enabled by default)
   - HTTP: Port 10080
   - HTTPS: Port 10443

2. **Generate API Key**:
   ```bash
   # Option A: Via SSH ServerQuery
   ssh serveradmin@your-server -p 10022
   # Then run:
   apikeyadd scope=manage

   # Option B: Via TS6 Server Web UI
   # Navigate to Server Settings → API Keys → Create New Key
   ```

3. **Copy API key** to `config.yaml`

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
  retention_days: null                        # null = keep forever, or set days

api:
  api_key: "SECRET_KEY"                       # Protect your stats!
  port: 8080
```

---

## CLI Commands

### User Statistics
```bash
# Top users by online time
python -m ts_activity_bot.cli top-users --days 7 --limit 10

# Detailed user profile
python -m ts_activity_bot.cli user-stats <client_uid> --days 30

# Top idle users
python -m ts_activity_bot.cli top-idle --days 7
```

### Server Analytics
```bash
# Hourly activity heatmap
python -m ts_activity_bot.cli hourly-heatmap --days 7

# Daily activity by day of week
python -m ts_activity_bot.cli daily-activity --days 30

# Peak times
python -m ts_activity_bot.cli peak-times --days 7

# Channel statistics
python -m ts_activity_bot.cli channel-stats --days 7
```

### Growth & Monitoring
```bash
# Growth metrics
python -m ts_activity_bot.cli growth --days 7

# Currently online users
python -m ts_activity_bot.cli online-now

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
| `GET /stats/summary?days=7` | Overall statistics summary |
| `GET /stats/top-users?days=7&limit=10` | Top users by online time |
| `GET /stats/user/{uid}?days=30` | Detailed user statistics |
| `GET /stats/hourly-heatmap?days=7` | Average users by hour |
| `GET /stats/daily-activity?days=30` | Average users by day of week |
| `GET /stats/top-idle?days=7&limit=10` | Users with highest idle time |
| `GET /stats/peak-times?days=7&limit=10` | Server peak times |
| `GET /stats/channels?days=7` | Channel popularity |
| `GET /stats/growth?days=7` | New vs returning users |
| `GET /stats/online-now` | Currently online users |
| `GET /stats/database` | Database statistics |

### API Documentation

When `api.docs_enabled: true` in config:
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

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
A: Partially. TS3 has WebQuery (3.12.0+) with similar API, but field names may differ. Minor code changes needed.

**Q: Can I use SSH ServerQuery instead of WebQuery?**
A: Not currently. This version focuses on WebQuery (HTTP/HTTPS). SSH support could be added.

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
