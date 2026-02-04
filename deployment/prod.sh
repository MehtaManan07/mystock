#!/usr/bin/env bash
set -e

APP_NAME="mystock"
APP_DIR="/home/manmehta/app"
VENV_DIR="$APP_DIR/venv"
SERVICE_NAME="mystock"
GIT_BRANCH="main"
PYTHON_BIN="python3"

echo "🚀 Deploying $APP_NAME..."

cd "$APP_DIR"

echo "📥 Pulling latest code..."
git fetch origin
git checkout "$GIT_BRANCH"
git pull origin "$GIT_BRANCH"

echo "🐍 Setting up virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
  $PYTHON_BIN -m venv "$VENV_DIR"
fi

echo "📦 Installing dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r requirements.txt

echo "🗄️ Running database migrations..."
if [ -f "alembic.ini" ]; then
  "$VENV_DIR/bin/alembic" upgrade head
else
  echo "⚠️  No alembic.ini found, skipping migrations"
fi

echo "🔄 Restarting systemd service..."
systemctl daemon-reload
systemctl restart "$SERVICE_NAME"

echo "🌐 Reloading nginx..."
systemctl reload nginx

echo "✅ Deployment complete!"
