"""Shared test env — applied before any test module imports server.config."""

from __future__ import annotations

import os

os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-upstream"
os.environ["ANTHROPIC_BASE_URL"] = "https://api.anthropic.com"
os.environ["ADMIN_TOKEN"] = "test-admin-token"
os.environ["FIREBASE_PROJECT_ID"] = "zuki-ai"

