"""Zuki's one door to Claude.

Priority:
  1. Signed in → the Zuki account server (the owner's key; per-account
     quotas, disable switches). The account server speaks the Anthropic API.
  2. Local ANTHROPIC_API_KEY → straight to Anthropic (dev / power users).
  3. Neither → AccountRequired; the UI should prompt sign-in.

SDK clients embed one shared httpx pool whose request hook swaps in a fresh
account token on every call — so a long-running session never rides an
expired ID token. Raw call sites use auth_headers()/messages_url() per call.
"""

from __future__ import annotations

import threading
from typing import Optional

import httpx

from config import cfg

try:
    import account as _account
except Exception:                # pragma: no cover — frozen/module contexts
    _account = None

ANTHROPIC_BASE = "https://api.anthropic.com"


class AccountRequired(Exception):
    """No way to reach Claude — sign in, or set a local ANTHROPIC_API_KEY."""


_lock = threading.Lock()
_generation = 0
_async_sdk: dict = {}
_async_http: Optional[httpx.AsyncClient] = None


def _acct():
    try:
        if _account is not None and _account.is_signed_in():
            return _account
    except Exception:
        pass
    return None


def account_mode() -> bool:
    return _acct() is not None


def has_claude() -> bool:
    """True when *some* Claude path exists (account or local key)."""
    return account_mode() or bool(cfg.anthropic_api_key)


def invalidate(pool: bool = False) -> None:
    """Drop cached SDK clients after sign-in/out. pool=True also drops the
    shared HTTP pool (network reset — e.g. system sleep/resume)."""
    global _generation, _async_http
    with _lock:
        _generation += 1
        _async_sdk.clear()
        if pool:
            _async_http = None


def credential() -> tuple[str, str]:
    """(secret, base_url); raises AccountRequired when nothing is configured."""
    acct = _acct()
    if acct is not None:
        return acct.id_token(), cfg.server_url
    if cfg.anthropic_api_key:
        return cfg.anthropic_api_key, ANTHROPIC_BASE
    raise AccountRequired(
        "Sign in to Zuki (tray menu → Account…), or set ANTHROPIC_API_KEY."
    )


def auth_headers(extra: Optional[dict] = None) -> dict:
    """Headers for a raw Anthropic-compatible call. Token is fresh per call."""
    secret, _base = credential()
    headers = {"x-api-key": secret, "anthropic-version": "2023-06-01"}
    if extra:
        headers.update(extra)
    return headers


def messages_url() -> str:
    return credential()[1] + "/v1/messages"


def models_url() -> str:
    return credential()[1] + "/v1/models"


def api_base() -> str:
    return credential()[1]


def _refresh_hook(request: httpx.Request) -> None:
    acct = _acct()
    if acct is not None:
        try:
            request.headers["x-api-key"] = acct.id_token()
        except Exception:
            pass                 # request proceeds with the embedded (older) token


def _shared_http() -> httpx.AsyncClient:
    global _async_http
    with _lock:
        if _async_http is None or _async_http.is_closed:
            _async_http = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=15.0),
                event_hooks={"request": [_refresh_hook]},
            )
        return _async_http


def warm_http() -> httpx.AsyncClient:
    """The shared pool, for connectivity warm-ups."""
    return _shared_http()


def make_async_client():
    """Cached AsyncAnthropic client (router / chat / workspace / research)."""
    import anthropic
    with _lock:
        gen = _generation
        cached = _async_sdk.get(gen)
        if cached is not None:
            return cached
    secret, base = credential()
    client = anthropic.AsyncAnthropic(
        api_key=secret, base_url=base, http_client=_shared_http(),
    )
    with _lock:
        _async_sdk.clear()
        _async_sdk[gen] = client
    return client


def describe() -> str:
    if account_mode():
        email = ""
        try:
            u = _acct().current_user()
            email = (u or {}).get("email", "")
        except Exception:
            pass
        return f"account ({email})" if email else "account"
    if cfg.anthropic_api_key:
        return "local API key"
    return "not configured"
