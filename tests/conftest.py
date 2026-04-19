"""Imposta env prima di qualsiasi import dell'app (SQLite in test)."""
from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./pytest_agent.db"
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_must_be_32_chars_ok"
os.environ["JWT_REFRESH_SECRET_KEY"] = "test_refresh_secret_key_32_chars_ok"
os.environ["SMTP_ENABLED"] = "false"
os.environ["LOG_JSON"] = "false"
