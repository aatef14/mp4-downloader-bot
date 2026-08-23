#!/data/data/com.termux/files/usr/bin/bash
# Starts the bot in the background so it survives closing Termux.

cd "$(dirname "$0")"

if pgrep -f "python bot.py" > /dev/null; then
    echo "Bot is already running. Use 'bash stop.sh' first if you want to restart it."
    exit 1
fi

termux-wake-lock

nohup python bot.py >> bot.log 2>&1 &
disown

echo "Bot started in the background."
echo "View live messages with: bash logs.sh"
echo "Stop it with:            bash stop.sh"
