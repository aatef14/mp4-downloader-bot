#!/data/data/com.termux/files/usr/bin/bash
# Tails the bot's live log output. Ctrl+C only stops watching,
# it does not stop the bot itself.

cd "$(dirname "$0")"

if [ ! -f bot.log ]; then
    echo "No bot.log yet. Start the bot first with: bash bot-start.sh"
    exit 1
fi

echo "Showing live bot messages. Press Ctrl+C to stop watching (bot keeps running)."
tail -f bot.log
