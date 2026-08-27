# ============================================================
# CONFIGURATION - Master Streaming Bot
# All tokens, IDs, emojis, and constants in one place
# ============================================================

import os

# ─── Bot Token ──────────────────────────────────────────────
TOKEN = "8901668516:AAGrIt__UkH6gEGLQos6iHxv13yp6AVkFkw"
OWNER_ID = 8206978592
ADMIN_IDS = [8206978592]

# ─── Folders ─────────────────────────────────────────────────
COOKIES_FOLDER = "cookies"
HITS_FOLDER = "hits"
VAULT_FOLDER = "vault"
OUTPUT_FOLDER = ".cache"

# Create folders if they don't exist
for folder in [COOKIES_FOLDER, HITS_FOLDER, VAULT_FOLDER, OUTPUT_FOLDER]:
    os.makedirs(folder, exist_ok=True)

WATERMARK = "Made By @NotYoursNaruto"

# ─── Premium Emoji Map ──────────────────────────────────────
E = {
    "bolt":      "5084974483685507801",
    "bolt2":     "5136449172806828766",
    "bolt3":     "5345941618623005800",
    "bolt4":     "5348503265967355284",
    "bolt5":     "5350298742685710886",
    "check":     "5278622189556354905",
    "check2":    "5895671830210940904",
    "check3":    "5197288647275071607",
    "cross":     "5042112436648281096",
    "cross2":    "5447644880824181073",
    "cross3":    "5121063440311386962",
    "cross4":    "6023909739669229757",
    "star":      "5980995951160987855",
    "gem":       "5226656353744862682",
    "globe":     "5134452506935427991",
    "link":      "5042101437237036298",
    "chat":      "5303138782004924588",
    "chat2":     "5040036030414062506",
    "link2":     "5201691993775818138",
    "user":      "5321304384838057247",
    "warn":      "5855207143724027916",
    "warn2":     "6008233706039284019",
    "rocket":    "5195033767969839232",
    "sparkle":   "5172739056592749710",
    "hourglass": "5215327832040811010",
    "plus":      "5253652327734192243",
    "dice":      "5361696340348779794",
    "refresh":   "5852670420074893746",
    "bank":      "5854784287013867183",
    "gift":      "6025929752982852543",
    "stop":      "6114014038960638990",
    "loading":   "5325834523068342417",
    "prev":      "4902349923049014048",
    "next":      "4902715076873553054",
    "help_prev": "5246943906645428644",
    "help_next": "5462965076413656490",
}

R = {
    "cc":         "5472250091332993630",
    "gate":       "6321225560789877992",
    "price":      "5039789890133296083",
    "bin_info":   "5775903905498010383",
    "visa":       "5298970748172385213",
    "master":     "5355269226732995665",
    "amex":       "4983234121556820510",
    "type":       "5350396951407895212",
    "level":      "5784914081165087232",
    "bank":       "5332455502917949981",
    "country":    "5285452600601237916",
    "checked_by": "5958417144877160497",
}

# ─── Service Names ──────────────────────────────────────────
SERVICES = {
    "netflix_trial": "Netflix Trial Offer",
    "netflix_check": "Netflix Account Checker",
    "netflix_token": "Netflix NF Token",
    "surfshark": "Surfshark Auto-Login",
    "spotify": "Spotify TV Activator",
    "hbomax": "HBO Max TV Activator",
    "crunchyroll": "Crunchyroll Checker",
    "jiohotstar": "JioHotstar TV Activator",
}

# ─── Stats File ─────────────────────────────────────────────
STATS_FILE = "bot_stats.json"
JIO_COOKIE_USAGE_FILE = "cookie_usage.json"