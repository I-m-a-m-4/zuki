"""Server configuration — everything comes from env / server/.env."""

import os
from pathlib import Path

from dotenv import load_dotenv

_HERE = Path(__file__).parent
load_dotenv(_HERE / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


# The owner's Claude key. Required for the proxy to work — set in server/.env.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
# Overridable so tests can point at a mock upstream.
UPSTREAM_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")

# The Firebase project that issues user ID tokens (Firebase console →
# Authentication → Settings → Project ID). Accounts live there; this server
# only verifies their tokens, so no private keys are involved.
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "zuki-ai").strip()

# Who may use /admin/* — Firebase accounts whose email is listed here
# (comma-separated), plus the ADMIN_TOKEN bearer for scripts (optional).
ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()

# Per-account daily cap on /v1/messages calls (admins are exempt).
DAILY_REQUEST_LIMIT = _int("DAILY_REQUEST_LIMIT", 200)
# Comma-separated model allowlist; empty = allow every model.
ALLOWED_MODELS = {m.strip() for m in os.getenv("ALLOWED_MODELS", "").split(",") if m.strip()}

DB_PATH = Path(os.getenv("ZUKI_DB_PATH", str(_HERE / "data" / "zuki.db")))

HOST = os.getenv("HOST", "0.0.0.0")
PORT = _int("PORT", 8787)
