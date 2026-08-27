# ============================================================
# NETFLIX NF TOKEN GENERATOR SERVICE
# ============================================================

import os
import re
import json
import zipfile
import tempfile
import requests
from io import BytesIO
from datetime import datetime
from typing import Optional, Dict, Tuple, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from telegram import Update, InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from config import E
from utils import pe, update_bot_stats


# ─── Constants ──────────────────────────────────────────────

WAITING_NETFLIX_TOKEN_FILE = 3

NFTOKEN_API_URL = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
NFTOKEN_QUERY_PARAMS = {
    "appVersion": "15.48.1",
    "config": '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false","skOverlayTestEnabled":"false","homeFeedTestTVMovieListsEnabled":"false","baselineOnIpadEnabled":"true","trailersVideoIdLoggingFixEnabled":"true","postPlayPreviewsEnabled":"false","bypassContextualAssetsEnabled":"false","roarEnabled":"false","useSeason1AltLabelEnabled":"false","disableCDSSearchPaginationSectionKinds":["searchVideoCarousel"],"cdsSearchHorizontalPaginationEnabled":"true","searchPreQueryGamesEnabled":"true","kidsMyListEnabled":"true","billboardEnabled":"true","useCDSGalleryEnabled":"true","contentWarningEnabled":"true","videosInPopularGamesEnabled":"true","avifFormatEnabled":"false","sharksEnabled":"true"}',
    "device_type": "NFAPPL-02-",
    "esn": "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "idiom": "phone",
    "iosVersion": "15.8.5",
    "isTablet": "false",
    "languages": "en-US",
    "locale": "en-US",
    "maxDeviceWidth": "375",
    "model": "saget",
    "modelType": "IPHONE8-1",
    "odpAware": "true",
    "path": '["account","token","default"]',
    "pathFormat": "graph",
    "pixelDensity": "2.0",
    "progressive": "false",
    "responseFormat": "json",
}

NFTOKEN_HEADERS = {
    "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
    "x-netflix.request.attempt": "1",
    "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
    "x-netflix.context.app-version": "15.48.1",
    "x-netflix.argo.translated": "true",
    "x-netflix.context.form-factor": "phone",
    "x-netflix.context.sdk-version": "2012.4",
    "x-netflix.client.appversion": "15.48.1",
    "x-netflix.context.max-device-width": "375",
    "x-netflix.context.ab-tests": "",
    "x-netflix.tracing.cl.useractionid": "4DC655F2-9C3C-4343-8229-CA1B003C3053",
    "x-netflix.client.type": "argo",
    "x-netflix.client.ftl.esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "x-netflix.context.locales": "en-US",
    "x-netflix.context.top-level-uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.client.iosversion": "15.8.5",
    "accept-language": "en-US;q=1",
    "x-netflix.argo.abtests": "",
    "x-netflix.context.os-version": "15.8.5",
    "x-netflix.request.client.context": '{"appState":"foreground"}',
    "x-netflix.context.ui-flavor": "argo",
    "x-netflix.argo.nfnsm": "9",
    "x-netflix.context.pixel-density": "2.0",
    "x-netflix.request.toplevel.uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.request.client.timezoneid": "Asia/Dhaka",
}


# ─── Core Functions ─────────────────────────────────────────

def parse_cookie_file_netflix(content: str) -> List[Tuple[str, dict]]:
    from services.netflix_check import parse_cookie_file_netflix
    return parse_cookie_file_netflix(content)


def generate_nftoken(cookie_dict: dict) -> Tuple[Optional[dict], Optional[str]]:
    netflix_id = cookie_dict.get('NetflixId')
    if not netflix_id:
        return None, "No NetflixId"

    headers = dict(NFTOKEN_HEADERS)
    headers["Cookie"] = f"NetflixId={netflix_id}"

    try:
        r = requests.get(NFTOKEN_API_URL, params=NFTOKEN_QUERY_PARAMS, headers=headers, timeout=20, verify=False)
        r.raise_for_status()
        data = r.json()
        td = ((((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default") or {})
        token = td.get("token")
        expires = td.get("expires")
        if not token:
            return None, "Dead cookie"
        if isinstance(expires, int) and len(str(expires)) == 13:
            expires //= 1000
        expiry = datetime.fromtimestamp(expires).strftime("%Y-%m-%d %H:%M:%S UTC") if expires else "Unknown"
        return {'token': token, 'expires': expiry, 'expires_unix': expires}, None
    except Exception as e:
        return None, str(e)


# ─── Helper Functions ────────────────────────────────────────

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


# ─── Handler ─────────────────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the Netflix token generator conversation."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"{pe(E['globe'])} <b>Netflix NF Token Generator</b>\n\n"
        f"{pe(E['next'])} Upload a <b>.txt</b>, <b>.json</b>, or <b>.zip</b> file\n"
        f"{pe(E['bolt'])} containing Netflix cookies.\n\n"
        f"{pe(E['sparkle'])} I will generate NF tokens for each account.",
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    return WAITING_NETFLIX_TOKEN_FILE


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle uploaded file and generate NF tokens."""
    document = update.message.document
    if not document:
        await update.message.reply_html(
            f"{pe(E['cross'])} Please upload a file.",
            reply_markup=cancel_button()
        )
        return WAITING_NETFLIX_TOKEN_FILE

    status_msg = await update.message.reply_html(
        f"{pe(E['loading'])} Processing file..."
    )

    try:
        file = await document.get_file()
        content = await file.download_as_bytearray()
        text = content.decode('utf-8', errors='ignore')

        all_cookies = []

        if document.file_name.lower().endswith('.zip'):
            with tempfile.TemporaryDirectory() as td:
                zip_path = os.path.join(td, document.file_name)
                with open(zip_path, 'wb') as f:
                    f.write(content)
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    for name in zf.namelist():
                        if name.endswith('/') or name.startswith('__MACOSX'):
                            continue
                        try:
                            c = zf.read(name).decode('utf-8', errors='ignore')
                            parsed = parse_cookie_file_netflix(c)
                            for _, cd in parsed:
                                if cd.get('NetflixId'):
                                    all_cookies.append(cd)
                        except:
                            pass
        else:
            parsed = parse_cookie_file_netflix(text)
            all_cookies = [cd for _, cd in parsed if cd.get('NetflixId')]

        if not all_cookies:
            await status_msg.edit_text(
                f"{pe(E['cross'])} No valid Netflix cookies found.",
                reply_markup=back_button()
            )
            return ConversationHandler.END

        await status_msg.edit_text(
            f"{pe(E['loading'])} Generating tokens for <b>{len(all_cookies)}</b> cookies..."
        )

        tokens = []
        failed = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(generate_nftoken, cd) for cd in all_cookies]
            for future in as_completed(futures):
                result, error = future.result()
                if result:
                    tokens.append(result)
                else:
                    failed.append(error or "Unknown")

        if tokens:
            buf = BytesIO()
            for i, token in enumerate(tokens, 1):
                buf.write(f"========== TOKEN #{i} ==========\n".encode())
                buf.write(f"Token: {token.get('token', 'N/A')}\n".encode())
                buf.write(f"Expires: {token.get('expires', 'N/A')}\n".encode())
                buf.write(f"\n📱 Phone: https://www.netflix.com/unsupported?nftoken={token.get('token', '')}\n".encode())
                buf.write(f"🖥️ Desktop: https://www.netflix.com/browse?nftoken={token.get('token', '')}\n".encode())
                buf.write(b"\n")
            buf.seek(0)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            await status_msg.edit_text(
                f"{pe(E['check'])} <b>Done!</b>\n\n"
                f"{pe(E['gem'])} <b>Tokens Generated:</b> {len(tokens)}\n"
                f"{pe(E['cross'])} <b>Failed:</b> {len(failed)}\n\n"
                f"{pe(E['bolt'])} Sending results...",
                reply_markup=back_button()
            )

            await update.message.reply_document(
                InputFile(buf, filename=f"netflix_tokens_{timestamp}.txt"),
                caption=f"{pe(E['gem'])} {len(tokens)} NF tokens generated!"
            )
            update_bot_stats(True)
        else:
            await status_msg.edit_text(
                f"{pe(E['cross'])} <b>No tokens generated.</b>\n\n"
                f"{pe(E['cross'])} Failed: {len(failed)}",
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