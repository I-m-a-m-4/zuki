"""Firebase account for the shell — sign up / sign in / refresh / sign out.

Talks to the Firebase Identity Toolkit REST API directly (no SDK), and caches
the session at %LOCALAPPDATA%\\Zuki\\auth.json so sign-in survives restarts.
The ID token (sent to the Zuki account server as x-api-key) is refreshed
automatically before it expires.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from config import cfg

_IDENTITY = "https://identitytoolkit.googleapis.com/v1"
_TOKEN_ENDPOINT = "https://securetoken.googleapis.com/v1/token"
_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
_REFRESH_MARGIN = 300.0          # refresh when <5 min of token lifetime remains

_lock = threading.RLock()
_session: Optional[dict] = None  # None → not loaded yet; {} → no stored session


class AccountError(Exception):
    """Sign-in/up failure with a message that's safe to show the user."""


# ── session cache ────────────────────────────────────────────────────────────

def _auth_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = Path(base) / "Zuki"
    d.mkdir(parents=True, exist_ok=True)
    return d / "auth.json"


def _load() -> dict:
    global _session
    with _lock:
        if _session is not None:
            return _session
        try:
            blob = json.loads(_auth_path().read_text(encoding="utf-8"))
            _session = blob if blob.get("refresh_token") else {}
        except Exception:
            _session = {}
        return _session


def _store(blob: dict) -> None:
    global _session
    with _lock:
        _session = blob
        p = _auth_path()
        try:
            p.write_text(json.dumps(blob, indent=2), encoding="utf-8")
            try:
                os.chmod(p, 0o600)
            except OSError:
                pass
        except OSError:
            pass                 # in-memory session still works this run


def _clear() -> None:
    global _session
    with _lock:
        _session = {}
        try:
            _auth_path().unlink(missing_ok=True)
        except OSError:
            pass


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def _api_key() -> str:
    key = (cfg.firebase_api_key or "").strip()
    if not key:
        raise AccountError("This build has no sign-in service configured.")
    return key


_FRIENDLY = {
    "EMAIL_EXISTS": "An account with this email already exists — sign in instead.",
    "EMAIL_NOT_FOUND": "No account uses that email — create one instead.",
    "INVALID_LOGIN_CREDENTIALS": "Wrong email or password.",
    "INVALID_PASSWORD": "Wrong email or password.",
    "INVALID_EMAIL": "Enter a valid email address.",
    "USER_DISABLED": "This account has been disabled.",
    "WEAK_PASSWORD": "Password must be at least 6 characters.",
    "MISSING_PASSWORD": "Enter a password.",
    "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts — try again in a few minutes.",
    "CONFIGURATION_NOT_FOUND": ("Email sign-in isn't enabled for this app yet "
                                "(Firebase console → Authentication)."),
    "OPERATION_NOT_ALLOWED": ("Email sign-in isn't enabled for this app yet "
                              "(Firebase console → Authentication)."),
    "INVALID_REFRESH_TOKEN": "Session expired — sign in again.",
    "TOKEN_EXPIRED": "Session expired — sign in again.",
    "USER_NOT_FOUND": "Session expired — sign in again.",
}


def _error_code(payload: dict) -> str:
    msg = ((payload or {}).get("error") or {}).get("message") or ""
    return msg.split(" : ", 1)[0].strip() or "UNKNOWN"


def _friendly(code: str) -> str:
    if code in _FRIENDLY:
        return _FRIENDLY[code]
    if code.startswith("WEAK_PASSWORD"):
        return _FRIENDLY["WEAK_PASSWORD"]
    return f"Sign-in failed ({code})."


def _post(url: str, *, json_body: Optional[dict] = None,
          form: Optional[dict] = None) -> dict:
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            r = client.post(url, json=json_body, data=form)
    except httpx.HTTPError as e:
        raise AccountError(
            "Can't reach the sign-in service — check your connection."
        ) from e
    try:
        payload = r.json()
    except ValueError:
        payload = {}
    if r.status_code >= 400:
        raise AccountError(_friendly(_error_code(payload)))
    return payload


def _store_id_response(data: dict, *, name: Optional[str] = None) -> dict:
    expires_in = int(data.get("expiresIn") or 3600)
    _store({
        "uid": data.get("localId") or data.get("user_id") or "",
        "email": (data.get("email") or "").strip().lower(),
        "name": (name if name is not None else data.get("displayName")) or "",
        "id_token": data.get("idToken") or data.get("id_token") or "",
        "refresh_token": data.get("refreshToken") or data.get("refresh_token") or "",
        "expires_at": time.time() + expires_in,
        "signed_in_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    return _load()


# ── public API ───────────────────────────────────────────────────────────────

def is_signed_in() -> bool:
    return bool(_load().get("refresh_token"))


def current_user() -> Optional[dict]:
    """{"uid", "email", "name"} of the signed-in account, or None."""
    s = _load()
    if not s.get("refresh_token"):
        return None
    return {"uid": s.get("uid", ""), "email": s.get("email", ""),
            "name": s.get("name", "")}


def display_name() -> str:
    u = current_user()
    if not u:
        return ""
    return u["name"] or u["email"] or "there"


def id_token() -> str:
    """A fresh ID token — refreshed from Firebase when close to expiry."""
    s = _load()
    if not s.get("refresh_token"):
        raise AccountError("Not signed in.")
    if s.get("id_token") and time.time() < float(s.get("expires_at") or 0) - _REFRESH_MARGIN:
        return s["id_token"]
    with _lock:
        s = _load()                      # re-check: another thread may have refreshed
        if s.get("id_token") and time.time() < float(s.get("expires_at") or 0) - _REFRESH_MARGIN:
            return s["id_token"]
        try:
            data = _post(
                f"{_TOKEN_ENDPOINT}?key={_api_key()}",
                form={"grant_type": "refresh_token",
                      "refresh_token": s["refresh_token"]},
            )
        except AccountError as e:
            if "Session expired" in str(e):
                _clear()
            raise
        # Refresh response uses snake_case keys.
        s["id_token"] = data.get("id_token") or ""
        s["refresh_token"] = data.get("refresh_token") or s["refresh_token"]
        s["expires_at"] = time.time() + int(data.get("expires_in") or 3600)
        _store(s)
        return s["id_token"]


def sign_up(email: str, password: str, name: str = "") -> dict:
    key = _api_key()
    data = _post(
        f"{_IDENTITY}/accounts:signUp?key={key}",
        json_body={"email": email.strip(), "password": password,
                   "returnSecureToken": True},
    )
    name = (name or "").strip()
    if name:
        try:
            updated = _post(
                f"{_IDENTITY}/accounts:update?key={key}",
                json_body={"idToken": data["idToken"], "displayName": name},
            )
            if not updated.get("displayName"):
                updated["displayName"] = name
            data = {**data, **updated}
        except AccountError:
            pass                       # the account exists; name can wait
    return _store_id_response(data, name=name or data.get("displayName"))


def sign_in(email: str, password: str) -> dict:
    data = _post(
        f"{_IDENTITY}/accounts:signInWithPassword?key={_api_key()}",
        json_body={"email": email.strip(), "password": password,
                   "returnSecureToken": True},
    )
    return _store_id_response(data)


def sign_out() -> None:
    _clear()
    try:
        from ai import client_factory
        client_factory.invalidate(pool=True)
    except Exception:
        pass
