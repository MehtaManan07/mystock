#!/bin/bash
# =============================================================================
# GCP VM Initial Setup Script
# =============================================================================
# Run this ONCE on a fresh GCP e2-micro VM (Debian/Ubuntu)
# Usage: sudo bash gcp_setup.sh YOUR_DOMAIN
#
# Example: sudo bash gcp_setup.sh mystock.example.com

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root: sudo bash gcp_setup.sh YOUR_DOMAIN${NC}"
    exit 1
fi

# Check domain argument
DOMAIN=${1:-}
if [ -z "$DOMAIN" ]; then
    echo -e "${RED}Usage: sudo bash gcp_setup.sh YOUR_DOMAIN${NC}"
    echo "Example: sudo bash gcp_setup.sh mystock.example.com"
    exit 1
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  MyStock GCP VM Setup${NC}"
echo -e "${GREEN}  Domain: $DOMAIN${NC}"
echo -e "${GREEN}========================================${NC}"

# -----------------------------------------------------------------------------
# 1. Update system packages
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[1/7] Updating system packages...${NC}"
apt-get update
apt-get upgrade -y

# -----------------------------------------------------------------------------
# 2. Install Python 3.11 and dependencies
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[2/7] Installing Python 3.11...${NC}"
apt-get install -y software-properties-common

# Check if we're on Debian or Ubuntu
if [ -f /etc/debian_version ]; then
    # For Debian, we might need to install from deadsnakes or use default python3
    apt-get install -y python3 python3-pip python3-venv python3-dev
else
    # For Ubuntu, add deadsnakes PPA for Python 3.11
    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update
    apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip
fi

# -----------------------------------------------------------------------------
# 3. Install Nginx
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[3/7] Installing Nginx...${NC}"
apt-get install -y nginx

# -----------------------------------------------------------------------------
# 4. Install Certbot for Let's Encrypt SSL
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[4/7] Installing Certbot...${NC}"
apt-get install -y certbot python3-certbot-nginx

# -----------------------------------------------------------------------------
# 5. Install other useful tools
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[5/7] Installing additional tools...${NC}"
apt-get install -y git sqlite3 curl

# -----------------------------------------------------------------------------
# 6. Create app user and directory structure
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[6/7] Creating app user and directories...${NC}"

# Create app user if not exists
if ! id "mystock" &>/dev/null; then
    useradd --system --create-home --shell /bin/bash mystock
fi

# Create app directories
APP_DIR="/home/mystock/app"
mkdir -p $APP_DIR
mkdir -p $APP_DIR/data
mkdir -p $APP_DIR/backups
chown -R mystock:mystock /home/mystock

# -----------------------------------------------------------------------------
# 7. Configure Nginx
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[7/7] Configuring Nginx...${NC}"

# Create Nginx config
cat > /etc/nginx/sites-available/mystock << EOF
# MyStock Nginx Configuration
# Domain: $DOMAIN

server {
    listen 80;
    server_name $DOMAIN;

    # Redirect HTTP to HTTPS (after SSL is configured)
    # Uncomment after running certbot:
    # return 301 https://\$server_name\$request_uri;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        proxy_read_timeout 86400;
    }
}
EOF

# Enable the site
ln -sf /etc/nginx/sites-available/mystock /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test Nginx config
nginx -t

# Restart Nginx
systemctl restart nginx
systemctl enable nginx

# -----------------------------------------------------------------------------
# Done!
# -----------------------------------------------------------------------------
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. Clone your repo as the mystock user:"
echo -e "     ${YELLOW}sudo -u mystock git clone YOUR_REPO_URL $APP_DIR${NC}"
echo ""
echo -e "  2. Run the deployment script:"
echo -e "     ${YELLOW}cd $APP_DIR && sudo bash deployment/prod.sh${NC}"
echo ""
echo -e "  3. Get SSL certificate (after app is running):"
echo -e "     ${YELLOW}sudo certbot --nginx -d $DOMAIN${NC}"
echo ""
echo -e "  4. Set up auto-renewal for SSL:"
echo -e "     ${YELLOW}sudo systemctl enable certbot.timer${NC}"
echo ""
echo -e "App directory: $APP_DIR"
echo -e "App user: mystock"
echo -e "Domain: $DOMAIN"
