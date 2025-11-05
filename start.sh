#!/bin/bash
# ===============================================
# ✅ FINAL START SCRIPT for Render Telegram Bot
# -----------------------------------------------
# Fixes:
#  - Telethon cache problem
#  - offset_id keyword error
#  - Keeps app alive with ping
# ===============================================

echo "🚀 Installing dependencies (force source build)..."

# Clean old caches and force rebuild
pip uninstall -y telethon > /dev/null 2>&1 || true
pip install --no-cache-dir --no-binary :all: telethon==1.37.0
pip install --no-cache-dir requests==2.32.3

echo "✅ Dependencies installed successfully."

# ===============================================
# Optional: keep Render from sleeping
# ===============================================
if [ -f "config.json" ]; then
  PING_URL=$(jq -r '.ping_url' config.json 2>/dev/null)
  if [ "$PING_URL" != "null" ] && [ "$PING_URL" != "" ]; then
    echo "🌐 Ping URL loaded: $PING_URL"
  else
    echo "⚠️ No ping_url found in config.json — skipping ping setup."
  fi
else
  echo "⚠️ No config.json file found."
fi

# ===============================================
# Keep container alive — ping every 10 minutes
# ===============================================
(
  while true; do
    if [ ! -z "$PING_URL" ]; then
      curl -fsS "$PING_URL" >/dev/null 2>&1 && echo "💓 Ping sent to keep alive"
    fi
    sleep 600
  done
) &

# ===============================================
# Start Python bot
# ===============================================
echo "✅ Starting Telegram Member Extractor..."
python3 bot_controlled_fetcher.py || python bot_controlled_fetcher.py
