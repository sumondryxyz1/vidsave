"""Telegram download bot: send a link, pick a quality, get the file."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction, ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import downloader
from downloader import MediaInfo

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("dlbot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Telegram bot upload limit is 50 MB (2 GB only with a local Bot API server).
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "1800"))

MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "3"))
_sem = asyncio.Semaphore(MAX_CONCURRENT)

# chat_id -> probed media info (kept briefly so callbacks can use it)
_pending: dict[int, MediaInfo] = {}
_pending_ts: dict[int, float] = {}
PENDING_TTL = 1800


def _fmt_duration(seconds: int | None) -> str:
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _quality_keyboard(chat_id: int, info: MediaInfo) -> InlineKeyboardMarkup:
    heights = downloader.available_heights(info)
    # Offer at most 4 sensible video options plus audio.
    picks = [h for h in (2160, 1440, 1080, 720, 480, 360, 240) if h in heights]
    if not picks:
        picks = heights[-4:] if heights else []
    picks = sorted(set(picks), reverse=True)[:4]

    row = [InlineKeyboardButton(f"🎬 {h}p", callback_data=f"q|{chat_id}|{h}") for h in picks]
    rows = [row] if row else []
    rows.append([InlineKeyboardButton("🎵 অডিও (MP3)", callback_data=f"q|{chat_id}|audio")])
    rows.append([InlineKeyboardButton("⭐ সেরা কোয়ালিটি", callback_data=f"q|{chat_id}|best")])
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 *ডাউনলোড বট*\n\n"
        "যেকোনো সাইটের (YouTube, Facebook, Instagram, TikTok, X…) লিংক পাঠান।\n"
        "আমি ভিডিও/অডিও কোয়ালিটি বেছে নিতে দেব, তারপর ফাইল পাঠাব।\n\n"
        "কমান্ড:\n"
        "/start – এই মেসেজ\n"
        "/help – সাহায্য",
        parse_mode=ParseMode.MARKDOWN,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🔗 শুধু একটা লিংক পেস্ট করে পাঠান।\n"
        "প্রাইভেট/এজ-রেস্ট্রিক্টেড কনটেন্টের জন্য বট চালানোর সময় "
        "`YT_COOKIES` / `FB_COOKIES` / `IG_COOKIES` এনভায়রনমেন্ট ভেরিয়েবলে "
        "cookies.txt ফাইলের পাথ দিন।\n\n"
        f"⚠️ Telegram-এর আপলোড লিমিট {MAX_UPLOAD_MB}MB। বড় ফাইল পাঠানো যাবে না।",
        parse_mode=ParseMode.MARKDOWN,
    )


def _prune_pending() -> None:
    now = time.time()
    for cid in list(_pending_ts):
        if now - _pending_ts[cid] > PENDING_TTL:
            _pending.pop(cid, None)
            _pending_ts.pop(cid, None)


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    url = downloader.extract_url(message.text or "")
    if not url:
        await message.reply_text("❌ কোনো বৈধ লিংক পাইনি। একটা URL পাঠান।")
        return

    _prune_pending()
    chat_id = update.effective_chat.id
    status = await message.reply_text("🔎 লিংক পরীক্ষা করছি…")

    try:
        info = await asyncio.wait_for(
            asyncio.to_thread(downloader.probe, url), timeout=120
        )
    except Exception as exc:  # noqa: BLE001 - report any extraction failure to user
        log.warning("probe failed for %s: %s", url, exc)
        await status.edit_text(
            "❌ লিংক থেকে তথ্য বের করা যায়নি।\n"
            "সাইট সাপোর্টেড কিনা বা লিংক সঠিক কিনা দেখুন।\n"
            f"`{type(exc).__name__}`"
        )
        return

    _pending[chat_id] = info
    _pending_ts[chat_id] = time.time()

    caption = (
        f"🎬 *{_escape(info.title)}*\n"
        f"👤 {_escape(info.uploader or 'unknown')}\n"
        f"⏱ {_fmt_duration(info.duration)}\n\n"
        "কোয়ালিটি বেছে নিন 👇"
    )

    keyboard = _quality_keyboard(chat_id, info)
    if info.thumbnail:
        try:
            await message.reply_photo(photo=info.thumbnail, caption=caption,
                                      parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
            await status.delete()
            return
        except TelegramError:
            pass
    await status.edit_text(caption, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


def _escape(text: str) -> str:
    for ch in ("_", "*", "[", "]", "`"):
        text = text.replace(ch, "\\" + ch)
    return text


async def on_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    _, owner, value = query.data.split("|", 2)
    chat_id = int(owner)

    info = _pending.get(chat_id)
    if not info:
        await query.edit_message_text("⌛ লিংকটির সময় শেষ। আবার লিংক পাঠান।")
        return

    if value == "audio":
        height, audio_only, label = None, True, "🎵 MP3"
    elif value == "best":
        height, audio_only, label = None, False, "⭐ best"
    else:
        height, audio_only, label = int(value), False, f"🎬 {value}p"

    await query.edit_message_text(f"⏳ ডাউনলোড হচ্ছে — {label}…")

    tmp = downloader.make_temp_dir()
    loop = asyncio.get_running_loop()
    last_edit = 0.0
    lock = asyncio.Lock()

    def hook(d: dict) -> None:
        nonlocal last_edit
        if d.get("status") != "downloading":
            return
        now = time.time()
        if now - last_edit < 4:
            return
        last_edit = now
        pct = d.get("_percent_str", "").strip()
        speed = d.get("_speed_str", "").strip()
        eta = d.get("_eta_str", "").strip()
        text = f"⏳ ডাউনলোড {label} — {pct} | {speed} | ETA {eta}"
        asyncio.run_coroutine_threadsafe(_safe_edit(query, text, lock), loop)

    try:
        async with _sem:
            path = await asyncio.wait_for(
                asyncio.to_thread(
                    downloader.download, info.webpage_url, tmp,
                    height=height, audio_only=audio_only, progress_hook=hook,
                ),
                timeout=DOWNLOAD_TIMEOUT,
            )
    except asyncio.TimeoutError:
        downloader.cleanup(tmp)
        await query.edit_message_text("⏱ সময় শেষ। ফাইলটি খুব বড় বা সাইট ধীর। আবার চেষ্টা করুন।")
        return
    except Exception as exc:  # noqa: BLE001 - surface failure reason
        log.warning("download failed: %s", exc)
        downloader.cleanup(tmp)
        await query.edit_message_text(f"❌ ডাউনলোড ব্যর্থ হলো।\n`{type(exc).__name__}`")
        return

    path = Path(path)
    size = path.stat().st_size

    if size > MAX_UPLOAD_BYTES:
        downloader.cleanup(tmp)
        await query.edit_message_text(
            f"📦 ফাইলটি {size / 1024 / 1024:.1f}MB — Telegram লিমিট "
            f"{MAX_UPLOAD_MB}MB এর চেয়ে বড়। ছোট কোয়ালিটি বেছে নিন।"
        )
        return

    await query.edit_message_text("📤 আপলোড হচ্ছে…")
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)

    try:
        with path.open("rb") as fh:
            if audio_only:
                await context.bot.send_audio(
                    chat_id=chat_id, audio=fh, title=info.title,
                    performer=info.uploader or None, duration=info.duration,
                    read_timeout=300, write_timeout=300,
                )
            else:
                await context.bot.send_video(
                    chat_id=chat_id, video=fh, caption=info.title[:1000],
                    duration=info.duration, supports_streaming=True,
                    read_timeout=300, write_timeout=300,
                )
    except TelegramError as exc:
        log.warning("upload failed: %s", exc)
        await query.edit_message_text("❌ আপলোড ব্যর্থ হলো। ফাইলটি হয়তো বড়।")
    else:
        await query.edit_message_text("✅ সম্পন্ন!")
    finally:
        downloader.cleanup(tmp)


async def _safe_edit(query, text: str, lock: asyncio.Lock) -> None:
    async with lock:
        try:
            await query.edit_message_text(text)
        except TelegramError:
            pass


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("unhandled error", exc_info=context.error)


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN সেট করুন (BotFather থেকে পাওয়া টোকেন):\n"
            "  export BOT_TOKEN=123456:ABC..."
        )

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(on_choice, pattern=r"^q\|"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_error_handler(on_error)

    log.info("Bot চালু হচ্ছে… আপলোড লিমিট %sMB", MAX_UPLOAD_MB)
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
