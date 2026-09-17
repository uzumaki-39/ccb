# ============================================================
# CURSOR COOKIE ANALYZER SERVICE
# ============================================================

import re
import json
import base64
from io import BytesIO
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import ContextTypes, ConversationHandler

from config import E
from utils import pe, update_bot_stats


WAITING_CURSOR_FILE = 10
CURSOR_EMOJI = "6273793612715138423"
CURSOR_COOKIES = ["WorkosCursorSessionToken", "cursor_session", "__client"]


def cursor_decode_jwt(token):
    try:
        token = token.strip()
        if not token or '.' not in token or len(token) < 50:
            return None
        parts = token.split('.')
        if len(parts) < 3:
            return None
        payload = parts[1] + '=' * (4 - len(parts[1]) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return None


def cursor_parse_cookies(content):
    found = []
    for line in content.strip().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '\t' in line:
            parts = line.split('\t')
            if len(parts) >= 7:
                name = parts[5]
                value = parts[6].strip()
                if name in CURSOR_COOKIES and value:
                    found.append({name: value})
            continue
        if line.startswith('{'):
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    ck = {k: v for k, v in data.items() if k in CURSOR_COOKIES}
                    if ck:
                        found.append(ck)
            except Exception:
                pass
            continue
        if '=' in line and not line.startswith('http') and ';' in line:
            cookies = {}
            for pair in line.split(';'):
                if '=' in pair:
                    k, _, v = pair.strip().partition('=')
                    k = k.strip()
                    v = v.strip()
                    if k in CURSOR_COOKIES and v:
                        cookies[k] = v
            if cookies:
                found.append(cookies)
            continue
        if line.count('.') == 2 and len(line) > 50:
            found.append({"WorkosCursorSessionToken": line})
    return found


def cursor_check_cookie(cookie_dict):
    token = (
        cookie_dict.get('WorkosCursorSessionToken') or
        cookie_dict.get('cursor_session') or
        cookie_dict.get('__client') or ''
    )
    if not token or len(token) < 50:
        return {"status": "INVALID", "email": "N/A", "plan": "N/A", "details": "No valid token"}
    data = cursor_decode_jwt(token)
    if not data:
        return {"status": "UNKNOWN", "email": "N/A", "plan": "N/A", "details": "Non-JWT token"}
    exp = data.get("exp")
    email = data.get("email", data.get("sub", "N/A"))
    name = data.get("name", "N/A")
    if exp and datetime.now().timestamp() > exp:
        return {"status": "EXPIRED", "email": email, "plan": "N/A",
                "details": f"Expired: {datetime.fromtimestamp(exp).strftime('%Y-%m-%d')}"}
    sub = data.get("subscription", {})
    if isinstance(sub, dict):
        tier = sub.get("tier", sub.get("plan", "free")).upper()
    elif sub:
        tier = str(sub).upper()
    else:
        tier = str(data.get("plan", data.get("tier", "free"))).upper()
    is_pro = tier in ["PRO", "PREMIUM", "BUSINESS", "TEAM", "ENTERPRISE", "HOBBY_PRO"]
    plan_label = tier.title() if tier else "Free"
    return {
        "status": "PRO" if is_pro else "FREE",
        "email": email,
        "name": name,
        "plan": plan_label,
        "tier": tier,
        "details": f"JWT tier:{tier}",
        "token": token[:40] + "...",
        "full_token": token,
    }


def cursor_cancel_button():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"{pe(E['cross'])} Cancel",
            callback_data="main_menu",
            icon_custom_emoji_id=E['cross']
        )
    ]])


def cursor_back_button():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"{pe(E['prev'])} Back",
            callback_data="main_menu",
            icon_custom_emoji_id=E['prev']
        )
    ]])


def cursor_fmt_pro(r):
    return (
        f"╔═══════════════════════════╗\n"
        f"║  {pe(CURSOR_EMOJI)} <b>CURSOR PRO HIT!</b>       ║\n"
        f"╚═══════════════════════════╝\n\n"
        f"{pe(E['user'])}  <b>Name   :</b> <code>{r.get('name','Unknown')}</code>\n"
        f"{pe(E['link'])}  <b>Email  :</b> <code>{r.get('email','Unknown')}</code>\n"
        f"{pe(E['gem'])}  <b>Plan   :</b> <code>{r.get('plan','Unknown')}</code>\n"
        f"{pe(E['bolt'])}  <b>Tier   :</b> <code>{r.get('tier','Unknown')}</code>\n"
        f"{pe(E['star'])}  <b>File   :</b> <code>{r.get('filename','?')}</code>"
    )


def cursor_fmt_summary(total, pro, free, dead):
    return (
        f"╔═══════════════════════════╗\n"
        f"║  {pe(CURSOR_EMOJI)} <b>CURSOR CHECK COMPLETE</b>  ║\n"
        f"╚═══════════════════════════╝\n\n"
        f"{pe(E['dice'])} Total : <b>{total}</b>\n"
        f"{pe(E['gem'])} Pro   : <b>{pro}</b>\n"
        f"{pe(E['cross'])} Free  : <b>{free}</b>\n"
        f"{pe(E['warn'])} Dead  : <b>{dead}</b>"
    )


def cursor_fmt_progress(done, total, pro, free, dead, last=None):
    pct = done / total if total else 0
    filled = int(pct * 10)
    bar = "█" * filled + "░" * (10 - filled)
    preview = ""
    if last and last.get("status") == "PRO":
        preview = (
            f"\n━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{pe(CURSOR_EMOJI)} <b>Latest Pro:</b>\n"
            f"  {pe(E['link'])} {last.get('email', 'Unknown')}\n"
            f"  {pe(E['gem'])} {last.get('plan', 'Unknown')}\n"
        )
    return (
        f"{pe(CURSOR_EMOJI)} <b>Cursor Analyzer</b> — Running\n\n"
        f"<code>[{bar}]  {int(pct * 100)}%</code>\n\n"
        f"{pe(E['gem'])} Pro     : <b>{pro}</b>\n"
        f"{pe(E['cross'])} Free    : <b>{free}</b>\n"
        f"{pe(E['warn'])} Dead    : <b>{dead}</b>\n"
        f"{pe(E['star'])} Checked : <b>{done}</b> / <b>{total}</b>"
        f"{preview}"
    )


async def cursor_start_handler(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{pe(CURSOR_EMOJI)} <b>Cursor Cookie Analyzer</b>\n\n"
        f"{pe(E['next'])} Upload a <b>.txt</b> file with Cursor cookies\n"
        f"{pe(E['bolt'])} (WorkosCursorSessionToken JWT)\n\n"
        f"{pe(E['star'])} I will decode JWTs and extract PRO accounts.",
        reply_markup=cursor_cancel_button(),
        parse_mode="HTML"
    )
    return WAITING_CURSOR_FILE


async def cursor_handle_file(update, context):
    document = update.message.document
    if not document:
        await update.message.reply_html(
            f"{pe(E['cross'])} Please upload a file.",
            reply_markup=cursor_cancel_button()
        )
        return WAITING_CURSOR_FILE

    status_msg = await update.message.reply_html(
        f"{pe(E['loading'])} Processing file..."
    )

    try:
        file = await document.get_file()
        content = await file.download_as_bytearray()
        text = content.decode('utf-8', errors='ignore')

        cookies = cursor_parse_cookies(text)
        if not cookies:
            await status_msg.edit_text(
                f"{pe(E['cross'])} No Cursor cookies found.",
                reply_markup=cursor_back_button()
            )
            return ConversationHandler.END

        total = len(cookies)
        pro_list = []
        free = 0
        dead = 0
        last = None

        for i, ck in enumerate(cookies, 1):
            result = cursor_check_cookie(ck)
            result['filename'] = document.file_name or 'file'
            if result["status"] == "PRO":
                pro_list.append(result)
                last = result
                await update.message.reply_html(cursor_fmt_pro(result))
            elif result["status"] == "FREE":
                free += 1
            else:
                dead += 1

            if i % 5 == 0 or i == total:
                try:
                    await status_msg.edit_text(
                        cursor_fmt_progress(i, total, len(pro_list), free, dead, last),
                        reply_markup=cursor_back_button()
                    )
                except Exception:
                    pass

        if pro_list:
            buf = BytesIO()
            for i, hit in enumerate(pro_list, 1):
                buf.write(f"========== CURSOR PRO #{i} ==========\n".encode())
                buf.write(f"Email : {hit.get('email', 'N/A')}\n".encode())
                buf.write(f"Name  : {hit.get('name', 'N/A')}\n".encode())
                buf.write(f"Plan  : {hit.get('plan', 'N/A')}\n".encode())
                buf.write(f"Tier  : {hit.get('tier', 'N/A')}\n\n".encode())
                buf.write(f"Token : {hit.get('full_token', '')}\n\n".encode())
            buf.seek(0)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            await update.message.reply_document(
                InputFile(buf, filename=f"cursor_pro_{ts}.txt"),
                caption=f"{pe(CURSOR_EMOJI)} {len(pro_list)} Pro accounts found!"
            )
            update_bot_stats(True)
        else:
            update_bot_stats(False)

        await status_msg.edit_text(
            cursor_fmt_summary(total, len(pro_list), free, dead),
            reply_markup=cursor_back_button()
        )

    except Exception as e:
        await status_msg.edit_text(
            f"{pe(E['cross'])} Error: {str(e)[:200]}",
            reply_markup=cursor_back_button()
        )
        update_bot_stats(False)

    return ConversationHandler.END