import os
from dotenv import load_dotenv

load_dotenv()

# ---------- Core ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_NAME = os.getenv("SHEET_NAME", "Railway_Equipment_Tracking_TKD")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# ---------- Google Sheets ----------
CREDENTIALS_FILE = "credentials.json"

SHEETS = {
    "LOCO_MASTER":      "loco_master",
    "EQUIPMENT_MASTER": "equipment_master",
    "LOCO_MESSAGES":    "loco_messages",
    "EQUIPMENT_HISTORY":"equipment_history",
    "DASHBOARD":        "dashboard_data",
    # ----- TSC Sheets -----
    "TSC_MASTER":           "tsc_master",
    "TSC_RECEIVE":          "tsc_receive_register",
    "TSC_ISSUE":            "tsc_issue_register",
    "TSC_REMOVAL":          "tsc_removal_register",
    "TSC_BLW_DISPATCH":     "tsc_blw_dispatch",
    "TSC_LOCO_RUNNING":     "tsc_loco_running",
    "TSC_PREMATURE_FAILURE":"tsc_premature_failure",
    "TSC_WAITING_DISPATCH": "tsc_waiting_dispatch",
}

# ---------- TSC Configuration ----------
TSC_WORKING_LIFE_YEARS: dict[str, int] = {
    "WDP4": 6,
    "WDG4": 8,
}
TSC_WARRANTY_YEARS = 2
TSC_PL_NUMBERS = {
    "OVERHAULING": "16080993",
    "WARRANTY":    "16080087",
}
TSC_COMMON_CAUSES = [
    "GIC Crack", "Abnormal Sound", "Jumper Bolt Broken", "Oil Throwing",
    "Blade Broken", "Gear Train Broken", "Idle Gear Play Lost",
    "Shaft Broken", "Block Crack", "Surging", "Clutch Defective",
    "Flange Crack", "Overdue", "6 YLY Schedule", "3 YLY Schedule",
    "12 YLY Schedule", "BAP Less", "Oil Seal Leakage", "Other",
]
# Alert thresholds (days before working life expiry)
TSC_ALERT_CRITICAL_DAYS = 90     # < 3 months = RED
TSC_ALERT_WARNING_DAYS  = 365    # < 1 year   = YELLOW


def detect_diesel_loco_type(loco_no: str) -> str | None:
    """
    Detect diesel loco type from its number.
    WDP4: 40xxx, 20xxx  →  6 year TSC life
    WDG4: 70xxx, 12xxx  →  8 year TSC life
    Returns None if loco number doesn't match known patterns.
    """
    if not loco_no:
        return None
    clean = str(loco_no).strip().split("/")[0].strip()
    if clean.startswith("40") or clean.startswith("20"):
        return "WDP4"
    elif clean.startswith("70") or clean.startswith("12"):
        return "WDG4"
    return None


def get_tsc_working_life(loco_type: str | None) -> int:
    """Return TSC working life in years for given loco type. Default 6."""
    if loco_type:
        return TSC_WORKING_LIFE_YEARS.get(loco_type.upper(), 6)
    return 6

# ---------- Pending action TTL ----------
# Seconds before an unconfirmed fitment/removal/add action expires
PENDING_TTL = int(os.getenv("PENDING_TTL", 300))   # 5 minutes

# ---------- Sheets cache TTL ----------
# Seconds to cache get_all_records() results; invalidated on every write
CACHE_TTL = int(os.getenv("CACHE_TTL", 60))        # 1 minute

# ---------- Loco classes ----------
LOCO_CLASSES = ["WAP4", "WAP5", "WAP7", "WAG9", "WAG9H", "WDG4", "WDP4"]

# ---------- Equipment types ----------
EQUIPMENT_TYPES = ["MPH", "MVRH", "PANTO", "GR", "SMGR", "TRANSFORMER"]

# ---------- Schedule types ----------
MAJOR_SCH_TYPES = ["TOH1", "TOH2", "TOH3", "TOH4", "IOH", "POH", "MTR"]
MINOR_SCH_TYPES = ["IA", "IC"]

# ---------- Overhaul cycles (loco-class-aware) ----------
# Values are in DAYS.
# PANTO and TRANSFORMER differ by loco class.
# For equipment types without class-specific rules, only "default" is used.
OVERHAUL_CYCLES_DAYS: dict[str, dict[str, int]] = {
    "MPH":         {"default": 547},                          # 1.5 years
    "MVRH":        {"default": 1642},                         # 4.5 years (IOH schedule)
    "PANTO":       {"WAP4": 547, "WAP5": 547, "WAP7": 547,   # 1.5 years for AC locos
                    "WAG9": 1095, "WAG9H": 1095,              # 3 years for WAG9 family
                    "default": 547},
    "GR":          {"default": 547},                          # 1.5 years
    "SMGR":        {"default": 547},                          # 1.5 years
    "TRANSFORMER": {"WAP4": 1642, "WAP5": 1642, "WAP7": 1642,# 4.5 years for AC locos
                    "WAG9": 3285, "WAG9H": 3285,              # 9 years for WAG9 family
                    "default": 1642},
}


def get_overhaul_days(equipment_type: str, loco_class: str | None = None) -> int:
    """
    Return overhaul interval in days for a given equipment type and loco class.

    Examples:
        get_overhaul_days("PANTO", "WAG9")   → 1095
        get_overhaul_days("PANTO", "WAP4")   → 547
        get_overhaul_days("MPH")             → 547
        get_overhaul_days("UNKNOWN")         → 365 (safe fallback)
    """
    cycles = OVERHAUL_CYCLES_DAYS.get((equipment_type or "").upper())
    if cycles is None:
        return 365  # safe fallback for unknown types
    if loco_class:
        key = loco_class.upper()
        if key in cycles:
            return cycles[key]
    return cycles.get("default", 365)