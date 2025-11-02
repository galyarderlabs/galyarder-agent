#!/bin/bash

# GalyarderAgent Landing - Quick Deploy Script
# Usage: ./deploy.sh [preview|prod]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Banner
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════╗"
echo "║   GalyarderAgent Landing - Deploy Script  ║"
echo "╚═══════════════════════════════════════════╝"
echo -e "${NC}"

# Check if Vercel CLI is installed
if ! command -v vercel &> /dev/null; then
    echo -e "${RED}✗ Vercel CLI is not installed${NC}"
    echo -e "${YELLOW}Installing Vercel CLI...${NC}"
    npm install -g vercel
fi

# Get deployment type from argument or prompt
DEPLOY_TYPE=${1:-}

if [ -z "$DEPLOY_TYPE" ]; then
    echo -e "${BLUE}Select deployment type:${NC}"
    echo "  1) Preview (development)"
    echo "  2) Production (agent.galyarderlabs.app)"
    read -p "Enter choice [1-2]: " choice

    case $choice in
        1) DEPLOY_TYPE="preview" ;;
        2) DEPLOY_TYPE="prod" ;;
        *) echo -e "${RED}✗ Invalid choice${NC}"; exit 1 ;;
    esac
fi

# Validate deployment type
if [[ "$DEPLOY_TYPE" != "preview" && "$DEPLOY_TYPE" != "prod" ]]; then
    echo -e "${RED}✗ Invalid deployment type: $DEPLOY_TYPE${NC}"
    echo "Usage: ./deploy.sh [preview|prod]"
    exit 1
fi

# Run pre-deployment checks
echo -e "\n${YELLOW}Running pre-deployment checks...${NC}"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    npm install
fi

# Run linter
echo -e "${YELLOW}Running linter...${NC}"
npm run lint || {
    echo -e "${RED}✗ Linting failed. Fix errors before deploying.${NC}"
    exit 1
}

# Test build
echo -e "${YELLOW}Testing production build...${NC}"
npm run build || {
    echo -e "${RED}✗ Build failed. Fix errors before deploying.${NC}"
    exit 1
}

echo -e "${GREEN}✓ Pre-deployment checks passed${NC}"

# Deploy
echo -e "\n${BLUE}Deploying to Vercel...${NC}"

if [ "$DEPLOY_TYPE" = "prod" ]; then
    echo -e "${YELLOW}Deploying to PRODUCTION: agent.galyarderlabs.app${NC}"
    read -p "Are you sure? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        echo -e "${YELLOW}Deployment cancelled${NC}"
        exit 0
    fi

    vercel --prod
else
    echo -e "${YELLOW}Deploying preview deployment...${NC}"
    vercel
fi

# Success message
echo -e "\n${GREEN}"
echo "╔═══════════════════════════════════════════╗"
echo "║         Deployment Successful! 🚀         ║"
echo "╚═══════════════════════════════════════════╝"
echo -e "${NC}"

if [ "$DEPLOY_TYPE" = "prod" ]; then
    echo -e "${GREEN}Production URL:${NC} https://agent.galyarderlabs.app"
    echo -e "\n${YELLOW}Next steps:${NC}"
    echo "  1. Test the production site"
    echo "  2. Verify OG image: https://developers.facebook.com/tools/debug/"
    echo "  3. Check analytics in Vercel Dashboard"
else
    echo -e "${YELLOW}Preview deployment created${NC}"
    echo "Check the URL provided by Vercel above"
fi

echo -e "\n${BLUE}Happy shipping! ✨${NC}"
