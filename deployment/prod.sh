#!/bin/bash

# deployment/prod.sh - Deploy mystock app for production (EC2)
# Usage: ./deployment/prod.sh

APP_NAME="mystock"
APP_DIR="/home/ec2-user/mystock"
VENV_DIR="/home/ec2-user/mystock/venv"

echo "🚀 Deploying MyStock app (PRODUCTION - EC2)..."

echo "📥 Pulling latest changes..."
cd $APP_DIR || exit
git pull origin main

echo "📦 Installing dependencies..."
source $VENV_DIR/bin/activate
pip install -r requirements.txt

echo "🔄 Restarting MyStock service..."
sudo systemctl restart $APP_NAME

echo "🌐 Restarting nginx..."
sudo systemctl reload nginx

echo "✅ Checking service status..."
if sudo systemctl is-active --quiet $APP_NAME; then
    echo "✅ MyStock service is running"
else
    echo "❌ MyStock service failed to start"
    sudo systemctl status $APP_NAME --no-pager
    exit 1
fi

echo "📄 Recent logs:"
sudo journalctl -u $APP_NAME -n 10 --no-pager

echo ""
echo "✅ Production deployment complete!"
