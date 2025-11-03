#!/bin/bash
echo "🚀 Installing dependencies..."
pip install -r requirements.txt

echo "✅ Starting Telegram Member Extractor..."
python3 bot_controlled_fetcher.py
