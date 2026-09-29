"""Passwords (scrypt, standard library), signed session tokens (PyJWT) and the sign-in dependencies."""
import functools
import hashlib
import hmac
import os
import secrets
import time

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import store

TOKEN_HOURS = 12
bearer = HTTPBearer(auto_error=False)


@functools.lru_cache
def _secret() -> str:
    """BILLTRAIL_SECRET if set, else a random key kept in data/secret.key (gitignored)."""
    if os.getenv("BILLTRAIL_SECRET"):
        return os.environ["BILLTRAIL_SECRET"]
    p = store.DATA / "secret.key"
    if not p.exists():
        p.write_text(secrets.token_hex(32))
    return p.read_text().strip()


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    return salt.hex() + "$" + hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32).hex()


def verify_password(pw: str, stored: str) -> bool:
    salt, _, digest = stored.partition("$")
    test = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32).hex()
    return hmac.compare_digest(test, digest)


def make_token(user: dict) -> str:
    return jwt.encode({"sub": user["id"], "exp": int(time.time()) + TOKEN_HOURS * 3600}, _secret(), algorithm="HS256")


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if not cred:
        raise HTTPException(401, "Sign in to continue.")
    try:
        uid = jwt.decode(cred.credentials, _secret(), algorithms=["HS256"])["sub"]
    except jwt.PyJWTError:
        raise HTTPException(401, "Your session has expired. Sign in again.")
    user = store.user_by_id(uid)
    if not user:
        raise HTTPException(401, "Account not found.")
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "Only admins can do this.")
    return user
