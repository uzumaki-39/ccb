# ============================================================
# SPOTIFY TV ACTIVATOR SERVICE
# ============================================================

import os
import re
import glob
import random
import uuid
import time
import requests
from typing import Optional, Dict, Tuple

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from config import E, COOKIES_FOLDER
from utils import pe, extract_cookie_dict, update_bot_stats


# ─── Constants ──────────────────────────────────────────────

WAITING_SPOTIFY_CODE = 5


# ─── Core Functions ─────────────────────────────────────────

def spotify_get_account_info(cookies: dict) -> Optional[Dict]:
    try:
        url = "https://www.spotify.com/eg-ar/account/subscription/manage/"
        headers = {
            'host': 'www.spotify.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9,ar;q=0.8,ru;q=0.7',
            'cache-control': 'max-age=0',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, cookies=cookies, allow_redirects=True, timeout=30)
        if response.status_code != 200:
            return None

        if "Don't have an account" in response.text or "إدارة اشتراكك" in response.text:
            pattern = r'"planNameLong":"([^"]*?)","planNameGpb"'
            match = re.search(pattern, response.text)
            plan = match.group(1) if match else "Unknown"

            email_pattern = r'"email":"([^"]+)"'
            email_match = re.search(email_pattern, response.text)
            email = email_match.group(1) if email_match else None

            country_pattern = r'"country":"([^"]+)"'
            country_match = re.search(country_pattern, response.text)
            country = country_match.group(1) if country_match else "Unknown"

            is_premium = "Premium" in plan or "باقة" in plan or "Family" in plan or "Duo" in plan

            return {
                'plan': plan,
                'email': email,
                'country': country,
                'is_premium': is_premium
            }
        return None
    except:
        return None


def spotify_get_csrf_token(cookies: dict) -> Tuple[Optional[str], Optional[str], Optional[dict]]:
    try:
        session = requests.Session()
        session.cookies.update(cookies)

        flow_ctx = f"{uuid.uuid4()}%3A{int(time.time())}"
        url = f"https://accounts.spotify.com/en/link/v2?flow_ctx={flow_ctx}"

        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9,ar;q=0.8,ru;q=0.7',
            'cache-control': 'max-age=0',
            'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            'referer': 'https://www.spotify.com/'
        }

        response = session.get(url, headers=headers, allow_redirects=True, timeout=30)
        if response.status_code != 200:
            return None, None, None

        html = response.text
        csrf_token = None
        pattern = r'initialToken":"([^"]+)"'
        match = re.search(pattern, html)
        if match:
            csrf_token = match.group(1)

        flow_pattern = r'flow_ctx=([^"\s&]+)'
        flow_match = re.search(flow_pattern, html)
        flow_ctx = flow_match.group(1) if flow_match else flow_ctx

        updated_cookies = cookies.copy()
        for cookie in session.cookies:
            updated_cookies[cookie.name] = cookie.value

        return csrf_token, flow_ctx, updated_cookies
    except:
        return None, None, None


def spotify_activate_tv(cookies: dict, code: str, csrf: str, flow: str) -> Tuple[bool, str, Optional[str]]:
    try:
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,ar;q=0.8,ru;q=0.7',
            'content-type': 'application/json',
            'origin': 'https://accounts.spotify.com',
            'referer': f'https://accounts.spotify.com/en/link/v2?flow_ctx={flow}',
            'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36'
        }
        if csrf:
            headers['x-csrf-token'] = csrf

        # Step 1: Submit
        r1 = requests.post(
            f"https://accounts.spotify.com/pair/api/code?flow_ctx={flow}",
            headers=headers,
            cookies=cookies,
            json={"code": code.upper()},
            timeout=30
        )
        if r1.status_code != 200:
            return False, "error", None

        data = r1.json()
        if data.get('result') == 'invalid':
            return False, "invalid", None
        if data.get('result') != 'ok':
            return False, "error", None

        tv_name = data.get('codeInfo', {}).get('authorizationInfo', {}).get('clientInfo', {}).get('name', 'Unknown TV')

        # Step 2: Resolve
        r2 = requests.post(
            f"https://accounts.spotify.com/pair/api/resolve?flow_ctx={flow}",
            headers=headers,
            cookies=cookies,
            json={"code": code.upper()},
            timeout=30
        )
        if r2.status_code != 200:
            return False, "error", tv_name

        result = r2.json().get('result', '')
        if result in ['ok', 'success']:
            return True, "success", tv_name

        return False, "error", tv_name
    except Exception as e:
        return False, "error", None


# ─── Handler ─────────────────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the Spotify TV activator conversation."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"{pe(E['globe'])} <b>Spotify TV Activator</b>\n\n"
        f"{pe(E['next'])} Send me the 6-digit TV code\n"
        f"{pe(E['bolt'])} from your Spotify TV screen.\n\n"
        f"{pe(E['warn'])} I will find a premium account and activate.",
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    return WAITING_SPOTIFY_CODE


async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle TV code and activate Spotify."""
    code = update.message.text.strip().upper()
    if len(code) != 6 or not code.isalnum():
        await update.message.reply_html(
            f"{pe(E['cross'])} Invalid code. Please send a 6-digit alphanumeric code.",
            reply_markup=cancel_button()
        )
        return WAITING_SPOTIFY_CODE

    status_msg = await update.message.reply_html(
        f"{pe(E['loading'])} Finding premium account..."
    )

    cookie_files = glob.glob(f"{COOKIES_FOLDER}/*.txt")
    random.shuffle(cookie_files)

    success = False
    info = None

    for filepath in cookie_files:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            cookies = extract_cookie_dict(content)
            if not cookies:
                continue

            account_info = spotify_get_account_info(cookies)
            if account_info and account_info.get('is_premium'):
                csrf, flow, updated_cookies = spotify_get_csrf_token(cookies)
                if csrf and flow:
                    ok, status, tv_name = spotify_activate_tv(updated_cookies, code, csrf, flow)
                    if ok:
                        success = True
                        info = {
                            'email': account_info.get('email', 'Unknown'),
                            'plan': account_info.get('plan', 'Unknown'),
                            'country': account_info.get('country', 'Unknown'),
                            'tv_name': tv_name or 'Unknown TV'
                        }
                        break
        except:
            continue

    if success:
        await status_msg.edit_text(
            f"{pe(E['check'])} <b>TV Activated!</b>\n\n"
            f"{pe(E['bolt'])} <b>Email:</b> {info.get('email', 'Unknown')}\n"
            f"{pe(E['star'])} <b>Plan:</b> {info.get('plan', 'Unknown')}\n"
            f"{pe(E['globe'])} <b>Country:</b> {info.get('country', 'Unknown')}\n"
            f"{pe(E['gem'])} <b>TV:</b> {info.get('tv_name', 'Unknown TV')}\n\n"
            f"{pe(E['sparkle'])} Your TV is now ready!",
            reply_markup=back_button()
        )
        update_bot_stats(True)
    else:
        await status_msg.edit_text(
            f"{pe(E['cross'])} <b>Activation Failed.</b>\n\n"
            f"{pe(E['warn'])} Invalid code or no premium account found.",
            reply_markup=back_button()
        )
        update_bot_stats(False)

    return ConversationHandler.END


def cancel_button():
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    from config import E
    from utils import pe
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"{pe(E['cross'])} Cancel",
            callback_data="main_menu",
            icon_custom_emoji_id=E['cross']
        )]
    ])


def back_button():
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    from config import E
    from utils import pe
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"{pe(E['prev'])} Back",
            callback_data="main_menu",
            icon_custom_emoji_id=E['prev']
        )]
    ])