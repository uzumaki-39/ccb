# ============================================================
# MASTER STREAMING ACTIVATOR BOT
# Modular Architecture - All services loaded dynamically
# ============================================================

import os
import glob
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

from config import TOKEN, OWNER_ID, E, COOKIES_FOLDER, WATERMARK
from utils import pe, load_bot_stats, update_bot_stats
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
            )
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
            )
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
            )
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
            )
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
            )
        ]
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
        f"{pe(E['rocket'])} <b>Master Streaming Activator Bot</b>\n"
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
        import zipfile
        from io import BytesIO
        import random
        import string
        from utils import extract_cookie_dict

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
                except:
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
        except:
            pass

    if os.path.exists("cookie_usage.json"):
        try:
            os.remove("cookie_usage.json")
        except:
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
            f"{pe(E['gem'])} <b>Master Streaming Activator Bot</b>\n\n"
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
        return

    if data == "help":
        await query.answer()
        text = (
            f"{pe(E['gift'])} <b>Help & Commands</b>\n\n"
            f"{pe(E['bolt'])} <b>How to use:</b>\n"
            f"1. Select a service from the main menu\n"
            f"2. Follow the instructions\n"
            f"3. Get results instantly\n\n"
            f"{pe(E['sparkle'])} <b>Services:</b>\n"
            f"• Netflix Trial Offer\n"
            f"• Netflix Account Checker\n"
            f"• Netflix NF Token Generator\n"
            f"• Surfshark Auto-Login\n"
            f"• Spotify TV Activator\n"
            f"• HBO Max TV Activator\n"
            f"• Crunchyroll Checker\n"
            f"• JioHotstar TV Activator\n\n"
            f"{pe(E['user'])} <b>Admin:</b> @KindCoders"
        )
        await query.edit_message_text(text, reply_markup=back_button(), parse_mode="HTML")
        return

    # Route to service modules
    service_map = {
        "netflix_trial": services.netflix_trial.start_handler,
        "netflix_check": services.netflix_check.start_handler,
        "netflix_token": services.netflix_token.start_handler,
        "surfshark": services.surfshark.start_handler,
        "spotify": services.spotify.start_handler,
        "hbomax": services.hbomax.start_handler,
        "crunchyroll": services.crunchyroll.start_handler,
        "jiohotstar": services.jiohotstar.start_handler,
    }

    if data in service_map:
        handler = service_map[data]
        return await handler(update, context)

    await query.answer("Unknown command")
    return ConversationHandler.END


# ─── Main Application ────────────────────────────────────────

def main():
    print("\n" + "=" * 70)
    print(f" {pe(E['gem'])} MASTER STREAMING ACTIVATOR BOT - MODULAR")
    print("=" * 70)
    print(f" {pe(E['bolt'])} Services: Netflix · Surfshark · Spotify · HBO Max · Crunchyroll · JioHotstar")
    print(f" {pe(E['star'])} Cookies Folder: {os.path.abspath(COOKIES_FOLDER)}")
    print(f" {pe(E['user'])} Owner ID: {OWNER_ID}")
    print("=" * 70 + "\n")

    # Build app
    app = ApplicationBuilder().token(TOKEN).build()

    # ─── Conversation Handler ──────────────────────────────────
    # States from all services
    states = {
        services.netflix_trial.WAITING_EMAIL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, services.netflix_trial.handle_email)
        ],
        services.netflix_check.WAITING_NETFLIX_FILE: [
            MessageHandler(filters.Document.ALL, services.netflix_check.handle_file)
        ],
        services.netflix_token.WAITING_NETFLIX_TOKEN_FILE: [
            MessageHandler(filters.Document.ALL, services.netflix_token.handle_file)
        ],
        services.surfshark.WAITING_SURFSHARK_CODE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, services.surfshark.handle_code)
        ],
        services.spotify.WAITING_SPOTIFY_CODE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, services.spotify.handle_code)
        ],
        services.hbomax.WAITING_HBO_CODE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, services.hbomax.handle_code)
        ],
        services.crunchyroll.WAITING_CRUNCHYROLL_CREDS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, services.crunchyroll.handle_creds)
        ],
        services.jiohotstar.WAITING_JIO_QR: [
            MessageHandler(filters.PHOTO, services.jiohotstar.handle_qr)
        ],
    }

    entry_points = [
        CallbackQueryHandler(button_callback, pattern="^(netflix_trial|netflix_check|netflix_token|surfshark|spotify|hbomax|crunchyroll|jiohotstar)$"),
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