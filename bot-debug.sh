#!/data/data/com.termux/files/usr/bin/bash
# Runs the bot in the foreground so any startup error is visible immediately.
# Use this instead of bot-start.sh when the bot isn't starting and you need to
# see why. Ctrl+C stops it.

cd "$(dirname "$0")"

if pgrep -f "python bot.py" > /dev/null; then
    echo "A background instance is already running (started via bot-start.sh)."
    echo "Stop it first with: bash bot-stop.sh"
    exit 1
fi

if [ ! -f .env ]; then
    echo "No .env file found. Run: cp .env.example .env, then edit it and add your BOT_TOKEN."
    exit 1
fi

echo "Running in the foreground. Ctrl+C to stop."
echo "---"
python bot.py
