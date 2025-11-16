# Connecting to External TeamSpeak Server

Guide for connecting the bot to a TeamSpeak server on a different machine/network.

## Deployment Scenarios

### Scenario 1: Bot and TeamSpeak on Same Docker Host ✅ EASIEST

```yaml
# docker-compose.yml
services:
  teamspeak:
    image: teamspeak:latest
    environment:
      - TS3SERVER_QUERY_IP_ALLOWLIST=172.16.0.0/12  # Docker bridge network
    networks:
      - my-network

  poller:
    build: .
    networks:
      - my-network  # Same network = containers can talk
    environment:
      - TS_BASE_URL=http://teamspeak:10080  # Use container name
```

**Result:** Bot connects internally via Docker network. No external ports needed.

---

### Scenario 2: Bot on Different Machine than TeamSpeak

**Example:**
- TeamSpeak server: `teamspeak.example.com` (public IP: `203.0.113.50`)
- Bot server: `bot.example.com` (public IP: `198.51.100.25`)

#### Step 1: Configure TeamSpeak Server

**Option A - Allow Specific Bot IP (Most Secure):**

```bash
# On TeamSpeak server machine
# Edit ts3server.ini or set environment variable
TS3SERVER_QUERY_IP_ALLOWLIST=198.51.100.25/32,127.0.0.1/32
```

**Option B - Allow Bot's Network CIDR:**

```bash
# If bot IP might change within a range
TS3SERVER_QUERY_IP_ALLOWLIST=198.51.100.0/24,127.0.0.1/32
```

**Option C - Allow All IPs (NOT RECOMMENDED for production):**

```bash
# Only use for testing/development
TS3SERVER_QUERY_IP_ALLOWLIST=0.0.0.0/0
```

**For Docker TeamSpeak:**

```yaml
# docker-compose.yml on TeamSpeak server
services:
  teamspeak:
    image: teamspeak:latest
    ports:
      - "9987:9987/udp"   # Voice
      - "10080:10080/tcp" # WebQuery HTTP (for bot)
      - "10443:10443/tcp" # WebQuery HTTPS (for bot, recommended)
    environment:
      - TS3SERVER_LICENSE=accept
      - TS3SERVER_QUERY_PROTOCOLS=raw,ssh,http
      # Allow bot's public IP
      - TS3SERVER_QUERY_IP_ALLOWLIST=198.51.100.25/32,127.0.0.1/32
```

**For Native TeamSpeak Installation:**

Edit `/opt/teamspeak3-server/ts3server.ini` (Linux) or `C:\TeamSpeak3-Server\ts3server.ini` (Windows):

```ini
query_ip_allowlist=198.51.100.25/32,127.0.0.1/32
```

Then restart TeamSpeak server:

```bash
# Linux
sudo systemctl restart teamspeak3-server

# Windows
net stop "TeamSpeak 3 Server"
net start "TeamSpeak 3 Server"
```

#### Step 2: Open Firewall on TeamSpeak Server

**Linux (UFW):**

```bash
# Allow WebQuery HTTP from bot's IP
sudo ufw allow from 198.51.100.25 to any port 10080 proto tcp

# OR allow WebQuery HTTPS (recommended)
sudo ufw allow from 198.51.100.25 to any port 10443 proto tcp

# Verify
sudo ufw status
```

**Linux (firewalld):**

```bash
# Create rich rule for specific source IP
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="198.51.100.25/32" port port="10443" protocol="tcp" accept'
sudo firewall-cmd --reload
```

**Windows Firewall:**

```powershell
# Allow WebQuery HTTPS from bot's IP
New-NetFirewallRule -DisplayName "TeamSpeak WebQuery Bot" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 10443 `
  -RemoteAddress 198.51.100.25 `
  -Action Allow
```

**Cloud Provider (AWS, Azure, GCP):**

Add inbound rule in Security Group / Network Security Group:
- **Protocol:** TCP
- **Port:** 10443 (HTTPS) or 10080 (HTTP)
- **Source:** Bot's IP address (198.51.100.25/32)
- **Description:** TeamSpeak WebQuery API for Stats Bot

#### Step 3: Configure Bot

**config.yaml on bot server:**

```yaml
teamspeak:
  # Use HTTPS for external connections (recommended)
  base_url: "https://teamspeak.example.com:10443"

  # API key from TeamSpeak server (created with apikeyadd)
  api_key: "YOUR_TEAMSPEAK_API_KEY"

  # Set to false if using self-signed certificate
  verify_ssl: false

  # Or set to true if you have a valid certificate
  # verify_ssl: true

  virtual_server_id: 1
  timeout: 10
```

#### Step 4: Test Connection

From bot server, test that WebQuery is accessible:

```bash
# Test HTTP (if using port 10080)
curl -H "x-api-key: YOUR_API_KEY" http://teamspeak.example.com:10080/1/serverinfo

# Test HTTPS (if using port 10443)
curl -k -H "x-api-key: YOUR_API_KEY" https://teamspeak.example.com:10443/1/serverinfo

# Should return JSON with server info
# If you get connection refused → firewall blocking
# If you get 401 → API key issue or IP not in allowlist
# If you get 200 + data → working!
```

**PowerShell (Windows bot):**

```powershell
$apiKey = "YOUR_API_KEY"
$headers = @{"x-api-key" = $apiKey}

# Test connection
Invoke-WebRequest -Uri "https://teamspeak.example.com:10443/1/serverinfo" `
  -Headers $headers `
  -SkipCertificateCheck

# Should return 200 OK
```

---

### Scenario 3: Bot Behind NAT/Dynamic IP

If bot's IP address changes (home internet, dynamic IP):

**Option 1 - Use VPN/Tunnel (Recommended):**

Set up WireGuard/OpenVPN between bot and TeamSpeak server:
- Bot always connects from same VPN IP
- TeamSpeak allowlist: VPN subnet

**Option 2 - Use Reverse Proxy with Authentication:**

Set up nginx on TeamSpeak server to proxy WebQuery with additional auth.

**Option 3 - Allow Wider CIDR (Less Secure):**

```bash
# Allow bot's ISP IP range (e.g., home internet /24 block)
TS3SERVER_QUERY_IP_ALLOWLIST=203.0.113.0/24,127.0.0.1/32
```

**Option 4 - Dynamic DNS + IP Allowlist Update Script:**

Use a script to automatically update TeamSpeak allowlist when bot IP changes.

---

## Security Best Practices

### 1. Always Use HTTPS (Port 10443) for External Connections

```yaml
teamspeak:
  base_url: "https://teamspeak.example.com:10443"  # HTTPS
  verify_ssl: true  # Verify certificate
```

**Why?** API key is sent in plaintext in HTTP headers. HTTPS encrypts the connection.

### 2. Restrict IP Allowlist to Minimum

**Bad:**
```bash
TS3SERVER_QUERY_IP_ALLOWLIST=0.0.0.0/0  # Allows anyone!
```

**Good:**
```bash
# Only allow bot's specific IP
TS3SERVER_QUERY_IP_ALLOWLIST=198.51.100.25/32,127.0.0.1/32
```

### 3. Use API Keys with Appropriate Scope

```bash
# For read-only stats bot, use 'read' scope
apikeyadd scope=read lifetime=365

# For bot that needs to send messages, use 'write'
apikeyadd scope=write lifetime=365

# Only use 'manage' if absolutely necessary
apikeyadd scope=manage lifetime=365
```

### 4. Set API Key Expiration

```bash
# API key valid for 1 year
apikeyadd scope=read lifetime=365

# Check when keys expire
apikeyadd list
```

### 5. Don't Expose WebQuery to Public Internet

**If possible, use:**
- VPN between bot and TeamSpeak
- Internal network only
- SSH tunnel: `ssh -L 10443:localhost:10443 user@teamspeak-server`

**Never expose WebQuery without IP filtering!**

### 6. Monitor Failed Authentication Attempts

Check TeamSpeak logs regularly:

```bash
# Look for failed WebQuery auth attempts
grep "invalid apikey" /var/log/teamspeak3-server/*.log
```

---

## Why YaTQA Doesn't Use IP Allowlist

**YaTQA and similar tools use Raw/SSH ServerQuery (ports 10011/10022), NOT WebQuery HTTP API.**

Different protocols:

| Protocol | Port | IP Allowlist? | Used By |
|----------|------|---------------|---------|
| **Raw ServerQuery** | 10011 | ❌ No (uses login/password auth) | YaTQA, TS3AudioBot, etc. |
| **SSH ServerQuery** | 10022 | ❌ No (uses SSH key auth) | Advanced admin tools |
| **WebQuery HTTP** | 10080/10443 | ✅ **Yes** (uses IP allowlist + API key) | **This bot** |

**Key Difference:**

- **Raw/SSH ServerQuery:** Requires `login serveradmin PASSWORD` command after connecting
- **WebQuery HTTP:** Requires API key in `x-api-key` header AND IP must be in allowlist

This is why YaTQA works without IP allowlist configuration!

---

## Troubleshooting External Connections

### Test 1: Can Bot Reach TeamSpeak Server?

```bash
# From bot server
ping teamspeak.example.com

# Test if port is open
nc -zv teamspeak.example.com 10443
# or
telnet teamspeak.example.com 10443
```

**PowerShell:**

```powershell
Test-NetConnection -ComputerName teamspeak.example.com -Port 10443
# Should show TcpTestSucceeded: True
```

### Test 2: Is Bot's IP in Allowlist?

Check TeamSpeak server logs:

```bash
# Look for bot's IP in logs
grep "query_ip_allowlist" /var/log/teamspeak3-server/*.log

# Or check current allowlist
# Connect via SSH ServerQuery and run:
serverinfo | grep query_ip_allowlist
```

### Test 3: Is Firewall Blocking?

**On TeamSpeak server:**

```bash
# Check if port is listening
sudo netstat -tlnp | grep 10443

# Check firewall rules
sudo ufw status  # Ubuntu/Debian
# or
sudo firewall-cmd --list-all  # CentOS/RHEL
```

### Test 4: API Key Valid?

```bash
# Test with curl from bot server
curl -v -H "x-api-key: YOUR_KEY" https://teamspeak.example.com:10443/1/serverinfo

# Check response:
# - 401 → API key invalid or IP blocked
# - 200 → Success!
# - Connection refused → Firewall or service not running
```

---

## Example: Production Setup

**TeamSpeak Server (teamspeak.example.com):**

```yaml
# docker-compose.yml
services:
  teamspeak:
    image: teamspeak:latest
    restart: unless-stopped
    ports:
      - "9987:9987/udp"
      - "10443:10443/tcp"  # HTTPS WebQuery only
    environment:
      - TS3SERVER_LICENSE=accept
      - TS3SERVER_QUERY_PROTOCOLS=raw,ssh,http
      # Allow bot server IP only
      - TS3SERVER_QUERY_IP_ALLOWLIST=198.51.100.25/32,127.0.0.1/32
    volumes:
      - ts3_data:/var/ts3server/
      - ./certs:/etc/ssl/teamspeak:ro  # SSL certificates
```

**Bot Server (bot.example.com):**

```yaml
# config.yaml
teamspeak:
  base_url: "https://teamspeak.example.com:10443"
  api_key: "YOUR_LONG_API_KEY_FROM_TS3"
  verify_ssl: true  # Production certificate
  virtual_server_id: 1
  timeout: 10

database:
  backend: "postgresql"  # Production database
  connection_string: "postgresql://user:pass@localhost:5432/ts_stats"

api:
  enabled: true
  bot_token: "YOUR_SECURE_RANDOM_TOKEN"
  host: "0.0.0.0"
  port: 8080
```

**Firewall on TeamSpeak server:**

```bash
# Allow voice from anywhere
sudo ufw allow 9987/udp

# Allow WebQuery ONLY from bot server
sudo ufw allow from 198.51.100.25 to any port 10443 proto tcp

# Default deny
sudo ufw default deny incoming
sudo ufw enable
```

---

Need help? Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) or open an issue!
