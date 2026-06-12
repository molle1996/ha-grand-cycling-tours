"""Constants for Grand Cycling Tours integration."""

DOMAIN = "grand_cycling_tours"
PLATFORMS = ["sensor"]

# Race identifiers
RACE_TDF = "tour-de-france"
RACE_GIRO = "giro-d-italia"
RACE_VUELTA = "vuelta-a-espana"

RACE_NAMES = {
    RACE_TDF: "Tour de France",
    RACE_GIRO: "Giro d'Italia",
    RACE_VUELTA: "Vuelta a España",
}

RACE_ICONS = {
    RACE_TDF: "mdi:flag-variant",
    RACE_GIRO: "mdi:flag-variant",
    RACE_VUELTA: "mdi:flag-variant",
}

# Jersey colours for GC / points / mountain / youth
JERSEY_ICONS = {
    "gc": "mdi:tshirt-crew",
    "points": "mdi:tshirt-crew",
    "mountain": "mdi:tshirt-crew",
    "youth": "mdi:tshirt-crew",
}

# PCS base URL
PCS_BASE = "https://www.procyclingstats.com"

# Race-specific URLs (slug/year)
def pcs_race_url(race_slug: str, year: int) -> str:
    return f"{PCS_BASE}/race/{race_slug}/{year}"

def pcs_stage_url(race_slug: str, year: int, stage_num: int) -> str:
    return f"{PCS_BASE}/race/{race_slug}/{year}/stage-{stage_num}"

# Default scan interval in minutes
DEFAULT_SCAN_INTERVAL = 15

# Config keys
CONF_RACES = "races"
CONF_SCAN_INTERVAL = "scan_interval"

# Sensor types
SENSOR_GC = "gc"
SENSOR_STAGE_WINNER = "stage_winner"
SENSOR_NEXT_STAGE = "next_stage"
SENSOR_CURRENT_STAGE = "current_stage"
SENSOR_POINTS = "points"
SENSOR_MOUNTAIN = "mountain"
SENSOR_YOUTH = "youth"
SENSOR_RACE_STATUS = "race_status"
SENSOR_STAGE_LIST = "stage_list"
SENSOR_TOP5 = "gc_top5"
