import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import Depends, HTTPException, Request, Response, status
from sqlite3 import Connection

from backend.config import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    get_cookie_samesite,
    get_cookie_secure,
)
from backend.db import delete_expired_sessions, get_db, get_session_record, serialize_user_row


SESSION_DAYS = 30
PASSWORD_ITERATIONS = 390000


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str, salt: Optional[str] = None) -> tuple:
    salt_value = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_value),
        PASSWORD_ITERATIONS,
    )
    return salt_value, digest.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    _, computed_hash = hash_password(password, salt)
    return hmac.compare_digest(computed_hash, expected_hash)


def create_session_tokens() -> tuple[str, str, str]:
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    expires_at = utc_now() + timedelta(days=SESSION_DAYS)
    return session_token, csrf_token, expires_at.isoformat()


def set_session_cookies(response: Response, session_token: str) -> None:
    max_age = SESSION_DAYS * 24 * 60 * 60
    secure = get_cookie_secure()
    samesite = get_cookie_samesite()

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=max_age,
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    secure = get_cookie_secure()
    samesite = get_cookie_samesite()

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=secure,
        samesite=samesite,
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path="/",
        secure=secure,
        samesite=samesite,
    )


def require_session(
    request: Request,
    conn: Connection = Depends(get_db),
) -> Dict:
    session_token = (request.cookies.get(SESSION_COOKIE_NAME) or "").strip()
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Нужна авторизация.",
        )

    delete_expired_sessions(conn)
    session = get_session_record(conn, session_token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия истекла или токен неверный.",
        )

    return {
        "token": session["session_token"],
        "csrf_token": session["session_csrf_token"],
        "user": serialize_user_row(session),
    }


def require_csrf(
    request: Request,
    session: Dict = Depends(require_session),
) -> Dict:
    header_token = (request.headers.get("X-CSRF-Token") or "").strip()
    session_token = str(session.get("csrf_token") or "").strip()

    if (
        not header_token
        or not session_token
        or not hmac.compare_digest(header_token, session_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token отсутствует или неверен.",
        )

    return session


def require_user(session: Dict = Depends(require_session)) -> dict:
    return session["user"]


def require_admin(user: dict = Depends(require_user)) -> dict:
    if not user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор может выполнять это действие.",
        )
    return user
