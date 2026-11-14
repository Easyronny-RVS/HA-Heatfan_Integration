"""Constanten voor de Heatfan-integratie."""
import json
from datetime import timedelta
from pathlib import Path

DOMAIN = "heatfan"

# Tekst op de apparaatpagina: Home Assistant toont dit als "by <MANUFACTURER>".
MANUFACTURER = "RVS for Heatfan (Unofficial and Vendor-unsupported)"

# Publieke client-configuratie van de Heatfan-app (Firebase).
API_KEY = "AIzaSyAviJOJdriDmOKJQtumhky632Cj8-9tyuc"
DB_URL = "https://heatfan-database-default-rtdb.europe-west1.firebasedatabase.app"
ROOT = "heatfan-controller-dc/live-data"

SCAN_INTERVAL = timedelta(seconds=30)

# Modus 1-5 zijn de automatische standen, modus 6 is boost/koelen.
MODES = ["1", "2", "3", "4", "5", "6"]

# Instelbereik zoals in de app: temperatuur 1-100 graden, snelheid 1-10.
TEMP_RANGE = (1, 100)
SPEED_RANGE = (1, 10)

# Eigen Lovelace-kaart met twee schuifregelaars (wordt automatisch geladen).
URL_BASE = "/heatfan_static"
CARD_FILE = "heatfan-card.js"
SERVICE_SET_CURVE = "set_curve"
try:
    CARD_VERSION = json.loads((Path(__file__).parent / "manifest.json").read_text())["version"]
except (OSError, ValueError, KeyError):
    CARD_VERSION = "0"
