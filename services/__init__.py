# ============================================================
# SERVICES INIT - Import all service modules
# All constants are defined directly here to avoid circular imports
# ============================================================

from . import netflix_trial
from . import netflix_check
from . import netflix_token
from . import surfshark
from . import spotify
from . import hbomax
from . import crunchyroll
from . import jiohotstar

# Define all constants here directly
WAITING_EMAIL = 1
WAITING_NETFLIX_FILE = 2
WAITING_NETFLIX_TOKEN_FILE = 3
WAITING_SURFSHARK_CODE = 4
WAITING_SPOTIFY_CODE = 5
WAITING_HBO_CODE = 6
WAITING_CRUNCHYROLL_CREDS = 7
WAITING_JIO_QR = 8

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