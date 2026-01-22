#!/bin/bash
# Deployment script for chat_converter
# This script pulls latest code, rebuilds containers, and verifies deployment

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DRY_RUN=false
PROJECT_DIR="/home/talha/curated_context_containers/docker/chat_converter"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --project-dir)
      PROJECT_DIR="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--dry-run] [--project-dir /path/to/project]"
      exit 1
      ;;
  esac
done

echo -e "${BLUE}======================================"
echo "Chat Converter Deployment Script"
echo "======================================${NC}"
echo ""

if [ "$DRY_RUN" = true ]; then
  echo -e "${YELLOW}🔍 DRY RUN MODE - No changes will be made${NC}"
  echo ""
fi

# Step 1: Navigate to project directory
echo -e "${BLUE}📂 Navigating to project directory...${NC}"
if [ ! -d "$PROJECT_DIR" ]; then
  echo -e "${RED}❌ Error: Project directory not found: $PROJECT_DIR${NC}"
  exit 1
fi

cd "$PROJECT_DIR" || exit 1
echo -e "${GREEN}✅ In directory: $(pwd)${NC}"
echo ""

# Step 2: Pull latest changes
echo -e "${BLUE}🔄 Pulling latest changes from GitHub...${NC}"
if [ "$DRY_RUN" = false ]; then
  git fetch origin
  BEFORE_SHA=$(git rev-parse HEAD)
  git reset --hard origin/main
  AFTER_SHA=$(git rev-parse HEAD)
  
  if [ "$BEFORE_SHA" = "$AFTER_SHA" ]; then
    echo -e "${YELLOW}⚠️  No new changes to deploy${NC}"
  else
    echo -e "${GREEN}✅ Updated from $BEFORE_SHA to $AFTER_SHA${NC}"
    git log --oneline "$BEFORE_SHA".."$AFTER_SHA"
  fi
else
  echo -e "${YELLOW}[DRY RUN] Would pull latest changes${NC}"
fi
echo ""

# Step 3: Rebuild Docker images
echo -e "${BLUE}🔨 Rebuilding Docker images...${NC}"
if [ "$DRY_RUN" = false ]; then
  docker-compose build --no-cache
  echo -e "${GREEN}✅ Images rebuilt successfully${NC}"
else
  echo -e "${YELLOW}[DRY RUN] Would rebuild Docker images${NC}"
fi
echo ""

# Step 4: Restart containers
echo -e "${BLUE}🔄 Restarting containers...${NC}"
if [ "$DRY_RUN" = false ]; then
  docker-compose down
  docker-compose up -d
  echo -e "${GREEN}✅ Containers restarted${NC}"
else
  echo -e "${YELLOW}[DRY RUN] Would restart containers${NC}"
fi
echo ""

# Step 5: Clean up old images
echo -e "${BLUE}🧹 Cleaning up old Docker images...${NC}"
if [ "$DRY_RUN" = false ]; then
  docker image prune -f
  echo -e "${GREEN}✅ Cleanup complete${NC}"
else
  echo -e "${YELLOW}[DRY RUN] Would clean up old images${NC}"
fi
echo ""

# Step 6: Verify deployment
echo -e "${BLUE}======================================"
echo "Verification"
echo "======================================${NC}"

if [ "$DRY_RUN" = false ]; then
  sleep 5  # Give containers time to start
  
  # Check if containers are running
  if docker ps | grep -q chat_converter; then
    echo -e "${GREEN}✅ Containers are running:${NC}"
    docker ps | grep chat_converter
  else
    echo -e "${RED}❌ Containers are not running!${NC}"
    echo "Recent logs:"
    docker-compose logs --tail=50
    exit 1
  fi
  echo ""
  
  # Test endpoints
  echo -e "${BLUE}Testing endpoints...${NC}"
  
  if curl -sf http://localhost:8080/api/chats > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Main API is responding (port 8080)${NC}"
  else
    echo -e "${YELLOW}⚠️  Main API not responding (port 8080)${NC}"
  fi
  
  if curl -sf http://localhost:8090/mcp > /dev/null 2>&1; then
    echo -e "${GREEN}✅ MCP server is responding (port 8090)${NC}"
  else
    echo -e "${YELLOW}⚠️  MCP server not responding (port 8090)${NC}"
  fi
else
  echo -e "${YELLOW}[DRY RUN] Would verify containers and test endpoints${NC}"
fi
echo ""

echo -e "${BLUE}======================================"
echo -e "${GREEN}🚀 Deployment completed successfully!${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo "Services available at:"
echo "  - Main API: http://192.168.0.102:8081"
echo "  - MCP Server: http://192.168.0.102:8090"
echo ""
