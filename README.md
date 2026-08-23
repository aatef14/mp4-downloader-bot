# mp4-downloader-bot

A Telegram bot that takes a YouTube, YouTube Shorts, Instagram, TikTok,
X/Twitter, Facebook, or Reddit video link and sends back the file as MP4
(video) or MP3 (audio), in a quality you choose. It runs on your own Android
phone via Termux — no rented server needed.

---

## 1. Install Termux on your phone

Don't use the Play Store version — it's outdated and broken for this use case.
Install from **F-Droid** instead:

1. Open your phone's browser and go to `f-droid.org`
2. Download and install the F-Droid app (your phone will warn about
   "installing unknown apps" — allow it for your browser just for this)
3. Open F-Droid, search for **Termux**, and install it
4. In F-Droid, also search for and install **Termux:Boot** and
   **Termux:API** (same publisher — needed later for auto-start and battery
   control)

## 2. Stop Android from killing the bot in the background

Android aggressively kills background apps to save battery, which would stop
the bot. Do this once:

1. **Settings → Apps → Termux → Battery** → set to **Unrestricted**
2. **Settings → Apps → Termux:Boot → Battery** → set to **Unrestricted**
3. **Settings → Battery → Battery optimization** → find Termux → **Don't optimize**
4. Open Termux, swipe it into your **Recent Apps** tray, and tap the pin/lock
   icon so a "clear all" swipe doesn't kill it

(No root required for any of this.)

## 3. Get a bot token from Telegram

1. In Telegram, search for **@BotFather** (the official one, verified checkmark)
2. Send it `/newbot`
3. Give it a display name (anything), then a username ending in `bot`
   (e.g. `my_video_downloader_bot`)
4. BotFather replies with a token like `7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxx`
   — copy it, you'll need it in step 5. **Keep it private** — anyone with it
   can control your bot.

## 4. Clone and set up the bot

Open Termux and run:

```bash
pkg install -y git
git clone https://github.com/aatef14/mp4-downloader-bot.git
cd mp4-downloader-bot
bash setup.sh
```

`setup.sh` installs Python, Node, ffmpeg, and all Python dependencies, sets
up storage access, and configures auto-start on reboot.

## 5. Add your bot token

```bash
cp .env.example .env
nano .env
```

Set `BOT_TOKEN=` to the token from step 3. Save with `Ctrl+O`, `Enter`, then
exit with `Ctrl+X`.

## 6. (Recommended) Lock the bot to just you

By default, **anyone who finds your bot's username on Telegram can use it**
— usernames are public and searchable. See [Whitelisting](#whitelisting-restricting-who-can-use-the-bot)
below to restrict it to yourself before going further.

## 7. Run it

```bash
bash start.sh
```

This starts the bot in the background — it keeps running even if you close
Termux. You'll see:
```
Bot started in the background.
View live messages with: bash logs.sh
Stop it with:            bash stop.sh
```

Then in Telegram, open a chat with your bot and send `/start`, or paste a
video link directly.

**Managing the bot going forward, three commands:**

| Action | Command |
|---|---|
| Start the bot | `bash start.sh` |
| Watch live activity/logs | `bash logs.sh` (Ctrl+C stops watching, not the bot) |
| Stop the bot | `bash stop.sh` |

Reboot your phone once after setup — Termux:Boot will auto-start the bot
from then on, so it comes back automatically after a restart or crash.

---

## How it works: choosing MP4/MP3 and quality

Send any supported video link. The bot detects which platform it's from and
asks you to pick a format:

```
Detected: YouTube
Choose a format:
[ 🎬 MP4 (video) ]  [ 🎵 MP3 (audio) ]
```

Then a quality menu appears:
- **MP4**: Best available, 1080p, 720p, 480p, 360p
- **MP3**: 320 kbps, 192 kbps, 128 kbps

Tap one, and the bot downloads and sends the file back with the title,
uploader, and duration as the caption.

---

## Whitelisting: restricting who can use the bot

Telegram bots are public by default — anyone who finds the username can
message it and use your phone's bandwidth/battery to download videos. To
restrict it to yourself (or a few trusted people):

1. Message your own bot with `/id` — it replies with your numeric Telegram
   user ID (e.g. `123456789`)
2. Stop the bot if it's running: `bash stop.sh`
3. Edit `.env`:
   ```bash
   nano .env
   ```
4. Set `ALLOWED_USER_IDS=123456789` (your ID). To allow more people,
   comma-separate their IDs: `ALLOWED_USER_IDS=123456789,987654321`
5. Save and restart: `bash start.sh`

Anyone whose ID isn't in that list gets "This bot is private." instead of a
response. Leaving `ALLOWED_USER_IDS` blank allows anyone to use the bot.

---

## Notes

- Telegram's standard Bot API caps uploads at 50MB (`MAX_FILE_SIZE_MB` in
  `.env`). To send larger files you'd need to run your own local Bot API
  server with credentials from https://my.telegram.org — not covered here.
- Instagram often rate-limits anonymous requests. If downloads start
  failing, export cookies from a logged-in browser session and point
  `INSTAGRAM_COOKIES_FILE` at that file in `.env`.
- Logs are written to `bot.log` in the project folder; it's automatically
  truncated once it exceeds `MAX_LOG_SIZE_MB` (default 20MB) so it won't
  fill up your storage.
- Leftover temp files from any crashed download are swept daily and on
  every startup, so normal use won't accumulate storage over time.
