# Test Environment Setup

Quick guide to run TeamSpeak 3 server + stats bot locally for testing.

## Prerequisites

- Docker & Docker Compose installed
- Ports available: 8080, 9987, 10011, 10022, 10080, 10443, 30033

## Quick Start

### 1. Create test directories

```bash
mkdir -p test-data test-logs
```

### 2. Start TeamSpeak 3 server

```bash
docker-compose -f docker-compose.test.yml up -d teamspeak
```

### 3. Get TeamSpeak API key

```bash
docker-compose -f docker-compose.test.yml logs teamspeak | grep apikey
```

You should see something like:
```
apikey=BAB4hHBG-RsfazBrPGqXmHRZzIkespN5digCBgABCDEF1234567890
```

**Copy the entire API key!**

### 4. Update config.test.yaml

Edit `config.test.yaml` and replace:
```yaml
api_key: "REPLACE_WITH_ACTUAL_API_KEY_FROM_TS3_CONTAINER"
```

With your actual API key:
```yaml
api_key: "BAB4hHBG-RsfazBrPGqXmHRZzIkespN5digCBgABCDEF1234567890"
```

### 5. Start all services

```bash
docker-compose -f docker-compose.test.yml up -d
```

### 6. Watch logs

```bash
docker-compose -f docker-compose.test.yml logs -f
```

You should see:
- TeamSpeak server starting
- Poller connecting and polling successfully
- API server starting

### 7. Test the bot API

```bash
# Health check (no auth)
curl http://localhost:8080/health

# Get stats (requires auth)
curl -H "X-API-Key: test-bot-token-123" http://localhost:8080/stats/summary?days=7

# Database stats
curl -H "X-API-Key: test-bot-token-123" http://localhost:8080/stats/database
```

### 8. Connect to TeamSpeak server

- **Address**: `localhost`
- **Port**: `9987`
- **Password**: None (by default)

Join the server and move around channels to generate some activity data!

### 9. Use CLI commands

```bash
# Database stats
docker-compose -f docker-compose.test.yml exec poller python -m ts_activity_bot.cli db-stats

# Top users
docker-compose -f docker-compose.test.yml exec poller python -m ts_activity_bot.cli top-users

# Currently online
docker-compose -f docker-compose.test.yml exec poller python -m ts_activity_bot.cli online-now
```

## Cleanup

### Stop services

```bash
docker-compose -f docker-compose.test.yml down
```

### Remove all data (including TS3 server data)

```bash
docker-compose -f docker-compose.test.yml down -v
rm -rf test-data test-logs
```

## Troubleshooting

### Poller shows "401 Unauthorized"

- Check that you copied the correct API key from TeamSpeak logs
- Make sure you updated `config.test.yaml` with the real API key
- API key should be the long string starting with the container name

### TeamSpeak container won't start

```bash
# Check logs
docker-compose -f docker-compose.test.yml logs teamspeak

# Remove old volume and try again
docker-compose -f docker-compose.test.yml down -v
docker-compose -f docker-compose.test.yml up -d teamspeak
```

### No data in statistics

- Join the TeamSpeak server (localhost:9987)
- Wait at least 30 seconds (one poll interval)
- Move between channels to create activity
- Check poller logs for "Poll successful"

## Network Architecture

```
┌─────────────────────────────────────────────────────┐
│                 ts-test-network                      │
│                                                      │
│  ┌──────────────┐          ┌─────────────────┐     │
│  │  TeamSpeak 3 │ ◄─────── │  Stats Poller   │     │
│  │   Server     │  WebQuery│  (Port 10080)   │     │
│  │              │          │                 │     │
│  └──────────────┘          └─────────────────┘     │
│        │                           │                │
│        │                    SQLite Database         │
│        │                           │                │
│        │                   ┌─────────────────┐     │
│        │                   │   Stats API     │     │
│        │                   │  (Port 8080)    │     │
│        │                   └─────────────────┘     │
│        │                           │                │
└────────┼───────────────────────────┼────────────────┘
         │                           │
         │                           │
    localhost:9987             localhost:8080
  (TeamSpeak Client)         (REST API / Docs)
```

## Service URLs

- **TeamSpeak Server**: `localhost:9987` (voice client)
- **TS WebQuery**: `localhost:10080` (bot connection)
- **Bot REST API**: `http://localhost:8080`
- **API Docs**: `http://localhost:8080/docs`
- **GraphQL**: `http://localhost:8080/graphql`

## Files

- `docker-compose.test.yml` - Complete test environment
- `config.test.yaml` - Bot configuration for testing
- `test-data/` - SQLite database (gitignored)
- `test-logs/` - Log files (gitignored)

---

**Happy testing! 🧪**
