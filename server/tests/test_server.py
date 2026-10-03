"""Server tests: run with `python -m pytest server/tests -q` from the repo root.

Firebase token verification is faked (tokens are "uid|email|name" strings) and
the upstream Anthropic API is an httpx MockTransport — nothing touches the
network.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from server import config, db, firebase_auth, proxy
from server.main import app

ADMIN_HEADERS = {"Authorization": "Bearer test-admin-token"}

DEFAULT_JSON_REPLY = {
    "id": "msg_test", "type": "message", "role": "assistant",
    "model": "claude-sonnet-5", "content": [{"type": "text", "text": "hello"}],
    "usage": {"input_tokens": 11, "output_tokens": 7},
}

SSE_CHUNKS = [
    b'event: message_start\ndata: {"type":"message_start","message":{"usage":{"input_tokens":21}}}\n\n',
    b'event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"text":"hi"}}\n\n',
    b'event: message_delta\ndata: {"type":"message_delta","usage":{"output_tokens":13}}\n\n',
    b'event: message_stop\ndata: {"type":"message_stop"}\n\n',
]


def tok(uid: str = "u1", email: str = "user@example.com", name: str = "User") -> str:
    return f"{uid}|{email}|{name}"


def fake_verify(token: str) -> dict:
    if "|" not in token:
        raise firebase_auth.InvalidToken("Sign-in token failed verification.")
    uid, email, name = token.split("|", 2)
    return {"sub": uid, "email": email, "name": name}


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class Upstream:
    """Stand-in for api.anthropic.com; records what the proxy sent."""

    def __init__(self) -> None:
        self.seen: list[httpx.Request] = []
        self.responder = None

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        if self.responder is not None:
            return self.responder(request)
        return httpx.Response(200, json=DEFAULT_JSON_REPLY)


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    db.set_db_path(tmp_path / "test.db")
    db.init_db()
    monkeypatch.setattr(firebase_auth, "verify_id_token", fake_verify)
    monkeypatch.setattr(config, "ADMIN_TOKEN", "test-admin-token")
    monkeypatch.setattr(config, "ADMIN_EMAILS", set())
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def upstream(monkeypatch) -> Upstream:
    mock = Upstream()

    def new_client():
        return httpx.AsyncClient(transport=httpx.MockTransport(mock.handle), timeout=30.0)

    monkeypatch.setattr(proxy, "new_client", new_client)
    return mock


# ── accounts ─────────────────────────────────────────────────────────────────

def test_me_auto_provisions_account(client):
    me = client.get("/auth/me", headers=auth(tok())).json()
    assert me["uid"] == "u1"
    assert me["email"] == "user@example.com"
    assert me["name"] == "User"
    assert me["is_admin"] is False
    assert me["daily_request_limit"] == config.DAILY_REQUEST_LIMIT
    assert me["usage_today"] == {"requests": 0, "input_tokens": 0, "output_tokens": 0}


def test_me_requires_valid_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers=auth("bogus")).status_code == 401
    assert client.get("/auth/me", headers={"x-api-key": "bogus"}).status_code == 401


def test_token_via_x_api_key(client):
    r = client.get("/auth/me", headers={"x-api-key": tok(uid="u2", email="two@example.com")})
    assert r.status_code == 200
    assert r.json()["uid"] == "u2"


def test_certs_unavailable_maps_to_503(client, monkeypatch):
    def down(_token):
        raise firebase_auth.CertsUnavailable("network down")

    monkeypatch.setattr(firebase_auth, "verify_id_token", down)
    r = client.get("/auth/me", headers=auth("whatever"))
    assert r.status_code == 503


def test_admin_me_payload(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_EMAILS", {"boss@example.com"})
    me = client.get("/auth/me", headers=auth(tok(uid="boss", email="boss@example.com"))).json()
    assert me["is_admin"] is True
    assert me["daily_request_limit"] is None


# ── proxy ────────────────────────────────────────────────────────────────────

def test_proxy_requires_auth(client):
    assert client.post("/v1/messages", json={"model": "m", "messages": []}).status_code == 401
    assert client.post("/v1/messages", headers=auth("bogus"), json={}).status_code == 401


def test_proxy_forwards_with_owner_key(client, upstream):
    r = client.post(
        "/v1/messages",
        headers={**auth(tok()), "anthropic-version": "2023-06-01",
                 "anthropic-beta": "computer-use-2025-11-24"},
        json={"model": "claude-sonnet-5", "max_tokens": 10,
              "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200
    assert r.json()["content"][0]["text"] == "hello"

    seen = upstream.seen[-1]
    assert str(seen.url) == "https://api.anthropic.com/v1/messages"
    assert seen.headers["x-api-key"] == "sk-ant-test-upstream"
    assert seen.headers["anthropic-beta"] == "computer-use-2025-11-24"

    usage = client.get("/auth/me", headers=auth(tok())).json()["usage_today"]
    assert usage["requests"] == 1
    assert usage["input_tokens"] == 11 and usage["output_tokens"] == 7


def test_proxy_streaming_passthrough_and_usage(client, upstream):
    async def sse():
        for chunk in SSE_CHUNKS:
            yield chunk

    upstream.responder = lambda req: httpx.Response(
        200, headers={"content-type": "text/event-stream"}, content=sse(),
    )
    r = client.post("/v1/messages", headers=auth(tok()),
                    json={"model": "claude-sonnet-5", "stream": True, "messages": []})
    assert r.status_code == 200
    assert "message_start" in r.text and "message_stop" in r.text
    assert '"text":"hi"' in r.text

    usage = client.get("/auth/me", headers=auth(tok())).json()["usage_today"]
    assert usage["requests"] == 1
    assert usage["input_tokens"] == 21 and usage["output_tokens"] == 13


def test_proxy_passes_upstream_errors(client, upstream):
    upstream.responder = lambda req: httpx.Response(
        401, json={"type": "error",
                   "error": {"type": "authentication_error", "message": "bad key"}},
    )
    r = client.post("/v1/messages", headers=auth(tok()), json={"model": "m", "messages": []})
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "bad key"


def test_daily_limit_enforced(client, upstream, monkeypatch):
    monkeypatch.setattr(config, "DAILY_REQUEST_LIMIT", 2)
    body = {"model": "m", "messages": []}
    assert client.post("/v1/messages", headers=auth(tok()), json=body).status_code == 200
    assert client.post("/v1/messages", headers=auth(tok()), json=body).status_code == 200
    r = client.post("/v1/messages", headers=auth(tok()), json=body)
    assert r.status_code == 429
    assert "Daily limit" in r.json()["error"]["message"]


def test_model_allowlist(client, upstream, monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_MODELS", {"claude-sonnet-5"})
    ok = client.post("/v1/messages", headers=auth(tok()),
                     json={"model": "claude-sonnet-5", "messages": []})
    assert ok.status_code == 200
    blocked = client.post("/v1/messages", headers=auth(tok()),
                          json={"model": "some-other-model", "messages": []})
    assert blocked.status_code == 400


def test_models_passthrough_not_counted(client, upstream):
    upstream.responder = lambda req: httpx.Response(200, json={"data": [{"id": "claude-sonnet-5"}]})
    r = client.get("/v1/models", headers=auth(tok()))
    assert r.status_code == 200 and r.json()["data"][0]["id"] == "claude-sonnet-5"
    assert client.get("/auth/me", headers=auth(tok())).json()["usage_today"]["requests"] == 0


# ── admin ────────────────────────────────────────────────────────────────────

def test_admin_requires_token_or_email_list(client):
    assert client.get("/admin/users").status_code == 401
    assert client.get("/admin/users", headers=auth("wrong")).status_code == 401


def test_admin_disabled_when_unconfigured(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_TOKEN", "")
    monkeypatch.setattr(config, "ADMIN_EMAILS", set())
    assert client.get("/admin/users", headers=ADMIN_HEADERS).status_code == 503


def test_admin_via_email_list(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_EMAILS", {"boss@example.com"})
    r = client.get("/admin/users", headers=auth(tok(uid="boss", email="boss@example.com")))
    assert r.status_code == 200
    denied = client.get("/admin/users", headers=auth(tok(uid="u9", email="nope@example.com")))
    assert denied.status_code == 403


def test_admin_page_served(client):
    r = client.get("/admin/")
    assert r.status_code == 200
    assert "Zuki" in r.text
    assert client.get("/admin", follow_redirects=False).status_code in (307, 302)


def test_admin_disable_and_per_user_limit(client, upstream):
    client.get("/auth/me", headers=auth(tok()))  # auto-provision
    users = client.get("/admin/users", headers=ADMIN_HEADERS).json()["users"]
    assert users[0]["email"] == "user@example.com"

    assert client.post("/admin/users/u1/limit",
                       headers=ADMIN_HEADERS, json={"daily_request_limit": 1}).status_code == 200
    body = {"model": "m", "messages": []}
    assert client.post("/v1/messages", headers=auth(tok()), json=body).status_code == 200
    assert client.post("/v1/messages", headers=auth(tok()), json=body).status_code == 429

    assert client.post("/admin/users/u1/disable",
                       headers=ADMIN_HEADERS, json={"disabled": True}).status_code == 200
    assert client.get("/auth/me", headers=auth(tok())).status_code == 403
    assert client.post("/v1/messages", headers=auth(tok()), json=body).status_code == 403


def test_admin_limit_validation_and_unknown_user(client):
    bad = client.post("/admin/users/u1/limit",
                      headers=ADMIN_HEADERS, json={"daily_request_limit": -5})
    assert bad.status_code == 400
    missing = client.post("/admin/users/nope/disable",
                          headers=ADMIN_HEADERS, json={"disabled": True})
    assert missing.status_code == 404


def test_admin_users_show_usage(client, upstream):
    client.post("/v1/messages", headers=auth(tok()), json={"model": "m", "messages": []})
    users = client.get("/admin/users", headers=ADMIN_HEADERS).json()["users"]
    row = users[0]
    assert row["requests_today"] == 1
    assert row["input_tokens_today"] == 11
    assert row["requests_total"] == 1
    assert row["tokens_total"] == 18
    assert row["last_seen"]


def test_health(client):
    assert client.get("/health").json()["ok"] is True
