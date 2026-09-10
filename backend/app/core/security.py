"""Password hashing, JWT, Fernet credential encryption. No secrets logged."""
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
import bcrypt
from cryptography.fernet import Fernet, InvalidToken
import base64
import hashlib
import os

from .config import get_settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet
    s = get_settings()
    key = (s.APP_ENCRYPTION_KEY or "").strip()
    if key:
        # Accept raw Fernet key or arbitrary passphrase (derive)
        try:
            Fernet(key.encode())
            _fernet = Fernet(key.encode())
            return _fernet
        except Exception:
            digest = hashlib.sha256(key.encode()).digest()
            _fernet = Fernet(base64.urlsafe_b64encode(digest))
            return _fernet
    # Dev fallback: derive from secret key (stable across restarts so DB survives)
    digest = hashlib.sha256(("fernet:" + s.APP_SECRET_KEY).encode()).digest()
    _fernet = Fernet(base64.urlsafe_b64encode(digest))
    return _fernet


def reset_fernet_cache():
    global _fernet
    _fernet = None


# --- passwords (bcrypt directly, no passlib) ---
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode()[:72], hashed.encode())
    except Exception:
        return False


# --- JWT ---
def create_token(sub: str) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": sub, "exp": exp}, s.APP_SECRET_KEY, algorithm=s.JWT_ALGORITHM)


def decode_token(token: str) -> str | None:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.APP_SECRET_KEY, algorithms=[s.JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


# --- credential encryption (SSH password / private key) ---
def encrypt_secret(plain: str) -> str:
    if not plain:
        return ""
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    if not token:
        return ""
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        raise ValueError("Cannot decrypt credential (wrong APP_ENCRYPTION_KEY?)")
