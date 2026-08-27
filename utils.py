# ============================================================
# UTILITIES - Shared helper functions
# ============================================================

import os
import re
import json
import time
import uuid
import codecs
import html as html_mod
import random
import string
import glob
from datetime import datetime
from typing import Optional, Dict, Tuple, List, Any
from config import E, R, COOKIES_FOLDER, HITS_FOLDER, JIO_COOKIE_USAGE_FILE


def pe(emoji_id: str) -> str:
    """Wrap a custom emoji ID into Telegram's premium emoji HTML tag."""
    return f'<tg-emoji emoji-id="{emoji_id}">⚡</tg-emoji>'


def safe_filename(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', name)


def clean_unicode(val: Any) -> str:
    if not isinstance(val, str):
        return str(val) if val else "Unknown"
    try:
        val = codecs.decode(val, 'unicode_escape')
    except:
        pass
    try:
        val = html_mod.unescape(val)
    except:
        pass
    val = val.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
    val = ''.join(c for c in val if ord(c) >= 32 or c in '\n\r\t')
    return val


def safe_html(text: Any) -> str:
    if not text:
        return "Unknown"
    text = clean_unicode(str(text))
    text = text.encode('ascii', errors='replace').decode('ascii', errors='replace')
    return text


def dict_to_netscape(cookie_dict: dict, domain: str = ".netflix.com") -> str:
    expiry = int(time.time()) + 180 * 24 * 3600
    lines = ["# Netscape HTTP Cookie File"]
    for k, v in cookie_dict.items():
        lines.append(f"{domain}\tTRUE\t/\tFALSE\t{expiry}\t{k}\t{v}")
    return "\n".join(lines)


def parse_netscape_cookie(content: str) -> dict:
    cookies = {}
    for line in content.strip().split('\n'):
        line = line.strip()
        if line.startswith('#') or not line:
            continue
        parts = line.split('\t')
        if len(parts) >= 7:
            cookies[parts[5]] = parts[6]
    return cookies


def parse_json_cookie(content: str) -> dict:
    try:
        data = json.loads(content)
        cookies = {}
        if isinstance(data, dict):
            for k, v in data.items():
                cookies[k] = str(v)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and 'name' in item and 'value' in item:
                    cookies[item['name']] = item['value']
        return cookies
    except:
        return {}


def extract_cookie_dict(content: str) -> Optional[dict]:
    content = content.strip()
    if content.startswith('{') or content.startswith('['):
        c = parse_json_cookie(content)
        if c and ('NetflixId' in c or 'SecureNetflixId' in c):
            return c
    c = parse_netscape_cookie(content)
    if c and ('NetflixId' in c or 'SecureNetflixId' in c):
        return c
    cookies = {}
    for line in content.split('\n'):
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            cookies[k.strip()] = v.strip()
    if cookies and ('NetflixId' in cookies or 'SecureNetflixId' in cookies):
        return cookies
    return None


def build_cookie_string(cookies: dict) -> str:
    return "; ".join([f"{k}={v}" for k, v in cookies.items()])


def generate_request_id() -> str:
    return uuid.uuid4().hex[:32]


def generate_toplevel_uuid() -> str:
    return str(uuid.uuid4())


# ─── Stats ──────────────────────────────────────────────────

STATS_FILE = "bot_stats.json"


def load_bot_stats() -> dict:
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {'total': 0, 'successful': 0, 'failed': 0, 'last': 'Never'}


def save_bot_stats(stats: dict):
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
    except:
        pass


def update_bot_stats(success: bool = True):
    stats = load_bot_stats()
    stats['total'] += 1
    if success:
        stats['successful'] += 1
    else:
        stats['failed'] += 1
    stats['last'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_bot_stats(stats)


# ─── JioHotstar Cookie Usage ───────────────────────────────

def jio_load_cookie_usage() -> dict:
    try:
        if os.path.exists(JIO_COOKIE_USAGE_FILE):
            with open(JIO_COOKIE_USAGE_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}


def jio_save_cookie_usage(usage: dict):
    try:
        with open(JIO_COOKIE_USAGE_FILE, 'w') as f:
            json.dump(usage, f, indent=2)
    except:
        pass


def jio_get_cookie_usage_count(cookie_name: str) -> int:
    usage = jio_load_cookie_usage()
    return usage.get(cookie_name, 0)


def jio_increment_cookie_usage(cookie_name: str) -> int:
    usage = jio_load_cookie_usage()
    usage[cookie_name] = usage.get(cookie_name, 0) + 1
    jio_save_cookie_usage(usage)
    return usage[cookie_name]


def jio_delete_cookie_file(filepath: str) -> bool:
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
    except:
        pass
    return False


def jio_get_random_cookie() -> Tuple[Optional[dict], Optional[str]]:
    cookie_files = glob.glob(f"{COOKIES_FOLDER}/*.txt")

    if not cookie_files:
        return None, "No cookie files found in vault"

    available_cookies = []
    for filepath in cookie_files:
        filename = os.path.basename(filepath)
        usage_count = jio_get_cookie_usage_count(filename)
        if usage_count < 3:
            available_cookies.append(filepath)

    if not available_cookies:
        return None, "All cookies have reached maximum usage limit (3 uses). Please upload more cookies."

    random.shuffle(available_cookies)
    filepath = available_cookies[0]
    filename = os.path.basename(filepath)

    cookie_str, token, device_id, cookies = jio_parse_cookie_file(filepath)

    if not cookie_str:
        return None, f"Failed to parse {filename}"

    name = filename.replace('.txt', '').split('_')[0] if '_' in filename else filename.replace('.txt', '')

    return {
        'name': name,
        'cookie_str': cookie_str,
        'token': token,
        'device_id': device_id,
        'filepath': filepath,
        'filename': filename,
        'cookies': cookies
    }, None


def jio_parse_cookie_file(filepath: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[dict]]:
    cookies = {}
    session_token = None
    user_up_token = None
    device_id = None
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 7:
                    name = parts[5]
                    value = parts[6]
                    cookies[name] = value
                    if name == 'sessionUserUP':
                        session_token = value
                    elif name == 'userUP':
                        user_up_token = value
                    elif name == 'deviceId':
                        device_id = value
    except:
        pass
    cookie_str = '; '.join([f"{k}={v}" for k, v in cookies.items()])
    return cookie_str, session_token or user_up_token, device_id, cookies