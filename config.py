import os
import secrets

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
