#!/bin/bash
# Senture Orbit - Databricks Apps Startup Script
#
# This script is used to start the application in Databricks Apps environment.
# It handles both local development and production deployment.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Senture Orbit...${NC}"

# Detect environment
if [ -n "$DATABRICKS_RUNTIME_VERSION" ] || [ -n "$DB_IS_DRIVER" ] || [ -n "$DATABRICKS_APP_ID" ]; then
    echo -e "${GREEN}Detected Databricks Apps environment${NC}"
    export IS_DATABRICKS_APPS=true
else
    echo -e "${YELLOW}Running in local development mode${NC}"
    export IS_DATABRICKS_APPS=false
fi

# Set working directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "Working directory: $(pwd)"

# Check for backend directory
if [ -d "backend" ]; then
    cd backend
    echo "Changed to backend directory"
fi

# Install dependencies if needed (for local development)
if [ "$IS_DATABRICKS_APPS" = "false" ]; then
    if [ -f "requirements.txt" ]; then
        echo -e "${YELLOW}Installing Python dependencies...${NC}"
        pip install -q -r requirements.txt
    fi
fi

# Set default port
PORT=${PORT:-8000}
HOST=${HOST:-0.0.0.0}

echo -e "${GREEN}Starting server on ${HOST}:${PORT}${NC}"

# Start the FastAPI application
exec python -m uvicorn app.main:app --host "$HOST" --port "$PORT"
