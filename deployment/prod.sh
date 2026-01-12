#!/bin/bash
# =============================================================================
# MyStock Production Deployment Script (GCP VM)
# =============================================================================
# Usage: sudo bash deployment/prod.sh
#
# This script:
# 1. Pulls latest code from git
# 2. Sets up/updates Python virtual environment
# 3. Runs database migrations
# 4. Installs/updates systemd service
# 5. Restarts the application

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_USER="mystock"
APP_DIR="/home/mystock/app"
VENV_DIR="$APP_DIR/venv"
SERVICE_NAME="mystock"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  MyStock Production Deployment${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root: sudo bash deployment/prod.sh${NC}"
    exit 1
fi

# Change to app directory
cd $APP_DIR || { echo -e "${RED}App directory not found: $APP_DIR${NC}"; exit 1; }

# -----------------------------------------------------------------------------
# 1. Pull latest changes
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[1/6] Pulling latest changes...${NC}"
sudo -u $APP_USER git pull origin main || {
    echo -e "${YELLOW}Git pull failed, continuing with existing code...${NC}"
}

# -----------------------------------------------------------------------------
# 2. Set up Python virtual environment
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[2/6] Setting up Python environment...${NC}"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    sudo -u $APP_USER python3 -m venv $VENV_DIR
fi

# Activate venv and install dependencies
sudo -u $APP_USER $VENV_DIR/bin/pip install --upgrade pip
sudo -u $APP_USER $VENV_DIR/bin/pip install -r requirements.txt

# -----------------------------------------------------------------------------
# 3. Create .env file if not exists
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[3/6] Checking environment configuration...${NC}"
if [ ! -f "$APP_DIR/.env" ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    if [ -f "$APP_DIR/.env.example" ]; then
        sudo -u $APP_USER cp $APP_DIR/.env.example $APP_DIR/.env
        echo -e "${RED}IMPORTANT: Edit $APP_DIR/.env and set your secrets!${NC}"
    else
        # Create minimal .env
        cat > $APP_DIR/.env << EOF
ENVIRONMENT=production
JWT_SECRET=$(openssl rand -hex 32)
SECRET_KEY=$(openssl rand -hex 32)
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
BACKUP_DIR=/home/mystock/app/backups
BACKUP_RETENTION_DAYS=7
EOF
        chown $APP_USER:$APP_USER $APP_DIR/.env
        chmod 600 $APP_DIR/.env
        echo -e "${GREEN}Generated .env with random secrets${NC}"
    fi
fi

# -----------------------------------------------------------------------------
# 4. Run database migrations
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[4/6] Running database migrations...${NC}"
sudo -u $APP_USER $VENV_DIR/bin/alembic upgrade head

# -----------------------------------------------------------------------------
# 5. Install/update systemd service
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[5/6] Installing systemd service...${NC}"
cp $APP_DIR/deployment/mystock.service /etc/systemd/system/mystock.service
systemctl daemon-reload
systemctl enable $SERVICE_NAME

# -----------------------------------------------------------------------------
# 6. Restart the application
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[6/6] Restarting application...${NC}"
systemctl restart $SERVICE_NAME

# Wait a moment for the app to start
sleep 3

# Check service status
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}  Deployment Successful!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "Service status: ${GREEN}running${NC}"
    echo ""
    echo -e "Useful commands:"
    echo -e "  View logs:     ${YELLOW}sudo journalctl -u $SERVICE_NAME -f${NC}"
    echo -e "  Restart:       ${YELLOW}sudo systemctl restart $SERVICE_NAME${NC}"
    echo -e "  Stop:          ${YELLOW}sudo systemctl stop $SERVICE_NAME${NC}"
    echo -e "  Status:        ${YELLOW}sudo systemctl status $SERVICE_NAME${NC}"
    echo ""
    
    # Test the endpoint
    echo -e "Testing API endpoint..."
    if curl -s http://127.0.0.1:8000/demo | grep -q "Hello"; then
        echo -e "API response: ${GREEN}OK${NC}"
    else
        echo -e "API response: ${YELLOW}Check logs if issues${NC}"
    fi
else
    echo -e "\n${RED}========================================${NC}"
    echo -e "${RED}  Deployment Failed!${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo -e "Service failed to start. Check logs:"
    echo -e "  ${YELLOW}sudo journalctl -u $SERVICE_NAME -n 50${NC}"
    echo ""
    systemctl status $SERVICE_NAME --no-pager || true
    exit 1
fi
