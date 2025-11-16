#!/bin/bash

# TeamSpeak Stats Bot - Test Environment Setup Script
# This script sets up a complete local test environment

set -e  # Exit on error

echo "======================================================================"
echo "TeamSpeak Stats Bot - Test Environment Setup"
echo "======================================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Create directories
echo -e "${GREEN}[1/6]${NC} Creating test directories..."
mkdir -p test-data test-logs
echo "✅ Directories created"
echo ""

# Step 2: Check if config.test.yaml exists
if [ ! -f "config.test.yaml" ]; then
    echo -e "${RED}ERROR: config.test.yaml not found!${NC}"
    echo "This file should have been created automatically."
    exit 1
fi
echo -e "${GREEN}[2/6]${NC} Config file found"
echo ""

# Step 3: Start TeamSpeak server
echo -e "${GREEN}[3/6]${NC} Starting TeamSpeak 3 server..."
docker-compose -f docker-compose.test.yml up -d teamspeak
echo "✅ TeamSpeak server starting..."
echo ""

# Step 4: Wait for TeamSpeak to be ready
echo -e "${GREEN}[4/6]${NC} Waiting for TeamSpeak server to initialize (15 seconds)..."
sleep 15
echo ""

# Step 5: Get API key
echo -e "${GREEN}[5/6]${NC} Retrieving TeamSpeak API key..."
API_KEY=$(docker-compose -f docker-compose.test.yml logs teamspeak | grep -oP 'apikey=\K[^\s]+' | head -1)

if [ -z "$API_KEY" ]; then
    echo -e "${RED}ERROR: Could not find API key in TeamSpeak logs!${NC}"
    echo ""
    echo "Manual steps:"
    echo "1. Check TeamSpeak logs: docker-compose -f docker-compose.test.yml logs teamspeak"
    echo "2. Look for a line with 'apikey=...'"
    echo "3. Copy the API key and update config.test.yaml manually"
    echo ""
    exit 1
fi

echo -e "${YELLOW}API Key found:${NC} ${API_KEY:0:30}..."
echo ""

# Update config.test.yaml with the API key
echo -e "${GREEN}[6/6]${NC} Updating config.test.yaml with API key..."
sed -i.bak "s|api_key:.*|api_key: \"$API_KEY\"|" config.test.yaml
rm -f config.test.yaml.bak
echo "✅ Configuration updated"
echo ""

# Start all services
echo -e "${GREEN}Starting all services...${NC}"
docker-compose -f docker-compose.test.yml up -d
echo ""

# Wait for services to be ready
echo "Waiting for services to start (10 seconds)..."
sleep 10
echo ""

# Show status
echo "======================================================================"
echo -e "${GREEN}✅ Test environment is ready!${NC}"
echo "======================================================================"
echo ""
echo "TeamSpeak Server:"
echo "  Voice: localhost:9987"
echo "  WebQuery: http://localhost:10080"
echo ""
echo "Stats Bot:"
echo "  API: http://localhost:8080"
echo "  Docs: http://localhost:8080/docs"
echo "  GraphQL: http://localhost:8080/graphql"
echo ""
echo "Useful commands:"
echo "  # View logs"
echo "  docker-compose -f docker-compose.test.yml logs -f"
echo ""
echo "  # Test API"
echo "  curl -H 'X-API-Key: test-bot-token-123' http://localhost:8080/health"
echo ""
echo "  # Database stats"
echo "  docker-compose -f docker-compose.test.yml exec poller python -m ts_activity_bot.cli db-stats"
echo ""
echo "  # Stop environment"
echo "  docker-compose -f docker-compose.test.yml down"
echo ""
echo "  # Clean up everything"
echo "  docker-compose -f docker-compose.test.yml down -v && rm -rf test-data test-logs"
echo ""
echo "======================================================================"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Connect TeamSpeak client to localhost:9987"
echo "2. Move around channels to generate activity"
echo "3. Wait 30 seconds for poller to collect data"
echo "4. Check stats via API or CLI"
echo ""
