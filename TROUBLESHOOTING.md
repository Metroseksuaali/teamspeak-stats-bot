# Troubleshooting Guide

## 401 Unauthorized - Invalid API Key

If you see this error in poller logs:

```
HTTP error 401: {"status":{"code":5122,"extra_message":"invalid api key","message":"invalid apikey"}}
```

### Quick Diagnosis

Run this PowerShell command to test your API key directly:

```powershell
# Replace YOUR_API_KEY with your actual key from config.test.yaml
$apiKey = "YOUR_API_KEY_HERE"
$headers = @{"x-api-key" = $apiKey}
Invoke-WebRequest -Uri "http://localhost:10080/1/serverinfo" -Headers $headers
```

### Possible Causes & Solutions

#### 0. **TeamSpeak Query IP Allowlist Blocking Docker Network (MOST COMMON)**

**Symptom:** API key works from Windows host but bot gets 401 errors.

**Root Cause:** TeamSpeak WebQuery has an IP allowlist that by default only allows `127.0.0.1` and `::1`. When the bot runs in a Docker container, it connects from a different IP address (Docker bridge network, e.g., `172.20.0.x`), which gets blocked.

**Check TeamSpeak logs:**
```powershell
docker compose -f docker-compose.test.yml logs teamspeak | Select-String "query_ip_allowlist"
```

If you see:
```
updated query_ip_allowlist ips: 127.0.0.1/32, ::1/128,
```

This means only localhost is allowed.

**Solution:** Add the `TS3SERVER_QUERY_IP_ALLOWLIST` environment variable to allow Docker network access.

Edit `docker-compose.test.yml`:

```yaml
teamspeak:
  environment:
    - TS3SERVER_LICENSE=accept
    - TS3SERVER_QUERY_PROTOCOLS=raw,ssh,http
    # Allow WebQuery API access from Docker network (fixes 401 errors)
    - TS3SERVER_QUERY_IP_ALLOWLIST=0.0.0.0/0
```

**Then restart:**

```powershell
docker compose -f docker-compose.test.yml down
docker compose -f docker-compose.test.yml up -d
```

**Note for production:** Instead of `0.0.0.0/0` (allows all IPs), use your specific Docker network CIDR, e.g., `172.20.0.0/16`.

#### 1. **API Key Not Configured**

**Check:** Open `config.test.yaml` and look for:
```yaml
teamspeak:
  api_key: "REPLACE_WITH_ACTUAL_API_KEY_FROM_TS3_CONTAINER"
```

If you see the placeholder text above, you need to configure the real API key.

**Solution (PowerShell):**

```powershell
# Step 1: Get API key from TeamSpeak logs
docker compose -f docker-compose.test.yml logs teamspeak | Select-String "apikey="

# Step 2: You should see something like:
# apikey=BAB4hHBG-RsfazBrPGqXmHRZzIkespN5digCBgXXXXXX

# Step 3: Copy the entire key and update config.test.yaml
# Replace the api_key line with your actual key:
# api_key: "BAB4hHBG-RsfazBrPGqXmHRZzIkespN5digCBgXXXXXX"

# Step 4: Restart services
docker compose -f docker-compose.test.yml restart poller
```

**Or use the automated script:**

```powershell
.\setup-test-env.ps1
```

#### 2. **API Key Has Wrong Permissions**

TeamSpeak API keys have different scopes: `read`, `write`, `manage`.

**Check:** Your API key needs **`manage`** scope for full access.

**Solution:** Create a new API key with correct scope:

```bash
# Connect to TeamSpeak ServerQuery (SSH)
ssh serveradmin@localhost -p 10022

# Enter your serveradmin password (from TeamSpeak logs)

# Create API key with manage scope
use sid=1
apikeyadd scope=manage

# Copy the generated apikey= string
quit
```

Update `config.test.yaml` with the new API key and restart:

```powershell
docker compose -f docker-compose.test.yml restart poller
```

#### 3. **API Key Contains Invalid Characters**

**Check:** Make sure the API key in `config.test.yaml`:
- Has no extra spaces before/after
- Is wrapped in quotes: `"YOUR_KEY_HERE"`
- Has no line breaks inside the key

**Correct:**
```yaml
api_key: "BAB4hHBG-RsfazBrPGqXmHRZzIkespN5digCBgXXXXXX"
```

**Incorrect:**
```yaml
api_key: BAB4hHBG-RsfazBrPGqXmHRZzIkespN5digCBgXXXXXX  # Missing quotes
api_key: "BAB4hHBG-RsfazBrPGqXmHRZzIkespN5digCBg
         XXXXXXX"  # Line break inside key
api_key: " BAB4hHBG-RsfazBrPGqXmHRZzIkespN5digCBg "  # Extra spaces
```

#### 4. **API Key Expired**

API keys can have a lifetime limit (in days).

**Check:** Your API key might have expired.

**Solution:** Create a new API key:

```bash
# Via ServerQuery
apikeyadd scope=manage lifetime=365  # Valid for 1 year

# Or create a key with no expiration
apikeyadd scope=manage
```

#### 5. **TeamSpeak Container Generated Invalid Key**

Sometimes the TeamSpeak container doesn't generate an API key on first start.

**Check logs:**

```powershell
docker compose -f docker-compose.test.yml logs teamspeak | Select-String "apikey"
```

**If no apikey found:**

```powershell
# Stop everything
docker compose -f docker-compose.test.yml down -v

# Start fresh
docker compose -f docker-compose.test.yml up -d teamspeak

# Wait 20 seconds
Start-Sleep -Seconds 20

# Check logs again
docker compose -f docker-compose.test.yml logs teamspeak | Select-String "apikey"
```

#### 6. **Wrong TeamSpeak URL or Port**

**Check `config.test.yaml`:**

```yaml
teamspeak:
  base_url: "http://teamspeak:10080"  # Container name, not localhost
  # OR
  base_url: "http://localhost:10080"  # If running bot outside Docker
```

**For Docker Compose:** Use `http://teamspeak:10080` (container name)

**For local testing:** Use `http://localhost:10080`

### Verification Steps

After fixing the API key, verify it works:

**1. Test API key directly:**

```powershell
# Replace with your actual API key
$apiKey = "YOUR_ACTUAL_KEY"
$headers = @{"x-api-key" = $apiKey}

# Test serverinfo endpoint
Invoke-WebRequest -Uri "http://localhost:10080/1/serverinfo" -Headers $headers

# Should return 200 OK with server information
```

**2. Check poller logs:**

```powershell
docker compose -f docker-compose.test.yml logs -f poller
```

You should see:

```
INFO - Fetched X clients from TeamSpeak server
INFO - Poll successful, X clients online
```

**3. Check database:**

```powershell
docker compose -f docker-compose.test.yml exec poller python -m ts_activity_bot.cli db-stats
```

Should show increasing snapshot counts.

### Still Having Issues?

1. **Enable debug logging:**

   Edit `config.test.yaml`:
   ```yaml
   logging:
     level: "DEBUG"  # Changed from INFO
   ```

   Restart: `docker compose -f docker-compose.test.yml restart poller`

2. **Check TeamSpeak is accessible:**

   ```powershell
   # From Windows host
   Test-NetConnection -ComputerName localhost -Port 10080

   # Should show TcpTestSucceeded: True
   ```

3. **View full error trace:**

   ```powershell
   docker compose -f docker-compose.test.yml logs poller | Select-String "401" -Context 5
   ```

4. **Verify Docker network:**

   ```powershell
   docker compose -f docker-compose.test.yml exec poller ping -c 3 teamspeak

   # Should succeed (from inside container)
   ```

### Clean Slate (Nuclear Option)

If nothing works, start completely fresh:

```powershell
# Stop and remove everything
docker compose -f docker-compose.test.yml down -v
Remove-Item -Recurse -Force test-data, test-logs -ErrorAction SilentlyContinue

# Create fresh directories
New-Item -ItemType Directory -Force test-data, test-logs

# Start TeamSpeak only
docker compose -f docker-compose.test.yml up -d teamspeak

# Wait for startup
Start-Sleep -Seconds 20

# Get the API key
$logs = docker compose -f docker-compose.test.yml logs teamspeak | Out-String
$apiKey = [regex]::Match($logs, 'apikey=([^\s\r\n]+)').Groups[1].Value
Write-Host "API Key: $apiKey"

# Update config.test.yaml with the API key
(Get-Content config.test.yaml) -replace 'api_key:.*', "api_key: `"$apiKey`"" | Set-Content config.test.yaml

# Start everything
docker compose -f docker-compose.test.yml up -d

# Watch logs
docker compose -f docker-compose.test.yml logs -f
```

---

## Bot Shows 0 Clients Despite Users Being Connected

**Symptom:**
- Users are connected to TeamSpeak server
- Bot logs show `Fetched 0 clients from TeamSpeak server`
- Users might see "client is flooding" error in TeamSpeak

**Root Cause 1: Query Client Filtering**

By default, `include_query_clients: false` filters out clients where `client_type = 1` (query clients).

If TeamSpeak classifies you as a query client (which can happen due to flooding protection or if you connected via query interface), you'll be filtered out.

**Solution:**

Edit `config.test.yaml`:

```yaml
teamspeak:
  # Set to true for testing to see ALL clients
  include_query_clients: true
```

**Root Cause 2: Polling Too Aggressive (Flooding)**

If polling interval is too short (e.g., 30 seconds), TeamSpeak may trigger flood protection and:
- Temporarily ban the bot's queries
- Classify regular clients as query clients
- Show "client is flooding" errors

**Solution:**

Edit `config.test.yaml`:

```yaml
polling:
  # Increase from 30 to 60 seconds
  interval_seconds: 60
```

**Root Cause 3: Multiple Poller Instances**

Check if you have multiple poller containers running:

```powershell
docker compose -f docker-compose.test.yml ps
```

If you see multiple `ts3-stats-poller` containers, stop all and start fresh:

```powershell
docker compose -f docker-compose.test.yml down
docker compose -f docker-compose.test.yml up -d
```

**Root Cause 4: Connected to Wrong Port**

Make sure you connected to **voice port 9987**, not query ports:
- ✅ `localhost:9987` - Voice (correct)
- ❌ `localhost:10011` - Raw ServerQuery (wrong)
- ❌ `localhost:10022` - SSH ServerQuery (wrong)

**Verification:**

After making changes, restart and test:

```powershell
# Restart poller to reload config
docker compose -f docker-compose.test.yml restart poller

# Wait 60 seconds for next poll
Start-Sleep -Seconds 65

# Check logs
docker compose -f docker-compose.test.yml logs poller --tail 20

# Should now see: "Fetched X clients from TeamSpeak server" (X > 0)
```

**Test API directly:**

```powershell
$apiKey = "YOUR_API_KEY_HERE"
$headers = @{"x-api-key" = $apiKey}

# This should show ALL clients (including query clients if any)
Invoke-WebRequest -Uri "http://localhost:10080/1/clientlist?-uid=&-times=" -Headers $headers | Select-Object -ExpandProperty Content
```

Check the response for your client. Look for `client_type` field:
- `"client_type": 0` = Normal user (should be tracked)
- `"client_type": 1` = Query client (filtered out if `include_query_clients: false`)

---

## Other Common Issues

### Database Connection Errors

```
ERROR - Failed to initialize database
```

**Solution:**

```powershell
# Create data directory
New-Item -ItemType Directory -Force test-data

# Restart poller
docker compose -f docker-compose.test.yml restart poller
```

### Port Already in Use

```
Error starting userland proxy: listen tcp 0.0.0.0:8080: bind: address already in use
```

**Solution:**

```powershell
# Find what's using the port
Get-NetTCPConnection -LocalPort 8080 | Select-Object -Property OwningProcess
Get-Process -Id <PID>

# Kill the process or change port in docker-compose.test.yml
```

### API Returns 503 Service Unavailable

```json
{"detail": "Stats endpoints not available when using PostgreSQL backend"}
```

**Solution:** This is expected when `database.backend: postgresql` is configured. Change to `sqlite` in `config.test.yaml` for full stats support.

---

Need more help? Check the [README.md](README.md) or open an issue on GitHub.
