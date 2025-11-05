#!/bin/bash
echo "🚀 Installing dependencies..."
pip install --no-cache-dir telethon==1.37.0 requests==2.32.3

echo "✅ Dependencies installed successfully."
echo "💓 Starting Telegram Member Extractor..."
python3 bot_controlled_fetcher.py
