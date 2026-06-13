import os
import secrets
from dataclasses import dataclass


@dataclass
class LeagueConfig:
    name: str           # Display name, e.g. "IPL Fantasy League 2026"
    short_name: str     # URL key, e.g. "ipl" or "wwc"
    emoji: str          # Navbar emoji
    data_dir: str
    scorecard_cache_dir: str
    scores_file: str
    match_history_file: str
    scoring_sheet_file: str
    master_scoresheet_file: str
    teams_file: str
    players_file: str
    dashboard_prefix: str  # URL prefix, e.g. "/dashboard" or "/wwc"


IPL_CONFIG = LeagueConfig(
    name="IPL Fantasy League 2026",
    short_name="ipl",
    emoji="🏏",
    data_dir="data",
    scorecard_cache_dir=os.path.join("data", "scorecards"),
    scores_file=os.path.join("data", "cumulative_scores.json"),
    match_history_file=os.path.join("data", "match_history.json"),
    scoring_sheet_file=os.path.join("data", "scoring_sheet.json"),
    master_scoresheet_file=os.path.join("data", "master_scoresheet.json"),
    teams_file="teams_data.json",
    players_file="players_data.json",
    dashboard_prefix="/dashboard",
)

WWC_CONFIG = LeagueConfig(
    name="Women's T20 World Cup 2026",
    short_name="wwc",
    emoji="🏆",
    data_dir=os.path.join("data", "wwc"),
    scorecard_cache_dir=os.path.join("data", "wwc", "scorecards"),
    scores_file=os.path.join("data", "wwc", "cumulative_scores.json"),
    match_history_file=os.path.join("data", "wwc", "match_history.json"),
    scoring_sheet_file=os.path.join("data", "wwc", "scoring_sheet.json"),
    master_scoresheet_file=os.path.join("data", "wwc", "master_scoresheet.json"),
    teams_file=os.path.join("data", "wwc", "teams_data.json"),
    players_file=os.path.join("data", "wwc", "players_data.json"),
    dashboard_prefix="/wwc",
)

LEAGUES = {"ipl": IPL_CONFIG, "wwc": WWC_CONFIG}

# ── RapidAPI Configuration ──
# IMPORTANT: Set RAPIDAPI_KEY environment variable before running
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
if not RAPIDAPI_KEY:
    print("WARNING: RAPIDAPI_KEY not set in environment. API calls will fail.")
RAPIDAPI_HOST = "cricbuzz-cricket.p.rapidapi.com"
BASE_URL = f"https://{RAPIDAPI_HOST}"

# ── File Paths ──
DATA_DIR = "data"
SCORECARD_CACHE_DIR = os.path.join(DATA_DIR, "scorecards")
SCORES_FILE = os.path.join(DATA_DIR, "cumulative_scores.json")
MATCH_HISTORY_FILE = os.path.join(DATA_DIR, "match_history.json")
SCORING_SHEET_FILE = os.path.join(DATA_DIR, "scoring_sheet.json")
MASTER_SCORESHEET_FILE = os.path.join(DATA_DIR, "master_scoresheet.json")
TEAMS_FILE = "teams_data.json"
PLAYERS_FILE = "players_data.json"

# ── Web Application Security Settings ──
# IMPORTANT: Set SECRET_KEY environment variable in production
# Generate a secure key with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# ── Automation API Key ──
# Used by GitHub Actions / cron to call POST /api/auto-score without a browser session.
# Set AUTOSCORE_API_KEY env var in Railway and as a GitHub Actions secret.
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
AUTOSCORE_API_KEY = os.environ.get("AUTOSCORE_API_KEY")

# ── Web Server Configuration ──
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
RELOAD = os.environ.get("RELOAD", "true").lower() == "true"

# ── User Database ──
# In production, replace with proper database and secure credential storage
# Password hashes generated with: import bcrypt; bcrypt.hashpw(b'password', bcrypt.gensalt()).decode('utf-8')
USERS_DB = {
    # Default admin user - CHANGE PASSWORD IN PRODUCTION
    "admin": {
        "password_hash": "$2b$12$EEtk9sihYENMAQTFZUnUM.p7gFMsupN84fjVG9qYvHs8Yt1N9HHkS",  # "admin123"
        "role": "admin"
    },
    # Add more users as needed
    # Example: "user1": {"password_hash": "hash_here", "role": "user"}
}

# ── Environment Configuration ──
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
DEBUG = ENVIRONMENT == "development"
