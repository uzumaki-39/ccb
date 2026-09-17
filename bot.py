# ============================================================
# MASTER BOT — Streaming + Cookie Checkers
# Modular Architecture - All services loaded dynamically
# ============================================================

import os
import re
import glob
import logging
import zipfile
import random
import string
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

from config import TOKEN, OWNER_ID, E, COOKIES_FOLDER, WATERMARK
from utils import pe, load_bot_stats, update_bot_stats, extract_cookie_dict
import services


# ─── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
log = logging.getLogger(__name__)


# ─── Main Menu Keyboard ──────────────────────────────────────
def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"{pe(E['globe'])} Netflix Trial",
                callback_data="netflix_trial",
                icon_custom_emoji_id=E['globe']
            ),
            InlineKeyboardButton(
                f"{pe(E['check'])} Netflix Check",
                callback_data="netflix_check",
                icon_custom_emoji_id=E['check']
            ),
        ],
        [
            InlineKeyboardButton(
                f"{pe(E['bolt'])} Netflix Token",
                callback_data="netflix_token",
                icon_custom_emoji_id=E['bolt']
            ),
            InlineKeyboardButton(
                f"{pe(E['globe'])} Surfshark",
                callback_data="surfshark",
                icon_custom_emoji_id=E['globe']
            ),
        ],
        [
            InlineKeyboardButton(
                f"{pe(E['rocket'])} Spotify TV",
                callback_data="spotify",
                icon_custom_emoji_id=E['rocket']
            ),
            InlineKeyboardButton(
                f"{pe(E['gem'])} HBO Max TV",
                callback_data="hbomax",
                icon_custom_emoji_id=E['gem']
            ),
        ],
        [
            InlineKeyboardButton(
                f"{pe(E['star'])} Crunchyroll",
                callback_data="crunchyroll",
                icon_custom_emoji_id=E['star']
            ),
            InlineKeyboardButton(
                f"{pe(E['chat'])} JioHotstar",
                callback_data="jiohotstar",
                icon_custom_emoji_id=E['chat']
            ),
        ],
        [
            InlineKeyboardButton(
                f"{pe(E['chatgpt'])} ChatGPT",
                callback_data="chatgpt",
                icon_custom_emoji_id=E['chatgpt']
            ),
            InlineKeyboardButton(
                f"{pe(E['cursor'])} Cursor",
                callback_data="cursor",
                icon_custom_emoji_id=E['cursor']
            ),
        ],
        [
            InlineKeyboardButton(
                f"{pe(E['instagram'])} Instagram",
                callback_data="instagram",
                icon_custom_emoji_id=E['instagram']
            ),
            InlineKeyboardButton(
                f"{pe(E['scan'])} Cookie Scan",
                callback_data="scan",
                icon_custom_emoji_id=E['scan']
            ),
        ],
        [
            InlineKeyboardButton(
                f"{pe(E['bank'])} Stats",
                callback_data="stats",
                icon_custom_emoji_id=E['bank']
            ),
            InlineKeyboardButton(
                f"{pe(E['gift'])} Help",
                callback_data="help",
                icon_custom_emoji_id=E['gift']
            ),
        ],
    ])


def back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"{pe(E['prev'])} Back",
            callback_data="main_menu",
            icon_custom_emoji_id=E['prev']
        )]
    ])


# ─── Command Handlers ────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    welcome = (
        f"{pe(E['gem'])} <b>Welcome, {user.first_name}!</b>\n\n"
        f"{pe(E['rocket'])} <b>Master Streaming + Cookie Bot</b>\n"
        f"{pe(E['bolt'])} Select a service below to get started.\n\n"
        f"{pe(E['sparkle'])} {WATERMARK}"
    )
    await update.message.reply_html(welcome, reply_markup=main_menu())


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_html(f"{pe(E['cross'])} Admin only!")
        return

    stats = load_bot_stats()
    cookie_count = len(glob.glob(f"{COOKIES_FOLDER}/*.txt"))

    text = (
        f"{pe(E['bank'])} <b>Bot Statistics</b>\n\n"
        f"{pe(E['bolt'])} <b>Total Activations:</b> {stats['total']}\n"
        f"{pe(E['check'])} <b>Successful:</b> {stats['successful']}\n"
        f"{pe(E['cross'])} <b>Failed:</b> {stats['failed']}\n"
        f"{pe(E['star'])} <b>Cookies in Vault:</b> {cookie_count}\n"
        f"{pe(E['hourglass'])} <b>Last Activity:</b> {stats.get('last', 'Never')}"
    )
    await update.message.reply_html(text, reply_markup=back_button())


async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_html(f"{pe(E['cross'])} Admin only!")
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_html(
            f"{pe(E['warn'])} Reply to a ZIP file with <code>/upload</code>",
            parse_mode="HTML"
        )
        return

    doc = update.message.reply_to_message.document
    if not doc.file_name.lower().endswith('.zip'):
        await update.message.reply_html(f"{pe(E['cross'])} Only .zip files accepted!")
        return

    status_msg = await update.message.reply_html(
        f"{pe(E['loading'])} Uploading cookies..."
    )

    try:
        file = await doc.get_file()
        content = await file.download_as_bytearray()

        os.makedirs(COOKIES_FOLDER, exist_ok=True)
        added = 0

        with zipfile.ZipFile(BytesIO(content), 'r') as zf:
            for name in zf.namelist():
                if name.endswith('/') or name.startswith('__MACOSX') or name.startswith('.'):
                    continue
                if not name.lower().endswith(('.txt', '.json')):
                    continue
                try:
                    c = zf.read(name).decode('utf-8', errors='ignore')
                    cookies = extract_cookie_dict(c)
                    if not cookies or not cookies.get('NetflixId'):
                        continue
                    base = os.path.basename(name)
                    safe = re.sub(r'[<>:"/\\|?*]', '_', base)
                    dest = os.path.join(COOKIES_FOLDER, safe)
                    if os.path.exists(dest):
                        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
                        name_part, ext = os.path.splitext(safe)
                        dest = os.path.join(COOKIES_FOLDER, f"{name_part}_{suffix}{ext}")
                    with open(dest, 'w', encoding='utf-8') as f:
                        f.write(c)
                    added += 1
                except Exception:
                    continue

        await status_msg.edit_text(
            f"{pe(E['check'])} <b>Upload Complete!</b>\n\n"
            f"{pe(E['bolt'])} Added: {added} cookies\n"
            f"{pe(E['star'])} Total: {len(glob.glob(f'{COOKIES_FOLDER}/*.txt'))}",
            reply_markup=back_button()
        )

    except Exception as e:
        await status_msg.edit_text(
            f"{pe(E['cross'])} Error: {str(e)[:200]}",
            reply_markup=back_button()
        )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_html(f"{pe(E['cross'])} Admin only!")
        return

    files = glob.glob(f"{COOKIES_FOLDER}/*.txt")
    deleted = 0
    for f in files:
        try:
            os.remove(f)
            deleted += 1
        except Exception:
            pass

    if os.path.exists("cookie_usage.json"):
        try:
            os.remove("cookie_usage.json")
        except Exception:
            pass

    await update.message.reply_html(
        f"{pe(E['check'])} <b>Cleared {deleted} cookies.</b>",
        reply_markup=back_button()
    )


# ─── Callback Router ─────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "main_menu":
        await query.answer()
        await query.edit_message_text(
            f"{pe(E['gem'])} <b>Master Streaming + Cookie Bot</b>\n\n"
            f"{pe(E['bolt'])} Select a service below.",
            reply_markup=main_menu(),
            parse_mode="HTML"
        )
        return ConversationHandler.END

    if data == "stats":
        await query.answer()
        stats = load_bot_stats()
        cookie_count = len(glob.glob(f"{COOKIES_FOLDER}/*.txt"))
        text = (
            f"{pe(E['bank'])} <b>Bot Statistics</b>\n\n"
            f"{pe(E['bolt'])} <b>Total Activations:</b> {stats['total']}\n"
            f"{pe(E['check'])} <b>Successful:</b> {stats['successful']}\n"
            f"{pe(E['cross'])} <b>Failed:</b> {stats['failed']}\n"
            f"{pe(E['star'])} <b>Cookies in Vault:</b> {cookie_count}\n"
            f"{pe(E['hourglass'])} <b>Last Activity:</b> {stats.get('last', 'Never')}"
        )
        await query.edit_message_text(text, reply_markup=back_button(), parse_mode="HTML")
        return ConversationHandler.END

    if data == "help":
        await query.answer()
        text = (
            f"{pe(E['gift'])} <b>Help & Commands</b>\n\n"
            f"{pe(E['rocket'])} <b>Streaming Services:</b>\n"
            f"• Netflix Trial / Check / Token\n"
            f"• Surfshark • Spotify TV • HBO Max\n"
            f"• Crunchyroll • JioHotstar\n\n"
            f"{pe(E['bolt'])} <b>Cookie Checkers:</b>\n"
            f"• ChatGPT • Cursor\n"
            f"• Instagram • Cookie Scanner\n\n"
            f"{pe(E['star'])} <b>How to use:</b>\n"
            f"1. Pick a service\n"
            f"2. Upload your cookie file\n"
            f"3. Get instant results\n\n"
            f"{pe(E['user'])} <b>Admin:</b> @NotYoursNaruto"
        )
        await query.edit_message_text(text, reply_markup=back_button(), parse_mode="HTML")
        return ConversationHandler.END

    # Route to service modules
    service_map = {
        "netflix_trial": services.netflix_trial.start_handler,
        "netflix_check": services.netflix_check.start_handler,
        "netflix_token": services.netflix_token.start_handler,
        "surfshark":     services.surfshark.start_handler,
        "spotify":       services.spotify.start_handler,
        "hbomax":        services.hbomax.start_handler,
        "crunchyroll":   services.crunchyroll.start_handler,
        "jiohotstar":    services.jiohotstar.start_handler,
        "chatgpt":       services.chatgpt_service.cg_start_handler,
        "cursor":        services.cursor_service.cursor_start_handler,
        "instagram":     services.instagram_service.insta_start_handler,
        "scan":          services.scan_cookies_service.scan_start_handler,
    }

    if data in service_map:
        handler = service_map[data]
        return await handler(update, context)

    await query.answer("Unknown command")
    return ConversationHandler.END


# ─── Main Application ────────────────────────────────────────
def main():
    print("\n" + "=" * 70)
    print(f" {pe(E['gem'])} MASTER BOT — STREAMING + COOKIE CHECKERS")
    print("=" * 70)
    print(f" {pe(E['bolt'])} 12 services loaded")
    print(f" {pe(E['star'])} Cookies Folder: {os.path.abspath(COOKIES_FOLDER)}")
    print(f" {pe(E['user'])} Owner ID: {OWNER_ID}")
    print("=" * 70 + "\n")

    app = ApplicationBuilder().token(TOKEN).build()

    # ─── Conversation Handler ────────────────────────────────
    states = {
        services.WAITING_EMAIL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, services.netflix_trial.handle_email)
        ],
        services.WAITING_NETFLIX_FILE: [
            MessageHandler(filters.Document.ALL, services.netflix_check.handle_file)
        ],
        services.WAITING_NETFLIX_TOKEN_FILE: [
            MessageHandler(filters.Document.ALL, services.netflix_token.handle_file)
        ],
        services.WAITING_SURFSHARK_CODE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, services.surfshark.handle_code)
        ],
        services.WAITING_SPOTIFY_CODE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, services.spotify.handle_code)
        ],
        services.WAITING_HBO_CODE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, services.hbomax.handle_code)
        ],
        services.WAITING_CRUNCHYROLL_CREDS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, services.crunchyroll.handle_creds)
        ],
        services.WAITING_JIO_QR: [
            MessageHandler(filters.PHOTO, services.jiohotstar.handle_qr)
        ],
        services.WAITING_CHATGPT_FILE: [
            MessageHandler(filters.Document.ALL, services.chatgpt_service.cg_handle_file)
        ],
        services.WAITING_CURSOR_FILE: [
            MessageHandler(filters.Document.ALL, services.cursor_service.cursor_handle_file)
        ],
        services.WAITING_INSTAGRAM_FILE: [
            MessageHandler(filters.Document.ALL, services.instagram_service.insta_handle_file)
        ],
        services.WAITING_SCAN_FILE: [
            MessageHandler(filters.Document.ALL, services.scan_cookies_service.scan_handle_file)
        ],
    }

    entry_points = [
        CallbackQueryHandler(
            button_callback,
            pattern="^(netflix_trial|netflix_check|netflix_token|surfshark|spotify|hbomax|crunchyroll|jiohotstar|chatgpt|cursor|instagram|scan)$"
        ),
    ]

    fallbacks = [
        CommandHandler("start", start),
        CallbackQueryHandler(button_callback, pattern="^main_menu$"),
    ]

    conv_handler = ConversationHandler(
        entry_points=entry_points,
        states=states,
        fallbacks=fallbacks,
        per_message=True,
    )

    app.add_handler(conv_handler)

    # ─── Other Handlers ──────────────────────────────────────
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("upload", upload_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^(main_menu|stats|help)$"))

    # ─── Run ─────────────────────────────────────────────────
    print(f"{pe(E['rocket'])} Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()