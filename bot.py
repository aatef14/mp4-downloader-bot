import asyncio
import logging
import os
import re
import tempfile
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

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("mp4-downloader-bot")

# Telegram callback_data is capped at 64 bytes, too short for most URLs, so
# retry buttons carry a short id that looks this dict up instead of the URL.
PENDING_URLS: dict[str, str] = {}


def detect_platform(url: str) -> str:
    for pattern, label in PLATFORM_LABELS:
        if pattern.search(url):
            return label
    return "link"


def build_ydl_opts(out_path: str, url: str) -> dict:
    opts = {
        "outtmpl": out_path,
        "format": f"bestvideo[ext=mp4][filesize<{MAX_FILE_SIZE_MB}M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<{MAX_FILE_SIZE_MB}M]/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_FILE_SIZE_MB * 1024 * 1024,
    }
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


def retry_keyboard(url: str) -> InlineKeyboardMarkup:
    req_id = uuid.uuid4().hex[:12]
    PENDING_URLS[req_id] = url
    return InlineKeyboardMarkup([[InlineKeyboardButton("Retry", callback_data=f"retry:{req_id}")]])


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Send me a video link from YouTube, YouTube Shorts, Instagram, TikTok, "
        "X/Twitter, Facebook, or Reddit and I'll send back the mp4.\n\n"
        f"Max file size: {MAX_FILE_SIZE_MB}MB (Telegram Bot API limit)."
    )


async def process_url(url: str, status, reply_target) -> None:
    """Download url, editing status messages along the way, and send the
    result (or a retry button on failure) via reply_target.reply_video/text."""
    platform = detect_platform(url)
    await status.edit_text(f"Detected: {platform}\nDownloading...")

    work_dir = tempfile.mkdtemp(prefix="mp4bot_")
    out_template = os.path.join(work_dir, f"{uuid.uuid4().hex}.%(ext)s")

    try:
        ydl_opts = build_ydl_opts(out_template, url)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            if not file_path.endswith(".mp4"):
                mp4_path = os.path.splitext(file_path)[0] + ".mp4"
                if os.path.exists(mp4_path):
                    file_path = mp4_path

        if not os.path.exists(file_path):
            await status.edit_text(
                "Download failed: no output file produced.",
                reply_markup=retry_keyboard(url),
            )
            return

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            await status.edit_text(
                f"Video is {size_mb:.1f}MB, over the {MAX_FILE_SIZE_MB}MB Telegram limit. "
                "Run a local Bot API server to raise this to 2GB."
            )
            return

        title = info.get("title") or ""
        duration = format_duration(info.get("duration"))
        uploader = info.get("uploader") or ""
        caption_parts = [p for p in [title, uploader, duration] if p]
        caption = "\n".join(caption_parts)[:1024] or None

        await status.edit_text(f"Detected: {platform}\nUploading...")
        with open(file_path, "rb") as f:
            await reply_target.reply_video(video=f, caption=caption, supports_streaming=True)
        await status.delete()

    except yt_dlp.utils.DownloadError as e:
        logger.warning("Download error for %s: %s", url, e)
        await status.edit_text(
            f"Couldn't download that link: {e}",
            reply_markup=retry_keyboard(url),
        )
    except Exception:
        logger.exception("Unexpected error handling %s", url)
        await status.edit_text(
            "Something went wrong processing that link.",
            reply_markup=retry_keyboard(url),
        )
    finally:
        for fname in os.listdir(work_dir):
            try:
                os.remove(os.path.join(work_dir, fname))
            except OSError:
                pass
        try:
            os.rmdir(work_dir)
        except OSError:
            pass


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message

    if ALLOWED_USER_IDS is not None and update.effective_user.id not in ALLOWED_USER_IDS:
        await message.reply_text("This bot is private.")
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
    status = await message.reply_text("Working on it...")
    await process_url(url, status, message)


async def handle_retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if ALLOWED_USER_IDS is not None and update.effective_user.id not in ALLOWED_USER_IDS:
        await query.edit_message_text("This bot is private.")
        return

    req_id = query.data.split(":", 1)[1]
    url = PENDING_URLS.pop(req_id, None)
    if not url:
        await query.edit_message_text("This retry link expired, send the URL again.")
        return

    status = query.message
    await process_url(url, status, status)


async def set_bot_info(app: Application) -> None:
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Show usage instructions"),
            BotCommand("help", "Show usage instructions"),
        ]
    )
    description = (
        "Send a YouTube, YouTube Shorts, Instagram, TikTok, X/Twitter, "
        "Facebook, or Reddit video link and get the mp4 back."
    )
    await app.bot.set_my_description(description)
    await app.bot.set_my_short_description("Video link to mp4 downloader")


def main() -> None:
    # Python 3.14 dropped asyncio.get_event_loop()'s auto-create behavior,
    # which python-telegram-bot's run_polling() still relies on internally.
    # https://github.com/python-telegram-bot/python-telegram-bot/issues/4874
    asyncio.set_event_loop(asyncio.new_event_loop())

    app = Application.builder().token(BOT_TOKEN).post_init(set_bot_info).build()
    app.add_handler(CommandHandler(["start", "help"], start_command))
    app.add_handler(CallbackQueryHandler(handle_retry, pattern=r"^retry:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
