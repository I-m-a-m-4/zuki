"""Verify Firebase Auth ID tokens — no service account required.

The desktop app and the admin page sign in with Firebase Auth (email/password)
and send the resulting ID token to this server. Google publishes the
token-signing certificates at a well-known URL; we verify the RS256 signature
against them and check the standard claims (aud/iss/exp/sub). Only the public
project id is needed — no private key, no firebase-admin SDK.
"""

from __future__ import annotations

import threading
import time

import httpx
import jwt
from cryptography import x509

from . import config

CERTS_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/"
    "securetoken@system.gserviceaccount.com"
)
_TIMEOUT = httpx.Timeout(15.0, connect=10.0)

_lock = threading.Lock()
_certs: dict[str, str] = {}
_certs_expire = 0.0


class InvalidToken(Exception):
    """Missing, malformed, expired, or wrong-project token."""


class CertsUnavailable(Exception):
    """Couldn't reach Google to fetch signing certs and have no cached copy."""


def _fetch_certs() -> dict[str, str]:
    resp = httpx.get(CERTS_URL, timeout=_TIMEOUT)
    resp.raise_for_status()
    certs: dict[str, str] = resp.json()
    max_age = 600.0
    for part in resp.headers.get("cache-control", "").split(","):
        part = part.strip()
        if part.startswith("max-age="):
            try:
                max_age = float(part.split("=", 1)[1])
            except ValueError:
                pass
    global _certs, _certs_expire
    _certs = certs
    _certs_expire = time.time() + max(60.0, max_age)
    return certs


def _certs_cached() -> dict[str, str]:
    with _lock:
        if _certs and time.time() < _certs_expire:
            return _certs
        try:
            return _fetch_certs()
        except Exception as e:
            if _certs:                      # stale beats nothing
                return _certs
            raise CertsUnavailable(str(e)) from e


def verify_id_token(token: str) -> dict:
    """Decoded claims for a valid Firebase ID token; raises InvalidToken otherwise."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as e:
        raise InvalidToken("Malformed sign-in token.") from e
    kid = header.get("kid")
    if not kid:
        raise InvalidToken("Sign-in token is missing its key id.")

    certs = _certs_cached()
    pem = certs.get(kid)
    if pem is None:                         # key rotated since our last fetch
        try:
            pem = _fetch_certs().get(kid)
        except Exception as e:
            raise CertsUnavailable(str(e)) from e
    if pem is None:
        raise InvalidToken("Sign-in token was signed with an unknown key.")

    key = x509.load_pem_x509_certificate(pem.encode()).public_key()
    try:
        claims = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=config.FIREBASE_PROJECT_ID,
            issuer=f"https://securetoken.google.com/{config.FIREBASE_PROJECT_ID}",
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
    except jwt.ExpiredSignatureError as e:
        raise InvalidToken("Session expired — sign in again.") from e
    except jwt.PyJWTError as e:
        raise InvalidToken("Sign-in token failed verification.") from e
    if not claims.get("sub"):
        raise InvalidToken("Sign-in token has no user id.")
    return claims
