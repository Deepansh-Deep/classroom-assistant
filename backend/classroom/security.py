"""JWT sessions and encryption of stored Google tokens.

v1 built its Fernet key by padding the secret with "0" characters and slicing it
to 32 bytes: a short secret produced a weak, partly predictable key. Here the key
is derived with HKDF-SHA256 from SECRET_KEY, which is required to be >= 32 chars.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import jwt
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .db import User, get_db

_bearer = HTTPBearer(auto_error=False)


@lru_cache
def _fernet() -> Fernet:
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"classroom-assistant/token-encryption", info=b"fernet-v1")
    key = hkdf.derive(get_settings().secret_key.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def issue_token(user: User) -> str:
    s = get_settings()
    payload = {"sub": user.id, "role": user.role, "exp": datetime.now(timezone.utc) + timedelta(minutes=s.jwt_minutes)}
    return jwt.encode(payload, s.secret_key, algorithm="HS256")


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)) -> User:
    if not creds:
        raise HTTPException(401, "Not signed in")
    try:
        data = jwt.decode(creds.credentials, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired, please sign in again")
    user = db.get(User, data["sub"])
    if not user:
        raise HTTPException(401, "User no longer exists")
    return user


def require_teacher(user: User = Depends(current_user)) -> User:
    if user.role != "teacher":
        raise HTTPException(403, "Teachers only")
    return user
