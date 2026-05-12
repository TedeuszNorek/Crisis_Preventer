#!/bin/bash

# SignalVortex Management Script

case "$1" in
    start)
        echo "Starting SignalVortex..."
        # Kill existing instances first to avoid conflicts
        pkill -f "twa_server.py"
        pkill -f "cloudflared_runner.py"
        pkill -f "telegram_entry.py"
        
        # Start API
        nohup .venv/bin/python3 src/api/twa_server.py > uvicorn.log 2>&1 &
        echo "API started on port 8003 (see uvicorn.log)"
        
        # Start Tunnel
        nohup .venv/bin/python3 src/bots/cloudflared_runner.py >> tunnel.log 2>&1 &
        echo "Tunnel runner started (see tunnel.log)"
        
        # Start Telegram Bot
        nohup .venv/bin/python3 src/bots/telegram_entry.py >> bot.log 2>&1 &
        echo "Telegram Bot started (see bot.log)"
        
        echo "------------------------------------------------"
        sleep 5
        if [ -f url.txt ]; then
            echo "CURRENT URL: $(cat url.txt)"
            echo "Remember to update BotFather with this link!"
        fi
        ;;
    stop)
        echo "Stopping SignalVortex..."
        pkill -f "twa_server.py"
        pkill -f "cloudflared_runner.py"
        pkill -f "telegram_entry.py"
        echo "All processes stopped."
        ;;
    status)
        echo "Checking SignalVortex processes..."
        ps aux | grep -E "twa_server|cloudflared_runner|telegram_entry" | grep -v grep
        ;;
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
esac
