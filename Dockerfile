# TeamSpeak 6 Activity Stats Bot - Docker Image
# Multi-stage build for smaller final image

# Stage 1: Builder - Install dependencies
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime - Create final image
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies (curl for healthcheck)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY ts_activity_bot/ ./ts_activity_bot/

# Add Python packages to PATH
ENV PATH=/root/.local/bin:$PATH

# Create directories for data and logs
RUN mkdir -p /app/data /app/logs

# Set Python to run in unbuffered mode (better for Docker logs)
ENV PYTHONUNBUFFERED=1

# Default command (run poller)
# Override with docker-compose or docker run command
CMD ["python", "-m", "ts_activity_bot.poller"]

# Health check (checks if database file exists and is accessible)
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sqlite3; conn=sqlite3.connect('/app/data/ts_activity.sqlite'); conn.close()" || exit 1
