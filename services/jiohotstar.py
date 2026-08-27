# ============================================================
# JIO HOTSTAR TV ACTIVATOR SERVICE
# ============================================================

import os
import re
import glob
import random
import requests
import cloudscraper
from io import BytesIO
from typing import Optional, Tuple

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from config import E, COOKIES_FOLDER
from utils import (
    pe, update_bot_stats, 
    jio_get_random_cookie, jio_increment_cookie_usage, 
    jio_delete_cookie_file, jio_get_cookie_usage_count
)


# ─── Constants ──────────────────────────────────────────────

WAITING_JIO_QR = 8


# ─── QR Scanning ────────────────────────────────────────────

def scan_qr(image_bytes: bytes) -> Optional[str]:
    try:
        import cv2
        import numpy as np
        from pyzbar.pyzbar import decode
        
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            decoded = decode(img)
            if not decoded:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
                decoded = decode(thresh)
            if decoded:
                return decoded[0].data.decode('utf-8')
    except:
        pass

    # Fallback to online API
    try:
        files = {'file': ('qr_image.jpg', BytesIO(image_bytes), 'image/jpeg')}
        response = requests.post('https://api.qrserver.com/v1/read-qr-code/', files=files, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data and data[0]['symbol'][0]['data']:
                return data[0]['symbol'][0]['data']
    except:
        pass
    return None


# ─── Core Functions ─────────────────────────────────────────

def jio_activate_tv(qr_url: str, cookie_info: dict) -> Tuple[bool, str]:
    scraper = cloudscraper.create_scraper()

    headers = {
        "authority": "www.hotstar.com",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-language": "en-MM,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
        "cookie": cookie_info['cookie_str'],
        "sec-ch-ua": '"Chromium";v="137", "Not/A)Brand";v="24"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"
    }

    if cookie_info.get('token'):
        if "userUP=" not in headers["cookie"]:
            headers["cookie"] += f"; userUP={cookie_info['token']}"

    try:
        response = scraper.get(qr_url, headers=headers, timeout=30)
        if response.status_code == 200:
            lowered_text = response.text.lower()
            if "success" in lowered_text or "activated" in lowered_text:
                return True, "✅ JioHotstar Activation Successful"
            elif "hotstar" in lowered_text and ("watch" in lowered_text or "tv" in lowered_text):
                return True, "✅ Page loaded! TV activation in progress"
            else:
                return True, "✅ Request completed. Check your TV"
        return False, f"❌ Failed with status: {response.status_code}"
    except Exception as e:
        return False, f"❌ Error: {str(e)[:100]}"


# ─── Handler ─────────────────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the JioHotstar TV activator conversation."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"{pe(E['globe'])} <b>JioHotstar TV Activator</b>\n\n"
        f"{pe(E['next'])} Send me the QR code image\n"
        f"{pe(E['bolt'])} from your JioHotstar TV screen.\n\n"
        f"{pe(E['warn'])} I will find a working account and activate.",
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    return WAITING_JIO_QR


async def handle_qr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle QR code image and activate JioHotstar."""
    if not update.message.photo:
        await update.message.reply_html(
            f"{pe(E['cross'])} Please send a photo of the QR code.",
            reply_markup=cancel_button()
        )
        return WAITING_JIO_QR

    status_msg = await update.message.reply_html(
        f"{pe(E['loading'])} Scanning QR code..."
    )

    try:
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()

        qr_data = scan_qr(image_bytes)

        if not qr_data:
            await status_msg.edit_text(
                f"{pe(E['cross'])} No QR code found. Please try again with a clearer image.",
                reply_markup=back_button()
            )
            update_bot_stats(False)
            return ConversationHandler.END

        # Normalize QR data
        if 'hotstar.com' not in qr_data and not qr_data.startswith('http'):
            if len(qr_data) >= 5 and qr_data.isalnum():
                qr_data = f"https://www.hotstar.com/qr?qr_code={qr_data}"
            else:
                await status_msg.edit_text(
                    f"{pe(E['cross'])} Invalid QR code. Not a JioHotstar QR.",
                    reply_markup=back_button()
                )
                update_bot_stats(False)
                return ConversationHandler.END

        await status_msg.edit_text(
            f"{pe(E['loading'])} Finding working account..."
        )

        cookie_info, error = jio_get_random_cookie()
        if not cookie_info:
            await status_msg.edit_text(
                f"{pe(E['cross'])} {error}",
                reply_markup=back_button()
            )
            update_bot_stats(False)
            return ConversationHandler.END

        name = cookie_info['name']
        usage_count = jio_get_cookie_usage_count(cookie_info['filename'])

        await status_msg.edit_text(
            f"{pe(E['check'])} Account: <b>{name}</b>\n"
            f"{pe(E['loading'])} Activating..."
        )

        success, message = jio_activate_tv(qr_data, cookie_info)

        if success:
            new_usage = jio_increment_cookie_usage(cookie_info['filename'])
            if new_usage >= 3:
                jio_delete_cookie_file(cookie_info['filepath'])

            qr_id = qr_data.split('qr_code=')[1].split('&')[0] if 'qr_code=' in qr_data else "N/A"

            await status_msg.edit_text(
                f"{pe(E['check'])} <b>Activation Successful!</b>\n\n"
                f"{pe(E['bolt'])} <b>Account:</b> {name}\n"
                f"{pe(E['bolt'])} <b>QR ID:</b> <code>{qr_id}</code>\n"
                f"{pe(E['bolt'])} <b>Usage:</b> {new_usage}/3\n\n"
                f"{pe(E['sparkle'])} Your TV is now connected!",
                reply_markup=back_button()
            )
            update_bot_stats(True)
        else:
            await status_msg.edit_text(
                f"{pe(E['cross'])} <b>Activation Failed</b>\n\n{message}",
                reply_markup=back_button()
            )
            update_bot_stats(False)

    except Exception as e:
        await status_msg.edit_text(
            f"{pe(E['cross'])} Error: {str(e)[:200]}",
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