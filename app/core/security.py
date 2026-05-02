from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    pw = (password or "").encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw, salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw((password or "").encode("utf-8"), (hashed or "").encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, uid: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "uid": uid, "type": "access", "exp": exp}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str, uid: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.refresh_token_expire_minutes)
    payload = {"sub": subject, "uid": uid, "type": "refresh", "exp": exp}
    return jwt.encode(payload, settings.jwt_refresh_secret_key, algorithm=settings.jwt_algorithm)
