#!/bin/bash
# Start the Chat Converter server
# Accessible via Tailscale by binding to 0.0.0.0

cd "$(dirname "$0")"

# Install Playwright browsers if needed
# Install Playwright browsers if needed
uv run python -m playwright install chromium 2>/dev/null || true

# Start server
echo "Starting Chat Converter on http://0.0.0.0:8080"
echo "Access via Tailscale at http://$(hostname):8080"
uv run uvicorn src.server:app --host 0.0.0.0 --port 8080
