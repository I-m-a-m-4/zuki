"""Firebase ID-token verification tests: real RS256 crypto, fake Google certs.

A throwaway RSA key signs test tokens; the matching self-signed certificate is
injected as if it were Google's published cert. No network involved.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import time

import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from server import firebase_auth

PROJECT = "zuki-ai"
KID = "test-kid-1"


def _make_key_and_cert() -> tuple[rsa.RSAPrivateKey, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "firebase-test")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    pem = cert.public_bytes(serialization.Encoding.PEM).decode("ascii")
    return key, pem


@pytest.fixture()
def signer(monkeypatch):
    key, pem = _make_key_and_cert()
    monkeypatch.setattr(firebase_auth, "_certs", {KID: pem})
    monkeypatch.setattr(firebase_auth, "_certs_expire", time.time() + 3600)

    def sign(claims: dict, kid: str | None = KID) -> str:
        private = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        headers = {"kid": kid} if kid is not None else {}
        return jwt.encode(claims, private, algorithm="RS256", headers=headers)

    return sign


def _claims(**over) -> dict:
    now = int(time.time())
    base = {
        "sub": "abc123",
        "aud": PROJECT,
        "iss": f"https://securetoken.google.com/{PROJECT}",
        "iat": now,
        "exp": now + 3600,
        "email": "user@example.com",
        "name": "User",
    }
    base.update(over)
    return base


def test_valid_token_verifies(signer):
    claims = firebase_auth.verify_id_token(signer(_claims()))
    assert claims["sub"] == "abc123"
    assert claims["email"] == "user@example.com"


def test_wrong_audience_rejected(signer):
    with pytest.raises(firebase_auth.InvalidToken):
        firebase_auth.verify_id_token(signer(_claims(aud="some-other-project")))


def test_wrong_issuer_rejected(signer):
    with pytest.raises(firebase_auth.InvalidToken):
        firebase_auth.verify_id_token(signer(_claims(iss="https://securetoken.google.com/evil")))


def test_expired_token_rejected(signer):
    now = int(time.time())
    with pytest.raises(firebase_auth.InvalidToken):
        firebase_auth.verify_id_token(signer(_claims(iat=now - 7200, exp=now - 3600)))


def test_wrong_signing_key_rejected(signer):
    other_key, _ = _make_key_and_cert()
    private = other_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    forged = jwt.encode(_claims(), private, algorithm="RS256", headers={"kid": KID})
    with pytest.raises(firebase_auth.InvalidToken):
        firebase_auth.verify_id_token(forged)


def test_malformed_token_rejected():
    with pytest.raises(firebase_auth.InvalidToken):
        firebase_auth.verify_id_token("not-a-jwt")


def test_missing_kid_rejected(signer):
    with pytest.raises(firebase_auth.InvalidToken):
        firebase_auth.verify_id_token(signer(_claims(), kid=None))


def test_unknown_kid_refetches_certs(signer, monkeypatch):
    token = signer(_claims(), kid="rotated-kid")
    monkeypatch.setattr(firebase_auth, "_fetch_certs",
                        lambda: {})  # rotation fetch doesn't know it yet
    with pytest.raises(firebase_auth.InvalidToken):
        firebase_auth.verify_id_token(token)


def test_rotated_kid_accepted_after_refetch(signer, monkeypatch):
    token = signer(_claims(), kid="rotated-kid")
    current = firebase_auth._certs
    monkeypatch.setattr(firebase_auth, "_fetch_certs",
                        lambda: {**current, "rotated-kid": current[KID]})
    claims = firebase_auth.verify_id_token(token)
    assert claims["sub"] == "abc123"


def _unsigned_token_with_kid(kid: str = "somekid") -> str:
    def b64(obj: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    return f"{b64({'alg': 'RS256', 'kid': kid})}.{b64({'sub': 'x'})}.sig"


def test_certs_unavailable_when_no_cache(monkeypatch):
    monkeypatch.setattr(firebase_auth, "_certs", {})
    monkeypatch.setattr(firebase_auth, "_certs_expire", 0.0)

    def boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(firebase_auth, "_fetch_certs", boom)
    with pytest.raises(firebase_auth.CertsUnavailable):
        firebase_auth.verify_id_token(_unsigned_token_with_kid())


def test_stale_certs_still_used(signer, monkeypatch):
    monkeypatch.setattr(firebase_auth, "_certs_expire", 0.0)  # expired cache

    def boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(firebase_auth, "_fetch_certs", boom)
    claims = firebase_auth.verify_id_token(signer(_claims()))
    assert claims["sub"] == "abc123"
