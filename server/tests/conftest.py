"""Shared test env — applied before any test module imports server.config."""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-upstream")
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("FIREBASE_PROJECT_ID", "zuki-ai")
