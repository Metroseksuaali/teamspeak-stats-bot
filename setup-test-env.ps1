# TeamSpeak Stats Bot - Test Environment Setup Script (PowerShell)
# This script sets up a complete local test environment on Windows

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "TeamSpeak Stats Bot - Test Environment Setup (Windows)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Create directories
Write-Host "[1/6] Creating test directories..." -ForegroundColor Green
New-Item -ItemType Directory -Force -Path "test-data" | Out-Null
New-Item -ItemType Directory -Force -Path "test-logs" | Out-Null
Write-Host "✅ Directories created" -ForegroundColor Green
Write-Host ""

# Step 2: Check if config.test.yaml exists
if (-not (Test-Path "config.test.yaml")) {
    Write-Host "ERROR: config.test.yaml not found!" -ForegroundColor Red
    Write-Host "This file should have been created automatically."
    exit 1
}
Write-Host "[2/6] Config file found" -ForegroundColor Green
Write-Host ""

# Step 3: Start TeamSpeak server
Write-Host "[3/6] Starting TeamSpeak 3 server..." -ForegroundColor Green
docker compose -f docker-compose.test.yml up -d teamspeak
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to start TeamSpeak server" -ForegroundColor Red
    exit 1
}
Write-Host "✅ TeamSpeak server starting..." -ForegroundColor Green
Write-Host ""

# Step 4: Wait for TeamSpeak to be ready
Write-Host "[4/6] Waiting for TeamSpeak server to initialize (20 seconds)..." -ForegroundColor Green
Start-Sleep -Seconds 20
Write-Host ""

# Step 5: Get API key
Write-Host "[5/6] Retrieving TeamSpeak API key from logs..." -ForegroundColor Green
$logs = docker compose -f docker-compose.test.yml logs teamspeak 2>&1 | Out-String

# Try to extract API key (pattern: apikey=XXXXX)
$apiKeyMatch = [regex]::Match($logs, 'apikey=([^\s\r\n]+)')

if (-not $apiKeyMatch.Success) {
    Write-Host "ERROR: Could not find API key in TeamSpeak logs!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Manual steps:" -ForegroundColor Yellow
    Write-Host "1. Check TeamSpeak logs:" -ForegroundColor Yellow
    Write-Host "   docker compose -f docker-compose.test.yml logs teamspeak" -ForegroundColor White
    Write-Host ""
    Write-Host "2. Look for a line with 'apikey=...' like:" -ForegroundColor Yellow
    Write-Host "   apikey=BAB4hHBG-RsfazBrPGqXmHRZzIkespN5digCBg..." -ForegroundColor White
    Write-Host ""
    Write-Host "3. Copy the API key and run:" -ForegroundColor Yellow
    Write-Host "   " -NoNewline
    Write-Host '(Get-Content config.test.yaml) -replace ''api_key:.*'', ''api_key: "YOUR_API_KEY_HERE"'' | Set-Content config.test.yaml' -ForegroundColor White
    Write-Host ""
    Write-Host "4. Restart services:" -ForegroundColor Yellow
    Write-Host "   docker compose -f docker-compose.test.yml restart" -ForegroundColor White
    Write-Host ""
    exit 1
}

$apiKey = $apiKeyMatch.Groups[1].Value
Write-Host "API Key found: $($apiKey.Substring(0, [Math]::Min(30, $apiKey.Length)))..." -ForegroundColor Yellow
Write-Host ""

# Step 6: Update config.test.yaml with the API key
Write-Host "[6/6] Updating config.test.yaml with API key..." -ForegroundColor Green
$configContent = Get-Content "config.test.yaml" -Raw
$configContent = $configContent -replace 'api_key:.*', "api_key: `"$apiKey`""
$configContent | Set-Content "config.test.yaml" -NoNewline
Write-Host "✅ Configuration updated" -ForegroundColor Green
Write-Host ""

# Start all services
Write-Host "Starting all services..." -ForegroundColor Green
docker compose -f docker-compose.test.yml up -d
Write-Host ""

# Wait for services to be ready
Write-Host "Waiting for services to start (10 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10
Write-Host ""

# Show status
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "✅ Test environment is ready!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "TeamSpeak Server:" -ForegroundColor Cyan
Write-Host "  Voice: localhost:9987"
Write-Host "  WebQuery: http://localhost:10080"
Write-Host ""
Write-Host "Stats Bot:" -ForegroundColor Cyan
Write-Host "  API: http://localhost:8080"
Write-Host "  Docs: http://localhost:8080/docs"
Write-Host "  GraphQL: http://localhost:8080/graphql"
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "  # View logs"
Write-Host "  docker compose -f docker-compose.test.yml logs -f" -ForegroundColor White
Write-Host ""
Write-Host "  # Test API"
Write-Host "  Invoke-WebRequest -Uri 'http://localhost:8080/health' -Headers @{'X-API-Key'='test-bot-token-123'}" -ForegroundColor White
Write-Host ""
Write-Host "  # Database stats"
Write-Host "  docker compose -f docker-compose.test.yml exec poller python -m ts_activity_bot.cli db-stats" -ForegroundColor White
Write-Host ""
Write-Host "  # Stop environment"
Write-Host "  docker compose -f docker-compose.test.yml down" -ForegroundColor White
Write-Host ""
Write-Host "  # Clean up everything"
Write-Host "  docker compose -f docker-compose.test.yml down -v; Remove-Item -Recurse -Force test-data, test-logs" -ForegroundColor White
Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Connect TeamSpeak client to localhost:9987"
Write-Host "2. Move around channels to generate activity"
Write-Host "3. Wait 30 seconds for poller to collect data"
Write-Host "4. Check stats via API or CLI"
Write-Host ""
