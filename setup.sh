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

echo "==> Setting up boot autostart"
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/start-bot.sh <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
cd ~/mp4-downloader-bot
python bot.py >> bot.log 2>&1
EOF
chmod +x ~/.termux/boot/start-bot.sh

echo "==> Acquiring wake lock for this session"
termux-wake-lock

echo ""
echo "Setup complete."
echo "1. Copy .env.example to .env and add your BOT_TOKEN."
echo "2. Run the bot manually the first time with: python bot.py"
echo "3. After that, it will auto-start on phone reboot via Termux:Boot."
