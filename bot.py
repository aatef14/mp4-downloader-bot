import asyncio
import logging
import os
import re
import shutil
import tempfile
import time
import uuid

import yt_dlp
from dotenv import load_dotenv
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
INSTAGRAM_COOKIES_FILE = os.environ.get("INSTAGRAM_COOKIES_FILE") or None
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "50"))

_allowed_raw = os.environ.get("ALLOWED_USER_IDS", "").strip()
ALLOWED_USER_IDS = {int(uid) for uid in _allowed_raw.split(",") if uid.strip()} if _allowed_raw else None

MAX_LOG_SIZE_MB = int(os.environ.get("MAX_LOG_SIZE_MB", "20"))
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.log")
CLEANUP_INTERVAL_SECONDS = 24 * 60 * 60
STALE_TEMP_DIR_AGE_SECONDS = 60 * 60
PENDING_URL_MAX_AGE_SECONDS = 30 * 60

# yt-dlp itself supports 1000+ sites, so we don't restrict which links are
# accepted — we just try to recognize the domain for a friendly label and
# let yt-dlp fail gracefully on anything it can't actually handle.
PLATFORM_LABELS = [
    (re.compile(r"(youtube\.com/shorts/)", re.IGNORECASE), "YouTube Shorts"),
    (re.compile(r"(youtube\.com|youtu\.be)", re.IGNORECASE), "YouTube"),
    (re.compile(r"instagram\.com/reel", re.IGNORECASE), "Instagram Reel"),
    (re.compile(r"instagram\.com", re.IGNORECASE), "Instagram"),
    (re.compile(r"tiktok\.com", re.IGNORECASE), "TikTok"),
    (re.compile(r"(twitter\.com|x\.com)", re.IGNORECASE), "X / Twitter"),
    (re.compile(r"facebook\.com|fb\.watch", re.IGNORECASE), "Facebook"),
    (re.compile(r"reddit\.com", re.IGNORECASE), "Reddit"),
]

URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)

PRIVATE_MESSAGE = (
    "This bot is private.\n\n"
    "Send /id to get your Telegram user ID, then send that ID to the bot "
    "owner and ask them to add it to ALLOWED_USER_IDS."
)

VIDEO_QUALITIES = [
    ("best", "Best available"),
    ("1080", "1080p"),
    ("720", "720p"),
    ("480", "480p"),
    ("360", "360p"),
]
AUDIO_QUALITIES = [
    ("320", "320 kbps"),
    ("192", "192 kbps"),
    ("128", "128 kbps"),
]

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("mp4-downloader-bot")

# Telegram callback_data is capped at 64 bytes, too short for most URLs, so
# button presses carry a short id that looks the URL up here instead.
# Each value is (url, created_at) so stale entries can be swept.
PENDING_URLS: dict[str, tuple[str, float]] = {}


def detect_platform(url: str) -> str:
    for pattern, label in PLATFORM_LABELS:
        if pattern.search(url):
            return label
    return "link"


def remember_url(url: str) -> str:
    req_id = uuid.uuid4().hex[:12]
    PENDING_URLS[req_id] = (url, time.time())
    return req_id


def format_keyboard(req_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🎬 MP4 (video)", callback_data=f"fmt:{req_id}:mp4"),
                InlineKeyboardButton("🎵 MP3 (audio)", callback_data=f"fmt:{req_id}:mp3"),
            ]
        ]
    )


def quality_keyboard(req_id: str, fmt: str) -> InlineKeyboardMarkup:
    options = VIDEO_QUALITIES if fmt == "mp4" else AUDIO_QUALITIES
    row = [
        InlineKeyboardButton(label, callback_data=f"dl:{req_id}:{fmt}:{value}")
        for value, label in options
    ]
    # Two buttons per row so it fits on a phone screen.
    rows = [row[i : i + 2] for i in range(0, len(row), 2)]
    return InlineKeyboardMarkup(rows)


def build_ydl_opts(out_path: str, url: str, fmt: str, quality: str) -> dict:
    opts = {
        "outtmpl": out_path,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_FILE_SIZE_MB * 1024 * 1024,
    }

    if fmt == "mp3":
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": quality,
            }
        ]
    else:
        height_filter = f"[height<={quality}]" if quality != "best" else ""
        opts["format"] = (
            f"bestvideo{height_filter}[ext=mp4]+bestaudio[ext=m4a]"
            f"/best{height_filter}[ext=mp4]/best{height_filter}/best"
        )
        opts["merge_output_format"] = "mp4"

    if "instagram.com" in url and INSTAGRAM_COOKIES_FILE:
        opts["cookiefile"] = INSTAGRAM_COOKIES_FILE
    return opts


def format_duration(seconds) -> str:
    if not seconds:
        return ""
    seconds = int(seconds)
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def find_output_file(work_dir: str) -> str | None:
    """yt-dlp's postprocessors (e.g. mp3 extraction) can change the final
    extension, so instead of guessing the path we just find the one real
    output file it left behind."""
    candidates = [
        f
        for f in os.listdir(work_dir)
        if not f.endswith((".part", ".ytdl", ".description", ".json"))
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda f: os.path.getsize(os.path.join(work_dir, f)), reverse=True)
    return os.path.join(work_dir, candidates[0])


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Send me a video link from YouTube, YouTube Shorts, Instagram, TikTok, "
        "X/Twitter, Facebook, or Reddit. I'll ask whether you want MP4 or MP3 "
        "and what quality, then send the file back.\n\n"
        f"Max file size: {MAX_FILE_SIZE_MB}MB (Telegram Bot API limit)."
    )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lines = [f"Your Telegram user ID: {user.id}"]
    if user.username:
        lines.append(f"Username: @{user.username}")
    lines.append("\nAdd this ID to ALLOWED_USER_IDS in .env to whitelist yourself.")
    await update.effective_message.reply_text("\n".join(lines))


async def process_download(url: str, fmt: str, quality: str, status, reply_target) -> None:
    """Download url as fmt/quality, editing status messages along the way,
    and send the result via reply_target.reply_video/reply_audio."""
    platform = detect_platform(url)
    await status.edit_text(f"Detected: {platform}\nDownloading...")

    work_dir = tempfile.mkdtemp(prefix="mp4bot_")
    out_template = os.path.join(work_dir, f"{uuid.uuid4().hex}.%(ext)s")

    try:
        ydl_opts = build_ydl_opts(out_template, url, fmt, quality)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        file_path = find_output_file(work_dir)
        if not file_path:
            await status.edit_text("Download failed: no output file produced.")
            return

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            await status.edit_text(
                f"File is {size_mb:.1f}MB, over the {MAX_FILE_SIZE_MB}MB Telegram limit. "
                "Try a lower quality, or run a local Bot API server to raise this to 2GB."
            )
            return

        title = info.get("title") or ""
        duration = format_duration(info.get("duration"))
        uploader = info.get("uploader") or ""
        caption_parts = [p for p in [title, uploader, duration] if p]
        caption = "\n".join(caption_parts)[:1024] or None

        await status.edit_text(f"Detected: {platform}\nUploading...")
        with open(file_path, "rb") as f:
            if fmt == "mp3":
                await reply_target.reply_audio(audio=f, caption=caption, title=title or None)
            else:
                await reply_target.reply_video(video=f, caption=caption, supports_streaming=True)
        await status.delete()

    except yt_dlp.utils.DownloadError as e:
        logger.warning("Download error for %s: %s", url, e)
        await status.edit_text(f"Couldn't download that link: {e}")
    except Exception:
        logger.exception("Unexpected error handling %s", url)
        await status.edit_text("Something went wrong processing that link.")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message

    if ALLOWED_USER_IDS is not None and update.effective_user.id not in ALLOWED_USER_IDS:
        await message.reply_text(PRIVATE_MESSAGE)
        return

    text = message.text or ""
    match = URL_RE.search(text)

    if not match:
        await message.reply_text(
            "Send me a YouTube, YouTube Shorts, Instagram, TikTok, X/Twitter, "
            "Facebook, or Reddit video link."
        )
        return

    url = match.group(0)
    req_id = remember_url(url)
    platform = detect_platform(url)
    await message.reply_text(
        f"Detected: {platform}\nChoose a format:",
        reply_markup=format_keyboard(req_id),
    )


async def handle_format_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if ALLOWED_USER_IDS is not None and update.effective_user.id not in ALLOWED_USER_IDS:
        await query.edit_message_text(PRIVATE_MESSAGE)
        return

    _, req_id, fmt = query.data.split(":")
    entry = PENDING_URLS.get(req_id)
    if not entry:
        await query.edit_message_text("This link expired, please send it again.")
        return

    await query.edit_message_text("Choose a quality:", reply_markup=quality_keyboard(req_id, fmt))


async def handle_quality_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if ALLOWED_USER_IDS is not None and update.effective_user.id not in ALLOWED_USER_IDS:
        await query.edit_message_text(PRIVATE_MESSAGE)
        return

    _, req_id, fmt, quality = query.data.split(":")
    entry = PENDING_URLS.pop(req_id, None)
    if not entry:
        await query.edit_message_text("This link expired, please send it again.")
        return

    url, _ = entry
    status = query.message
    await process_download(url, fmt, quality, status, status)


def cleanup_temp_files() -> int:
    """Remove leftover mp4bot_* temp dirs (normally cleaned up per-download,
    but a crash mid-download can strand one). Returns count removed."""
    removed = 0
    tmp_root = tempfile.gettempdir()
    now = time.time()
    try:
        entries = os.listdir(tmp_root)
    except OSError:
        return 0
    for name in entries:
        if not name.startswith("mp4bot_"):
            continue
        path = os.path.join(tmp_root, name)
        try:
            if now - os.path.getmtime(path) < STALE_TEMP_DIR_AGE_SECONDS:
                continue
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
        except OSError:
            pass
    return removed


def cleanup_pending_urls() -> int:
    now = time.time()
    stale = [rid for rid, (_, created) in PENDING_URLS.items() if now - created > PENDING_URL_MAX_AGE_SECONDS]
    for rid in stale:
        PENDING_URLS.pop(rid, None)
    return len(stale)


def rotate_log_if_large() -> None:
    try:
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > MAX_LOG_SIZE_MB * 1024 * 1024:
            open(LOG_PATH, "w").close()
            logger.info("Truncated bot.log after exceeding %sMB", MAX_LOG_SIZE_MB)
    except OSError:
        pass


async def daily_cleanup(context: ContextTypes.DEFAULT_TYPE) -> None:
    removed = cleanup_temp_files()
    cleanup_pending_urls()
    rotate_log_if_large()
    if removed:
        logger.info("Daily cleanup removed %d stale temp dir(s)", removed)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Network blips during polling (phone briefly losing signal/WiFi) are
    # normal and self-recovering, so log them as a one-liner instead of a
    # full traceback that makes it look like the bot crashed.
    logger.warning("Update handling error: %s", context.error)


async def set_bot_info(app: Application) -> None:
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Show usage instructions"),
            BotCommand("help", "Show usage instructions"),
            BotCommand("id", "Show your Telegram user ID"),
        ]
    )
    description = (
        "Send a YouTube, YouTube Shorts, Instagram, TikTok, X/Twitter, "
        "Facebook, or Reddit video link, pick MP4 or MP3 and a quality, "
        "and get the file back."
    )
    await app.bot.set_my_description(description)
    await app.bot.set_my_short_description("Video/audio link downloader")


def main() -> None:
    # Python 3.14 dropped asyncio.get_event_loop()'s auto-create behavior,
    # which python-telegram-bot's run_polling() still relies on internally.
    # https://github.com/python-telegram-bot/python-telegram-bot/issues/4874
    asyncio.set_event_loop(asyncio.new_event_loop())

    app = Application.builder().token(BOT_TOKEN).post_init(set_bot_info).build()
    app.add_handler(CommandHandler(["start", "help"], start_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CallbackQueryHandler(handle_format_choice, pattern=r"^fmt:"))
    app.add_handler(CallbackQueryHandler(handle_quality_choice, pattern=r"^dl:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    app.job_queue.run_repeating(daily_cleanup, interval=CLEANUP_INTERVAL_SECONDS, first=60)
    cleanup_temp_files()
    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
