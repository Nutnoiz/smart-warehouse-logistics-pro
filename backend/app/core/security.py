import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
import jwt
from app.core.config import settings

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return f"pbkdf2_sha256$210000${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"

def verify_password(password: str, encoded: str) -> bool:
    try:
        _, rounds, salt, expected = encoded.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(rounds))
        return hmac.compare_digest(base64.b64encode(digest).decode(), expected)
    except (ValueError, TypeError):
        return False

def create_access_token(subject: str, version: int = 0) -> str:
    payload = {"sub": subject, "ver": version, "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.token_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

def decode_access_token(token: str) -> str | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])["sub"]
    except (jwt.InvalidTokenError, KeyError):
        return None

def decode_claims(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], options={"require": ["sub", "exp", "ver"]})
    except jwt.InvalidTokenError:
        return None
