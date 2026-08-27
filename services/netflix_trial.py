# ============================================================
# NETFLIX TRIAL OFFER SERVICE
# ============================================================

import re
import json
import requests
import uuid
from typing import Tuple, Optional, Dict
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from config import E
from utils import (
    pe, build_cookie_string, extract_cookie_dict, 
    generate_request_id, generate_toplevel_uuid, update_bot_stats
)


# ─── Constants ──────────────────────────────────────────────

_NETFLIX_SRV = "http://85.115.209.225:3739"
_NETFLIX_APIKEY = "NetflixCookie2026!@#"


# ─── Core Functions ─────────────────────────────────────────

def netflix_get_cookies() -> Optional[dict]:
    """Get fresh Netflix cookies from the API."""
    try:
        headers = {"X-API-Key": _NETFLIX_APIKEY}
        response = requests.get(f"{_NETFLIX_SRV}/get-cookie", headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if 'cookies' in data:
                cookie_dict = extract_cookie_dict(data['cookies'])
                if cookie_dict:
                    return cookie_dict
        return None
    except Exception as e:
        return None


def extract_flwssn(cookie_string: str) -> str:
    match = re.search(r'flwssn=([^;]+)', cookie_string)
    return match.group(1) if match else str(uuid.uuid4())


def netflix_send_trial_offer(email: str, cookie_dict: dict) -> Tuple[dict, bool]:
    """Send 30-day trial offer to email."""
    cookie_string = build_cookie_string(cookie_dict)
    flwssn = extract_flwssn(cookie_string)
    
    results = {}
    
    # Step 1: Init Signup
    try:
        headers = {
            'authority': 'web.prod.cloud.netflix.com',
            'accept': '*/*',
            'accept-language': 'en-MM,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
            'content-type': 'application/json',
            'cookie': cookie_string,
            'origin': 'https://www.netflix.com',
            'referer': 'https://www.netflix.com/',
            'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            'x-netflix.context.app-version': 'v38c5b0da',
            'x-netflix.context.form-factor': 'phone',
            'x-netflix.context.is-inapp-browser': 'false',
            'x-netflix.context.locales': 'en-in',
            'x-netflix.context.operation-name': 'CLCSWebInitSignup',
            'x-netflix.context.ui-flavor': 'akira',
            'x-netflix.request.attempt': '1',
            'x-netflix.request.clcs.bucket': 'high',
            'x-netflix.request.client.context': '{"appstate":"foreground"}',
            'x-netflix.request.id': generate_request_id(),
            'x-netflix.request.originating.url': 'https://www.netflix.com/in/',
            'x-netflix.request.toplevel.uuid': generate_toplevel_uuid()
        }

        data = {
            "operationName": "CLCSWebInitSignup",
            "variables": {
                "inputNode": "WELCOME",
                "locale": "en-IN",
                "inputFields": [
                    {"name": "flwssn", "value": {"stringValue": flwssn}},
                    {"name": "email", "value": {"stringValue": email}},
                    {"name": "recaptchaError", "value": {"stringValue": "LOAD_TIMED_OUT"}},
                    {"name": "recaptchaResponseTime", "value": {}},
                    {"name": "recaptchaSiteKey", "value": {"stringValue": "6LdqW_EqAAAAAO87Fb_kcZfNzs0IqJRcKiJDYpUv"}},
                    {"name": "recaptchaToken", "value": {}}
                ]
            },
            "extensions": {
                "persistedQuery": {
                    "id": "5d76d6a0-ccfe-4c31-b587-b4e1954732ca",
                    "version": 102
                }
            }
        }

        response = requests.post('https://web.prod.cloud.netflix.com/graphql',
                                 headers=headers, json=data, timeout=15)
        results['init'] = {'status': response.status_code}
        
        if response.status_code != 200:
            return results, False
    except:
        return results, False

    # Step 2: Screen Update
    try:
        headers = {
            'authority': 'web.prod.cloud.netflix.com',
            'accept': '*/*',
            'accept-language': 'en-MM,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
            'content-type': 'application/json',
            'cookie': cookie_string,
            'origin': 'https://www.netflix.com',
            'referer': 'https://www.netflix.com/signup',
            'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            'x-netflix.context.app-version': 'v38c5b0da',
            'x-netflix.context.form-factor': 'phone',
            'x-netflix.context.is-inapp-browser': 'false',
            'x-netflix.context.locales': 'en-in',
            'x-netflix.context.operation-name': 'CLCSScreenUpdate',
            'x-netflix.context.ui-flavor': 'akira',
            'x-netflix.request.attempt': '1',
            'x-netflix.request.clcs.bucket': 'high',
            'x-netflix.request.client.context': '{"appstate":"foreground"}',
            'x-netflix.request.id': generate_request_id(),
            'x-netflix.request.originating.url': 'https://www.netflix.com/signup',
            'x-netflix.request.toplevel.uuid': generate_toplevel_uuid()
        }

        data = {
            "operationName": "CLCSScreenUpdate",
            "variables": {
                "format": "HTML",
                "imageFormat": "PNG",
                "locale": "en-IN",
                "serverState": "Bgjru+vcAxLTAf/qOOEwXPLVxW+7Jod9WpjYuKN8j1qfhQpzCK4mmQts5eMSeaP+l7s6NKcNBO4rmYabFFCVnMpCH3ib4AicvXAKm30Z+s5W3Cst0D0BK5x/pwn3QmByi/OgGwU/fzaiR5oxSlZe4fKVexWHISkE4GMzJqLaaXQR0M73ynZB9idNBfqsz3RA5WJN+DGAbVUOZlWl8eZqffvQpp/5MGubeQFpdwKqkAx1nHh7/xI1i9tDU0KLgrvkZrbe6nQ1MX2nc9TBxqnVVxtc3ptHdqydP1wlIu0YBiIOCgydgLg1SvK6tSPOff8=",
                "serverScreenUpdate": "Bgjru+vcAxKSAjDnHOxlaIbFSbwaWzZo/REHFnNG7OtpcXdKTDlcL4/o+huGi/fNW+jrqNDqDSsv1iytiG/ZtvO9ierUE9M1Kc/yEj9JsSiG3XpPciFDzPd6psSaG68XLbos+Qie0wniXCtJyWDLDuLd9ayCMB8qGCxwbov6B41kCQY/zArwlecm0GNoJdd5jvZfBJVtytD6mMCYnPA/9zhX4okj+6IGet9xOCYt76IDiuyESxgKbaOLcd6DQIDSBf4m/lYi2Tasj7olPkCaDIXxjU+0UY+b7eDyhvi2if2vt6510ARrGsSZq8DaazQmrpAbfiCW47s1/1mR59vUMYeT8VCqqAvbNwipqyP1DQMHtoTnCoWns0+x6IgYBiIOCgx9EW4i3i9SUswnHEg=",
                "inputFields": [
                    {"name": "email", "value": {"stringValue": email}},
                    {"name": "pipcConsent", "value": {"booleanValue": False}}
                ]
            },
            "extensions": {
                "persistedQuery": {
                    "id": "0fd81de7-07af-4c7d-802f-0f4ea4181aa3",
                    "version": 102
                }
            }
        }

        response = requests.post('https://web.prod.cloud.netflix.com/graphql',
                                 headers=headers, json=data, timeout=15)
        results['update'] = {'status': response.status_code}
    except:
        pass

    # Step 3: Image request (confirmation)
    try:
        headers = {
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'en-MM,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Referer': 'https://www.netflix.com/',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"'
        }

        image_url = 'https://occ-0-6711-64.1.nflxso.net/dnm/api/v6/QqNdfvCShgtu-ra1rla_KxCcSSY/AAAAQAmpros-eVHttd-jyVbIiMTW885cisEwMOLTGkTzHQifWIkevLiCu24tEsptsw.png?r=bff'
        response = requests.get(image_url, headers=headers, timeout=10)
        results['image'] = {'status': response.status_code}
        
        if response.status_code == 200:
            return results, True
        return results, False
    except:
        return results, False


# ─── Handler ─────────────────────────────────────────────────

WAITING_EMAIL = 1


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the Netflix trial conversation."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"{pe(E['globe'])} <b>Netflix 30-Day Trial Offer</b>\n\n"
        f"{pe(E['next'])} Send me your email address.\n"
        f"{pe(E['warn'])} I will send the trial offer to your email.",
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    return WAITING_EMAIL


async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle email input and send trial offer."""
    email = update.message.text.strip()
    if '@' not in email:
        await update.message.reply_html(
            f"{pe(E['cross'])} Invalid email address. Please try again.",
            reply_markup=cancel_button()
        )
        return WAITING_EMAIL

    status_msg = await update.message.reply_html(
        f"{pe(E['loading'])} Sending trial offer to <b>{email}</b>..."
    )

    cookie_dict = netflix_get_cookies()
    if not cookie_dict:
        await status_msg.edit_text(
            f"{pe(E['cross'])} Failed to get cookies. Service unavailable.",
            reply_markup=back_button()
        )
        update_bot_stats(False)
        return ConversationHandler.END

    results, success = netflix_send_trial_offer(email, cookie_dict)

    if success:
        await status_msg.edit_text(
            f"{pe(E['check'])} <b>Success!</b>\n\n"
            f"{pe(E['bolt'])} Trial offer sent to <b>{email}</b>\n"
            f"{pe(E['sparkle'])} Check your inbox!",
            reply_markup=back_button()
        )
        update_bot_stats(True)
    else:
        await status_msg.edit_text(
            f"{pe(E['cross'])} <b>Failed</b>\n\n"
            f"{pe(E['warn'])} Unable to send trial offer. The service might be temporarily down.",
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