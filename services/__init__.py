# ============================================================
# SERVICES INIT - Import all service modules
# All constants are now properly defined and exported
# ============================================================

from . import netflix_trial
from . import netflix_check
from . import netflix_token
from . import surfshark
from . import spotify
from . import hbomax
from . import crunchyroll
from . import jiohotstar

# Export all constants for bot.py
WAITING_EMAIL = netflix_trial.WAITING_EMAIL
WAITING_NETFLIX_FILE = netflix_check.WAITING_NETFLIX_FILE
WAITING_NETFLIX_TOKEN_FILE = netflix_token.WAITING_NETFLIX_TOKEN_FILE
WAITING_SURFSHARK_CODE = surfshark.WAITING_SURFSHARK_CODE
WAITING_SPOTIFY_CODE = spotify.WAITING_SPOTIFY_CODE
WAITING_HBO_CODE = hbomax.WAITING_HBO_CODE
WAITING_CRUNCHYROLL_CREDS = crunchyroll.WAITING_CRUNCHYROLL_CREDS
WAITING_JIO_QR = jiohotstar.WAITING_JIO_QR

# Also export the modules themselves
__all__ = [
    'netflix_trial',
    'netflix_check',
    'netflix_token',
    'surfshark',
    'spotify',
    'hbomax',
    'crunchyroll',
    'jiohotstar',
    'WAITING_EMAIL',
    'WAITING_NETFLIX_FILE',
    'WAITING_NETFLIX_TOKEN_FILE',
    'WAITING_SURFSHARK_CODE',
    'WAITING_SPOTIFY_CODE',
    'WAITING_HBO_CODE',
    'WAITING_CRUNCHYROLL_CREDS',
    'WAITING_JIO_QR',
]