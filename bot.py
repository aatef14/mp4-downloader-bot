import asyncio
import logging
import os
import re
import tempfile
import uuid

import yt_dlp
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, MessageHandler, ContextTypes, filters

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
INSTAGRAM_COOKIES_FILE = os.environ.get("INSTAGRAM_COOKIES_FILE") or None
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "50"))

URL_RE = re.compile(
    r"https?://(?:www\.)?"
    r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|instagram\.com/(?:reel|p|tv)/)"
    r"[^\s]+",
    re.IGNORECASE,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("mp4-downloader-bot")


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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    text = message.text or ""
    match = URL_RE.search(text)

    if not match:
        await message.reply_text(
            "Send me a YouTube, YouTube Shorts, or Instagram video/reel link."
        )
        return

    url = match.group(0)
    status = await message.reply_text("Downloading...")

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
            await status.edit_text("Download failed: no output file produced.")
            return

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            await status.edit_text(
                f"Video is {size_mb:.1f}MB, over the {MAX_FILE_SIZE_MB}MB Telegram limit. "
                "Run a local Bot API server to raise this to 2GB."
            )
            return

        await status.edit_text("Uploading...")
        with open(file_path, "rb") as f:
            await message.reply_video(video=f, supports_streaming=True)
        await status.delete()

    except yt_dlp.utils.DownloadError as e:
        logger.warning("Download error for %s: %s", url, e)
        await status.edit_text(f"Couldn't download that link: {e}")
    except Exception:
        logger.exception("Unexpected error handling %s", url)
        await status.edit_text("Something went wrong processing that link.")
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


def main() -> None:
    # Python 3.14 dropped asyncio.get_event_loop()'s auto-create behavior,
    # which python-telegram-bot's run_polling() still relies on internally.
    # https://github.com/python-telegram-bot/python-telegram-bot/issues/4874
    asyncio.set_event_loop(asyncio.new_event_loop())

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
