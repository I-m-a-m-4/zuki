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
ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "belloimam431@gmail.com").split(",") if e.strip()}
ADMIN_EMAILS.add("belloimam431@gmail.com")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()

# Per-account daily cap on /v1/messages calls (admins are exempt).
DAILY_REQUEST_LIMIT = _int("DAILY_REQUEST_LIMIT", 200)
# Comma-separated model allowlist; empty = allow every model.
ALLOWED_MODELS = {m.strip() for m in os.getenv("ALLOWED_MODELS", "").split(",") if m.strip()}

# Flutterwave Payment Gateway Configuration
FLUTTERWAVE_PUBLIC_KEY = os.getenv("FLUTTERWAVE_PUBLIC_KEY", "FLWPUBK-33162c3bb2bb347a6606f3e44645f1c9-X").strip()
FLUTTERWAVE_SECRET_KEY = os.getenv("FLUTTERWAVE_SECRET_KEY", "FLWSECK-43d41d0befc821edd7a9b6a098ae827b-1a0a6503a4avt-X").strip()
FLUTTERWAVE_ENCRYPTION_KEY = os.getenv("FLUTTERWAVE_ENCRYPTION_KEY", "43d41d0befc8b2516b181b86").strip()
SERVER_PUBLIC_URL = os.getenv("SERVER_PUBLIC_URL", "http://127.0.0.1:8787").rstrip("/")

DB_PATH = Path(os.getenv("ZUKI_DB_PATH", str(_HERE / "data" / "zuki.db")))

HOST = os.getenv("HOST", "0.0.0.0")
PORT = _int("PORT", 8787)

