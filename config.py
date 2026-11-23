import os
import secrets
from tournaments import Tournament

# Tournament settings live in data/tournaments/<id>/tournament.json (see tournaments.py).
# LeagueConfig is kept as a name for type hints used across the code.
LeagueConfig = Tournament


# ── RapidAPI Configuration ──
# IMPORTANT: Set RAPIDAPI_KEY environment variable before running
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
if not RAPIDAPI_KEY:
    print("WARNING: RAPIDAPI_KEY not set in environment. API calls will fail.")
RAPIDAPI_HOST = "cricbuzz-cricket.p.rapidapi.com"
BASE_URL = f"https://{RAPIDAPI_HOST}"

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
    "admin": {
        "password_hash": "$2b$12$9lIArDyg8/s1t4RWL85Glu3Ihqs0z6Y6H5KeIzLpvImjU0dkumgUK",
        "role": "admin"
    },
    "viewer": {
        "password_hash": "$2b$12$LDRjuyLZUDsbpeSkU8FBxenMgn6l9N7hK2VZLni.TMCXepgSsaaw6",
        "role": "user"
    },
}

# ── Environment Configuration ──
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
DEBUG = ENVIRONMENT == "development"
