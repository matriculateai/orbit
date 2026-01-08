#!/bin/bash
# Senture Orbit - Build Script for Databricks Apps Deployment
#
# This script builds the application for deployment to Databricks Apps.
# It builds the frontend and prepares the backend for deployment.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Building Senture Orbit for Databricks Apps...${NC}"

# Set working directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "Project root: $(pwd)"

# Build frontend
echo -e "${YELLOW}Building frontend...${NC}"
cd frontend

# Install dependencies
echo "Installing frontend dependencies..."
npm ci --only=production

# Set production API URL (relative for same-origin deployment)
export REACT_APP_API_URL=""

# Build production assets
echo "Building production assets..."
npm run build

# Copy built assets to backend static directory
echo -e "${YELLOW}Copying frontend assets to backend...${NC}"
cd ..
rm -rf backend/static
mkdir -p backend/static
cp -r frontend/build/* backend/static/

echo -e "${GREEN}Frontend build complete!${NC}"

# Verify backend dependencies
echo -e "${YELLOW}Verifying backend dependencies...${NC}"
cd backend
pip install -q -r requirements.txt

echo -e "${GREEN}Build complete!${NC}"
echo ""
echo "To deploy to Databricks Apps:"
echo "  1. Create a new Databricks App in your workspace"
echo "  2. Upload this project directory"
echo "  3. Configure the app with the app.yaml file"
echo "  4. Set required environment variables (GENIE_SPACE_ID, ANTHROPIC_API_KEY)"
echo "  5. Deploy the app"
