# mp4-downloader-bot

Telegram bot that fetches YouTube, YouTube Shorts, and Instagram video links and
replies with the mp4 file directly in chat. Designed to run on an Android
phone via Termux instead of a rented server.

## Setup (Termux, on the Android device)

1. Install these from F-Droid: **Termux**, **Termux:Boot**, **Termux:API**.
2. In Termux, disable battery optimization for Termux and Termux:Boot
   (Settings → Apps → Termux/Termux:Boot → Battery → Unrestricted), and pin
   Termux in the recent-apps tray.
3. Clone this repo:
   ```bash
   git clone https://github.com/aatef14/mp4-downloader-bot.git
   cd mp4-downloader-bot
   ```
4. Run the setup script:
   ```bash
   bash setup.sh
   ```
5. Copy `.env.example` to `.env` and fill in your bot token from
   [@BotFather](https://t.me/BotFather):
   ```bash
   cp .env.example .env
   nano .env
   ```
6. Start the bot manually the first time to confirm it works:
   ```bash
   python bot.py
   ```
7. Reboot the phone once — Termux:Boot will auto-start the bot from then on
   (see `~/.termux/boot/start-bot.sh`, created by `setup.sh`).

## Notes

- Telegram's standard Bot API caps uploads at 50MB (`MAX_FILE_SIZE_MB` in
  `.env`). To send larger files you need to run your own local Bot API
  server with credentials from https://my.telegram.org — not covered here yet.
- Instagram often rate-limits anonymous requests. If downloads start
  failing, export cookies from a logged-in browser session and point
  `INSTAGRAM_COOKIES_FILE` at that file in `.env`.
- Logs are written to `bot.log` when started via the boot script.
