#!/data/data/com.termux/files/usr/bin/bash
# One-shot Termux setup for the mp4-downloader-bot.
# Run this inside Termux after installing Termux, Termux:Boot, and Termux:API from F-Droid.

set -e

echo "==> Updating Termux packages"
pkg update -y && pkg upgrade -y

echo "==> Installing Python, Node, ffmpeg, git"
pkg install -y python nodejs ffmpeg git

echo "==> Enabling storage access (approve the Android permission prompt)"
termux-setup-storage

echo "==> Installing Python dependencies"
pip install -r requirements.txt

echo "==> Making start/stop/logs scripts executable"
chmod +x start.sh stop.sh logs.sh

echo "==> Setting up boot autostart"
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/start-bot.sh <<EOF
#!/data/data/com.termux/files/usr/bin/bash
bash "$(pwd)/start.sh"
EOF
chmod +x ~/.termux/boot/start-bot.sh

echo "==> Acquiring wake lock for this session"
termux-wake-lock

echo ""
echo "Setup complete."
echo "1. Copy .env.example to .env and add your BOT_TOKEN."
echo "2. Start the bot with:   bash start.sh"
echo "3. Watch live logs with: bash logs.sh"
echo "4. Stop the bot with:    bash stop.sh"
echo "5. It will also auto-start on phone reboot via Termux:Boot."
