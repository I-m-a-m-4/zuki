"""Zuki account server: Firebase auth, Claude proxy, admin controls.

Accounts live in Firebase Auth; this server verifies Firebase ID tokens and
keeps only operational state locally (disabled flag, caps, usage counters).

Run:  uvicorn server.main:app --host 0.0.0.0 --port 8787
"""

from __future__ import annotations

import hmac
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from pydantic import BaseModel

from . import config, db, firebase_auth, proxy

VERSION = "0.2.0"

_STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    if not config.ANTHROPIC_API_KEY:
        print("[server] WARNING: ANTHROPIC_API_KEY is not set — /v1/* will fail.")
    if not config.ADMIN_TOKEN and not config.ADMIN_EMAILS:
        print("[server] WARNING: neither ADMIN_TOKEN nor ADMIN_EMAILS is set — "
              "/admin/* is disabled.")
    yield


app = FastAPI(title="Zuki Account Server", version=VERSION, lifespan=lifespan)


# ── error helpers ────────────────────────────────────────────────────────────

def _error(status: int, etype: str, message: str, headers: Optional[dict] = None) -> JSONResponse:
    return JSONResponse(
        {"type": "error", "error": {"type": etype, "message": message}},
        status_code=status, headers=headers,
    )


class _AuthError(Exception):
    def __init__(self, status: int, etype: str, message: str):
        self.status, self.etype, self.message = status, etype, message


@app.exception_handler(_AuthError)
async def _auth_error_handler(_request: Request, exc: _AuthError):
    return _error(exc.status, exc.etype, exc.message)


def _token_from_request(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    api_key = request.headers.get("x-api-key", "")
    return api_key.strip() or None


def _is_admin_email(email: Optional[str]) -> bool:
    return bool(email) and email.strip().lower() in config.ADMIN_EMAILS


def _user_payload(user: db.User, usage: dict) -> dict:
    is_admin = _is_admin_email(user.email)
    limit = config.DAILY_REQUEST_LIMIT if user.daily_request_limit is None else user.daily_request_limit
    plan = "admin" if is_admin else getattr(user, "plan_tier", "free")
    is_pro = is_admin or plan in ("pro", "unlimited", "admin")
    return {
        "uid": user.uid, "email": user.email, "name": user.name,
        "is_admin": is_admin,
        "plan_tier": plan,
        "is_pro": is_pro,
        "subscription_status": "active" if is_pro else getattr(user, "subscription_status", "none"),
        "daily_request_limit": None if is_pro else limit,
        "usage_today": usage,
    }


def _verified_claims(request: Request) -> dict:
    """Verify the caller's Firebase ID token. Raises _AuthError on failure."""
    token = _token_from_request(request)
    if not token:
        raise _AuthError(401, "authentication_error",
                         "Sign in required. Open Zuki → Account to sign in.")
    try:
        return firebase_auth.verify_id_token(token)
    except firebase_auth.CertsUnavailable:
        raise _AuthError(503, "api_error",
                         "Cannot reach Google's token service — try again shortly.")
    except firebase_auth.InvalidToken as e:
        raise _AuthError(401, "authentication_error", str(e))


def current_user(request: Request) -> db.User:
    """Resolve the caller from a Firebase ID token (Bearer or x-api-key)."""
    claims = _verified_claims(request)
    user = db.ensure_user(claims["sub"], claims.get("email"), claims.get("name"))
    if user.disabled:
        raise _AuthError(403, "permission_error", "This account has been disabled.")
    return user


# ── models ───────────────────────────────────────────────────────────────────

class DisableBody(BaseModel):
    disabled: bool


class LimitBody(BaseModel):
    daily_request_limit: Optional[int] = None


class BillingInitBody(BaseModel):
    currency: str = "NGN"
    plan: str = "pro"


# ── account ──────────────────────────────────────────────────────────────────

@app.get("/auth/me")
def me(user: db.User = Depends(current_user)):
    return _user_payload(user, db.get_usage(user.uid))


# ── Flutterwave Billing ──────────────────────────────────────────────────────

@app.post("/v1/billing/initialize")
async def billing_initialize(body: BillingInitBody, user: db.User = Depends(current_user)):
    currency = (body.currency or "NGN").strip().upper()
    amount = 5000 if currency == "NGN" else 10
    tx_ref = f"zuki_{user.uid}_{int(time.time())}"

    redirect_url = f"{config.SERVER_PUBLIC_URL}/billing/callback"
    flw_payload = {
        "tx_ref": tx_ref,
        "amount": amount,
        "currency": currency,
        "redirect_url": redirect_url,
        "customer": {
            "email": user.email,
            "name": user.name or user.email,
        },
        "customizations": {
            "title": "Zuki Pro Subscription",
            "description": f"Monthly Zuki Pro Access ({currency} {amount})",
            "logo": "https://raw.githubusercontent.com/I-m-a-m-4/zuki/main/zuki/shell/assets/icon.ico",
        },
        "meta": {
            "uid": user.uid,
            "plan": body.plan,
        },
    }

    headers = {
        "Authorization": f"Bearer {config.FLUTTERWAVE_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post("https://api.flutterwave.com/v3/payments", json=flw_payload, headers=headers)
            res_data = resp.json()
    except Exception as e:
        return _error(500, "billing_error", f"Failed to connect to Flutterwave: {e}")

    if resp.status_code != 200 or res_data.get("status") != "success":
        msg = res_data.get("message") or "Failed to initiate payment with Flutterwave."
        return _error(400, "billing_error", msg)

    link = (res_data.get("data") or {}).get("link")
    return {"ok": True, "payment_link": link, "tx_ref": tx_ref}


@app.get("/billing/callback")
async def billing_callback(status: Optional[str] = None, tx_ref: Optional[str] = None, transaction_id: Optional[str] = None):
    verified = False
    error_msg = ""
    uid = None

    if transaction_id and config.FLUTTERWAVE_SECRET_KEY:
        try:
            headers = {"Authorization": f"Bearer {config.FLUTTERWAVE_SECRET_KEY}"}
            async with httpx.AsyncClient(timeout=30.0) as client:
                v_resp = await client.get(f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify", headers=headers)
                v_data = v_resp.json()
                if v_resp.status_code == 200 and v_data.get("status") == "success":
                    t_data = v_data.get("data") or {}
                    if t_data.get("status") == "successful":
                        verified = True
                        meta = t_data.get("meta") or {}
                        uid = meta.get("uid")
                        if not uid and tx_ref and tx_ref.startswith("zuki_"):
                            parts = tx_ref.split("_")
                            if len(parts) >= 2:
                                uid = parts[1]
                        if uid:
                            db.upgrade_user_plan(uid, "pro", tx_ref)
        except Exception as e:
            error_msg = str(e)

    if verified:
        html = """
        <!doctype html>
        <html>
        <head><title>Zuki Pro — Payment Successful</title>
        <style>
          body { background: #0b0d12; color: #e8ecf4; font-family: 'Segoe UI', system-ui, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
          .card { background: #141821; border: 1px solid #252c3d; padding: 40px; border-radius: 16px; text-align: center; max-width: 440px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
          h1 { color: #3ddc97; margin: 0 0 12px; font-size: 24px; }
          p { color: #8b93a7; line-height: 1.6; margin: 0 0 24px; }
          .badge { display: inline-block; background: #7c6cff; color: white; padding: 6px 16px; border-radius: 999px; font-weight: 600; font-size: 13px; margin-bottom: 20px; }
        </style>
        </head>
        <body>
          <div class="card">
            <div class="badge">✨ ZUKI PRO ACTIVE</div>
            <h1>Payment Successful!</h1>
            <p>Thank you for subscribing to <b>Zuki Pro</b>. Your account has been upgraded with unlimited access, high-speed inference, and all premium features.</p>
            <p>You can close this tab and return to the Zuki desktop app.</p>
          </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html, status_code=200)
    else:
        html = f"""
        <!doctype html>
        <html>
        <head><title>Payment Incomplete</title>
        <style>
          body {{ background: #0b0d12; color: #e8ecf4; font-family: 'Segoe UI', system-ui, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
          .card {{ background: #141821; border: 1px solid #252c3d; padding: 40px; border-radius: 16px; text-align: center; max-width: 440px; }}
          h1 {{ color: #ff5c6c; margin: 0 0 12px; font-size: 22px; }}
          p {{ color: #8b93a7; line-height: 1.6; margin: 0 0 20px; }}
        </style>
        </head>
        <body>
          <div class="card">
            <h1>Payment Verification Incomplete</h1>
            <p>We could not automatically verify this payment. {error_msg}</p>
            <p>If you were charged, please contact support with reference: <b>{tx_ref or transaction_id}</b>.</p>
          </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html, status_code=400)


@app.post("/v1/billing/webhook")
async def billing_webhook(request: Request):
    secret_hash = config.FLUTTERWAVE_ENCRYPTION_KEY
    signature = request.headers.get("verif-hash")
    if secret_hash and signature != secret_hash:
        return Response(status_code=401)

    try:
        body = await request.json()
    except Exception:
        return Response(status_code=400)

    data = body.get("data") or {}
    status = data.get("status")
    tx_ref = data.get("tx_ref") or ""

    if status == "successful" and tx_ref.startswith("zuki_"):
        meta = data.get("meta") or {}
        uid = meta.get("uid")
        if not uid:
            parts = tx_ref.split("_")
            if len(parts) >= 2:
                uid = parts[1]
        if uid:
            db.upgrade_user_plan(uid, "pro", tx_ref)

    return {"status": "ok"}


# ── Claude proxy ─────────────────────────────────────────────────────────────

def _enforce_quota(user: db.User) -> Optional[JSONResponse]:
    if _is_admin_email(user.email):
        return None
    if getattr(user, "plan_tier", "free") in ("pro", "unlimited", "admin"):
        return None
    limit = config.DAILY_REQUEST_LIMIT if user.daily_request_limit is None else user.daily_request_limit
    if limit is None:
        return None
    usage = db.get_usage(user.uid)
    if usage["requests"] >= limit:
        return _error(
            429, "rate_limit_error",
            f"Daily limit reached ({limit} requests). Resets at midnight UTC, or upgrade to Zuki Pro for unlimited access.",
            headers={"retry-after": "3600"},
        )
    return None



def _enforce_model(body: dict) -> Optional[JSONResponse]:
    model = body.get("model")
    if config.ALLOWED_MODELS and model not in config.ALLOWED_MODELS:
        return _error(400, "invalid_request_error", f"Model '{model}' is not allowed.")
    return None


@app.post("/v1/messages")
async def messages(request: Request, user: db.User = Depends(current_user)):
    quota = _enforce_quota(user)
    if quota is not None:
        return quota
    try:
        body = await request.json()
    except ValueError:
        return _error(400, "invalid_request_error", "Request body must be JSON.")
    blocked = _enforce_model(body)
    if blocked is not None:
        return blocked

    db.bump_usage(user.uid, requests=1)
    headers = dict(request.headers)

    if body.get("stream"):
        status, iterator, resp_headers, error_body = await proxy.forward_stream(
            "/v1/messages", body, headers,
            on_usage=lambda i, o: db.bump_usage(user.uid, input_tokens=i, output_tokens=o),
        )
        if iterator is None:
            return Response(error_body or b"", status_code=status,
                            headers=resp_headers, media_type="application/json")
        return StreamingResponse(iterator, status_code=status,
                                 media_type=resp_headers.get("content-type", "text/event-stream"),
                                 headers=resp_headers)

    status, content, resp_headers = await proxy.forward_json(
        "POST", "/v1/messages", body, headers,
    )
    if status == 200:
        i, o = proxy.parse_usage_json(content)
        db.bump_usage(user.uid, input_tokens=i, output_tokens=o)
    return Response(content, status_code=status, headers=resp_headers,
                    media_type="application/json")


@app.post("/v1/messages/count_tokens")
async def count_tokens(request: Request, _user: db.User = Depends(current_user)):
    try:
        body = await request.json()
    except ValueError:
        return _error(400, "invalid_request_error", "Request body must be JSON.")
    status, content, resp_headers = await proxy.forward_json(
        "POST", "/v1/messages/count_tokens", body, dict(request.headers),
    )
    return Response(content, status_code=status, headers=resp_headers,
                    media_type="application/json")


@app.get("/v1/models")
async def models(request: Request, _user: db.User = Depends(current_user)):
    status, content, resp_headers = await proxy.forward_json(
        "GET", "/v1/models", None, dict(request.headers),
    )
    return Response(content, status_code=status, headers=resp_headers,
                    media_type="application/json")


# ── admin ────────────────────────────────────────────────────────────────────

def require_admin(request: Request) -> None:
    """Admin auth: ADMIN_TOKEN bearer (scripts) or a Firebase account whose
    email is listed in ADMIN_EMAILS (the /admin/ web page)."""
    if not config.ADMIN_TOKEN and not config.ADMIN_EMAILS:
        raise _AuthError(503, "api_error",
                         "Admin API disabled (set ADMIN_TOKEN or ADMIN_EMAILS).")
    token = _token_from_request(request) or ""
    if config.ADMIN_TOKEN and hmac.compare_digest(token, config.ADMIN_TOKEN):
        return
    if config.ADMIN_EMAILS:
        try:
            claims = firebase_auth.verify_id_token(token)
        except firebase_auth.CertsUnavailable:
            raise _AuthError(503, "api_error",
                             "Cannot reach Google's token service — try again shortly.")
        except firebase_auth.InvalidToken:
            raise _AuthError(401, "authentication_error", "Sign in required.")
        if _is_admin_email(claims.get("email")):
            return
        raise _AuthError(403, "permission_error", "This account is not an admin.")
    raise _AuthError(401, "authentication_error", "Invalid admin token.")


@app.get("/admin/")
def admin_page():
    return FileResponse(_STATIC_DIR / "admin.html")


@app.get("/admin")
def admin_redirect():
    return RedirectResponse("/admin/")


@app.get("/admin/users")
def admin_users(_: None = Depends(require_admin)):
    return {"users": db.list_users()}


@app.post("/admin/users/{uid}/disable")
def admin_disable(uid: str, body: DisableBody, _: None = Depends(require_admin)):
    if not db.set_disabled(uid, body.disabled):
        return _error(404, "not_found_error", "No such user.")
    return {"ok": True}


class PlanBody(BaseModel):
    plan_tier: str  # "free" or "pro"


@app.post("/admin/users/{uid}/limit")
def admin_limit(uid: str, body: LimitBody, _: None = Depends(require_admin)):
    if body.daily_request_limit is not None and body.daily_request_limit < 0:
        return _error(400, "invalid_request_error", "Limit must be >= 0 or null.")
    if not db.set_limit(uid, body.daily_request_limit):
        return _error(404, "not_found_error", "No such user.")
    return {"ok": True}


@app.post("/admin/users/{uid}/plan")
def admin_plan(uid: str, body: PlanBody, _: None = Depends(require_admin)):
    if not db.upgrade_user_plan(uid, body.plan_tier):
        return _error(404, "not_found_error", "No such user.")
    return {"ok": True}



# ── misc ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"ok": True, "service": "zuki-account-server", "version": VERSION}


@app.get("/")
def root():
    return {
        "service": "zuki-account-server", "version": VERSION,
        "accounts": "Firebase Auth (client SDK) — server verifies ID tokens",
        "proxy": "POST /v1/messages (Anthropic-compatible)",
        "admin": "GET /admin/",
    }
