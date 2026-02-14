# -*- coding: utf-8 -*-
"""
JobVision Auto-Apply configuration.
All constants and defaults in one place.
"""

import os
from pathlib import Path

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"
DEBUG_HTML_DIR = BASE_DIR / "debug_html"

# --- URLs ---
BASE_URL = "https://jobvision.ir"
LOGIN_URL = f"{BASE_URL}/login"
RECOMMENDED_JOBS_URL = f"{BASE_URL}/recommended-jobs"
RECOMMENDED_JOBS_HIGH_EMPLOYMENT = f"{BASE_URL}/recommended-jobs/high-employment"

# --- Accepted location/work-type keywords (دورکاری، گلستان، گرگان) ---
ACCEPTED_LOCATION_KEYWORDS = ("دورکاری", "گلستان", "گرگان")
SKIP_TITLE_KEYWORDS = ("کارآموز", "Intern", "intern")

# --- Playwright ---
NAVIGATION_TIMEOUT_MS = 60_000
DEFAULT_TIMEOUT_MS = 15_000
GOTO_RETRIES = 3
GOTO_RETRY_DELAY_SEC = 2

# --- Pagination ---
MAX_PAGES = 50
PAGE_LOAD_WAIT_MS = 2000

# --- Gemini (optional) ---
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_APPLY_THRESHOLD = 60  # 0-100
GEMINI_RETRIES = 2
GEMINI_RETRY_DELAY_SEC = 1

# --- Files ---
SENT_JOBS_FILE = DATA_DIR / "sent_jobs.json"
APPLICATIONS_JSON = DATA_DIR / "applications.json"
APPLICATIONS_CSV = DATA_DIR / "applications.csv"

# --- Env ---
def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


GEMINI_API_KEY = get_env("GEMINI_API_KEY")

# --- Create dirs ---
LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
DEBUG_HTML_DIR.mkdir(exist_ok=True)
