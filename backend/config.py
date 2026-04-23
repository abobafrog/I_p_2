from __future__ import annotations

import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "froggy_coder.db"
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]
SESSION_COOKIE_NAME = "froggy_session"
CSRF_COOKIE_NAME = "froggy_csrf"

load_dotenv(BASE_DIR / ".env", override=False)


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_csv(value: str | None, default: List[str]) -> List[str]:
    if value is None:
        return default

    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or default


def get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value

    raise RuntimeError(
        f"Environment variable {name} is required. Add it to .env or your deployment secrets."
    )


def get_admin_username() -> str:
    return os.getenv("FROGGY_ADMIN_USERNAME", "frog_admin").strip() or "frog_admin"


def get_admin_password() -> str:
    return get_required_env("FROGGY_ADMIN_PASSWORD")


def get_database_path() -> Path:
    override = os.getenv("FROGGY_DB_PATH", "").strip()
    if override:
        return Path(override)
    return DEFAULT_DB_PATH


def get_allowed_origins() -> List[str]:
    return _parse_csv(os.getenv("FROGGY_ALLOWED_ORIGINS"), DEFAULT_ALLOWED_ORIGINS)


def get_cookie_secure() -> bool:
    return _parse_bool(os.getenv("FROGGY_COOKIE_SECURE"), default=False)


def get_cookie_samesite() -> str:
    value = os.getenv("FROGGY_COOKIE_SAMESITE", "lax").strip().lower()
    if value in {"lax", "strict", "none"}:
        return value
    return "lax"


def get_translation_api_base_url() -> str:
    return os.getenv("FROGGY_TRANSLATION_API_BASE_URL", "").strip()


def get_translation_api_key() -> str:
    return os.getenv("FROGGY_TRANSLATION_API_KEY", "").strip()


def get_translation_timeout_seconds() -> float:
    raw_value = os.getenv("FROGGY_TRANSLATION_TIMEOUT_SECONDS", "5").strip()
    try:
        return max(1.0, float(raw_value))
    except ValueError:
        return 5.0
