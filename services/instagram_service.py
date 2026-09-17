# ============================================================
# INSTAGRAM COOKIE CHECKER SERVICE
# ============================================================

import re
import requests

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from config import E
from utils import pe, update_bot_stats


WAITING_INSTAGRAM_FILE = 11
INSTAGRAM_EMOJI = "5319160079465857105"
INSTAGRAM_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"


def insta_parse_netscape(content):
    cookies = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) >= 7:
            name = parts[5]
            value = parts[6]
            if 'instagram.com' in parts[0].lower():
                cookies[name] = value
    return cookies


def insta_check_cookies(cookies):
    required = ["sessionid", "ds_user_id", "csrftoken", "mid"]
    missing = [c for c in required if c not in cookies]
    if missing:
        return {"status": "INVALID", "message": f"Missing cookies: {', '.join(missing)}"}
    try:
        session = requests.Session()
        for k, v in cookies.items():
            session.cookies.set(k, v, domain=".instagram.com")
        headers = {
            "User-Agent": INSTAGRAM_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.instagram.com/",
            "Upgrade-Insecure-Requests": "1",
        }
        response = session.get(
            "https://www.instagram.com/accounts/edit/",
            headers=headers,
            timeout=20,
            allow_redirects=True,
        )
        final_url = response.url
        status_code = response.status_code
        if status_code == 200 and "/accounts/edit" in final_url:
            username = "N/A"
            m = re.search(r'"username":"([^"]+)"', response.text)
            if m:
                username = m.group(1)
            return {
                "status": "LIVE",
                "username": username,
                "final_url": final_url,
                "cookies": cookies,
            }
        elif "/accounts/login" in final_url.lower() or "/login" in final_url.lower():
            return {"status": "DEAD", "message": "Redirected to login"}
        else:
            return {"status": "UNKNOWN", "message": f"HTTP {status_code}"}
    except Exception as e:
        return {"status": "INVALID", "message": str(e)[:80]}


def insta_cancel_button():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"{pe(E['cross'])} Cancel",
            callback_data="main_menu",
            icon_custom_emoji_id=E['cross']
        )
    ]])


def insta_back_button():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"{pe(E['prev'])} Back",
            callback_data="main_menu",
            icon_custom_emoji_id=E['prev']
        )
    ]])


def insta_fmt_live(r):
    return (
        f"╔═══════════════════════════╗\n"
        f"║  {pe(INSTAGRAM_EMOJI)} <b>INSTAGRAM LIVE!</b>     ║\n"
        f"╚═══════════════════════════╝\n\n"
        f"{pe(E['user'])}  <b>Username :</b> <code>{r.get('username','N/A')}</code>\n"
        f"{pe(E['check'])}  <b>Status   :</b> <code>LIVE</code>\n"
        f"{pe(E['star'])}  <b>File     :</b> <code>{r.get('filename','?')}</code>"
    )


def insta_fmt_dead(r):
    return (
        f"╔═══════════════════════════╗\n"
        f"║  {pe(INSTAGRAM_EMOJI)} <b>INSTAGRAM DEAD</b>      ║\n"
        f"╚═══════════════════════════╝\n\n"
        f"{pe(E['cross'])}  <b>Reason :</b> <code>{r.get('message', r.get('reason','Unknown'))[:80]}</code>\n"
        f"{pe(E['star'])}  <b>File   :</b> <code>{r.get('filename','?')}</code>"
    )


async def insta_start_handler(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{pe(INSTAGRAM_EMOJI)} <b>Instagram Cookie Checker</b>\n\n"
        f"{pe(E['next'])} Upload a <b>.txt</b> file with Instagram cookies\n"
        f"{pe(E['bolt'])} (Netscape: sessionid, ds_user_id, csrftoken, mid)\n\n"
        f"{pe(E['star'])} I will verify each session.",
        reply_markup=insta_cancel_button(),
        parse_mode="HTML"
    )
    return WAITING_INSTAGRAM_FILE


async def insta_handle_file(update, context):
    document = update.message.document
    if not document:
        await update.message.reply_html(
            f"{pe(E['cross'])} Please upload a file.",
            reply_markup=insta_cancel_button()
        )
        return WAITING_INSTAGRAM_FILE

    status_msg = await update.message.reply_html(
        f"{pe(E['loading'])} Processing file..."
    )

    try:
        file = await document.get_file()
        content = await file.download_as_bytearray()
        text = content.decode('utf-8', errors='ignore')

        cookies = insta_parse_netscape(text)
        if not cookies:
            await status_msg.edit_text(
                f"{pe(E['cross'])} No Instagram cookies found.",
                reply_markup=insta_back_button()
            )
            return ConversationHandler.END

        result = insta_check_cookies(cookies)
        result['filename'] = document.file_name or 'file'

        if result.get("status") == "LIVE":
            await status_msg.edit_text(insta_fmt_live(result), reply_markup=insta_back_button())
            update_bot_stats(True)
        else:
            await status_msg.edit_text(insta_fmt_dead(result), reply_markup=insta_back_button())
            update_bot_stats(False)

    except Exception as e:
        await status_msg.edit_text(
            f"{pe(E['cross'])} Error: {str(e)[:200]}",
            reply_markup=insta_back_button()
        )
        update_bot_stats(False)

    return ConversationHandler.END