"""SQLite storage: user records and daily usage. Stdlib only.

Accounts are Firebase identities (uid); this DB only keeps the operational
state the proxy needs — disabled flag, per-user caps, and usage counters.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import config

_lock = threading.Lock()
_db_path: Path = config.DB_PATH


def set_db_path(path: Path | str) -> None:
    global _db_path
    _db_path = Path(path)
    _db_path.parent.mkdir(parents=True, exist_ok=True)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    with _lock, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                uid TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                disabled INTEGER NOT NULL DEFAULT 0,
                daily_request_limit INTEGER,
                plan_tier TEXT NOT NULL DEFAULT 'free',
                subscription_ref TEXT,
                subscription_status TEXT NOT NULL DEFAULT 'none'
            );
            CREATE TABLE IF NOT EXISTS usage (
                uid TEXT NOT NULL REFERENCES users(uid),
                day TEXT NOT NULL,
                requests INTEGER NOT NULL DEFAULT 0,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (uid, day)
            );
            """
        )
        # Migration for existing databases
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "plan_tier" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN plan_tier TEXT NOT NULL DEFAULT 'free'")
        if "subscription_ref" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN subscription_ref TEXT")
        if "subscription_status" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN subscription_status TEXT NOT NULL DEFAULT 'none'")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── users ────────────────────────────────────────────────────────────────────

@dataclass
class User:
    uid: str
    email: str
    name: Optional[str]
    created_at: str
    last_seen: str
    disabled: bool
    daily_request_limit: Optional[int]
    plan_tier: str = "free"
    subscription_ref: Optional[str] = None
    subscription_status: str = "none"

    @staticmethod
    def from_row(row: sqlite3.Row) -> "User":
        keys = row.keys()
        return User(
            uid=row["uid"], email=row["email"], name=row["name"],
            created_at=row["created_at"], last_seen=row["last_seen"],
            disabled=bool(row["disabled"]),
            daily_request_limit=row["daily_request_limit"],
            plan_tier=row["plan_tier"] if "plan_tier" in keys else "free",
            subscription_ref=row["subscription_ref"] if "subscription_ref" in keys else None,
            subscription_status=row["subscription_status"] if "subscription_status" in keys else "none",
        )


def ensure_user(uid: str, email: str, name: Optional[str] = None) -> User:
    """Auto-provision on first sight; refresh email/name/last_seen afterwards."""
    email = (email or "").strip().lower() or f"{uid}@firebase.local"
    name = (name or "").strip() or None
    now = _now()
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (uid, email, name, created_at, last_seen) "
            "VALUES (?,?,?,?,?)",
            (uid, email, name, now, now),
        )
        conn.execute(
            "UPDATE users SET email = ?, name = COALESCE(?, name), last_seen = ? WHERE uid = ?",
            (email, name, now, uid),
        )
        row = conn.execute("SELECT * FROM users WHERE uid = ?", (uid,)).fetchone()
    return User.from_row(row)


def upgrade_user_plan(uid: str, plan_tier: str = "pro", ref: Optional[str] = None) -> bool:
    """Upgrade user plan and update subscription reference."""
    with _lock, _connect() as conn:
        cur = conn.execute(
            "UPDATE users SET plan_tier = ?, subscription_ref = ?, subscription_status = 'active' WHERE uid = ?",
            (plan_tier, ref, uid),
        )
        return cur.rowcount > 0


def get_user(uid: str) -> Optional[User]:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE uid = ?", (uid,)).fetchone()
    return User.from_row(row) if row else None


def list_users() -> list[dict]:
    with _lock, _connect() as conn:
        rows = conn.execute(
            """SELECT u.*,
                      IFNULL(g.requests, 0) AS requests_today,
                      IFNULL(g.input_tokens, 0) AS input_tokens_today,
                      IFNULL(g.output_tokens, 0) AS output_tokens_today,
                      IFNULL(t.requests, 0) AS requests_total,
                      IFNULL(t.input_tokens, 0) + IFNULL(t.output_tokens, 0) AS tokens_total
               FROM users u
               LEFT JOIN usage g ON g.uid = u.uid AND g.day = ?
               LEFT JOIN (SELECT uid, SUM(requests) AS requests,
                                 SUM(input_tokens) AS input_tokens,
                                 SUM(output_tokens) AS output_tokens
                          FROM usage GROUP BY uid) t ON t.uid = u.uid
               ORDER BY u.created_at DESC, u.uid""",
            (today(),),
        ).fetchall()
    return [
        {
            "uid": r["uid"], "email": r["email"], "name": r["name"],
            "created_at": r["created_at"], "last_seen": r["last_seen"],
            "disabled": bool(r["disabled"]),
            "daily_request_limit": r["daily_request_limit"],
            "plan_tier": r["plan_tier"] if "plan_tier" in r.keys() else "free",
            "subscription_ref": r["subscription_ref"] if "subscription_ref" in r.keys() else None,
            "subscription_status": r["subscription_status"] if "subscription_status" in r.keys() else "none",
            "requests_today": r["requests_today"],
            "input_tokens_today": r["input_tokens_today"],
            "output_tokens_today": r["output_tokens_today"],
            "requests_total": r["requests_total"],
            "tokens_total": r["tokens_total"],
        }
        for r in rows
    ]



def set_disabled(uid: str, disabled: bool) -> bool:
    with _lock, _connect() as conn:
        cur = conn.execute("UPDATE users SET disabled = ? WHERE uid = ?",
                           (int(disabled), uid))
        return cur.rowcount > 0


def set_limit(uid: str, limit: Optional[int]) -> bool:
    with _lock, _connect() as conn:
        cur = conn.execute(
            "UPDATE users SET daily_request_limit = ? WHERE uid = ?", (limit, uid)
        )
        return cur.rowcount > 0


# ── usage ────────────────────────────────────────────────────────────────────

def bump_usage(uid: str, requests: int = 0, input_tokens: int = 0, output_tokens: int = 0) -> None:
    if requests == 0 and input_tokens == 0 and output_tokens == 0:
        return
    with _lock, _connect() as conn:
        conn.execute(
            """INSERT INTO usage (uid, day, requests, input_tokens, output_tokens)
               VALUES (?,?,?,?,?)
               ON CONFLICT(uid, day) DO UPDATE SET
                 requests = requests + excluded.requests,
                 input_tokens = input_tokens + excluded.input_tokens,
                 output_tokens = output_tokens + excluded.output_tokens""",
            (uid, today(), requests, input_tokens, output_tokens),
        )


def get_usage(uid: str) -> dict:
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT * FROM usage WHERE uid = ? AND day = ?", (uid, today())
        ).fetchone()
    return {
        "requests": row["requests"] if row else 0,
        "input_tokens": row["input_tokens"] if row else 0,
        "output_tokens": row["output_tokens"] if row else 0,
    }
