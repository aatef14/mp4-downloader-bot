#!/data/data/com.termux/files/usr/bin/bash
# Starts the bot in the background so it survives closing Termux.

cd "$(dirname "$0")"

if pgrep -f "python bot.py" > /dev/null; then
    echo "Bot is already running. Use 'bash bot-stop.sh' first if you want to restart it."
    exit 1
fi

termux-wake-lock

nohup python bot.py >> bot.log 2>&1 &
disown

sleep 3

if pgrep -f "python bot.py" > /dev/null; then
    echo "Bot started in the background."
    echo "View live messages with: bash bot-logs.sh"
    echo "Stop it with:            bash bot-stop.sh"
else
    echo "Bot failed to start. Last log lines:"
    echo "---"
    tail -n 20 bot.log
    echo "---"
    echo "Run 'bash bot-debug.sh' to see the full error live."
    exit 1
fi
