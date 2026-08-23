#!/data/data/com.termux/files/usr/bin/bash
# Stops the background bot process started by bot-start.sh.

if pgrep -f "python bot.py" > /dev/null; then
    pkill -f "python bot.py"
    echo "Bot stopped."
else
    echo "Bot is not running."
fi
