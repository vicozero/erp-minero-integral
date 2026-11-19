from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, status

from app.core.config import settings

_ALGORITHM = "HS256"
_MAX_BCRYPT_BYTES = 72

SESSION_COOKIE_NAME = "erp_session"
CSRF_COOKIE_NAME = "erp_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"

# Argon2id: 64 MiB, 3 iteraciones, 4 hilos. Parámetros explícitos para que el
# hash resultante sea portable y no dependa de valores por defecto de librería.
_password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)


def hash_password(password: str) -> str:
    """Devuelve un hash Argon2id en formato PHC."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica Argon2id y, transitoriamente, hashes bcrypt de la Fase 2.

    El soporte bcrypt permite que las cuentas ya sembradas sigan entrando; el
    primer inicio de sesión exitoso reescribe el hash a Argon2id.
    """
    if not password_hash:
        return False
    if password_hash.startswith("$argon2"):
        try:
            return bool(_password_hasher.verify(password_hash, password))
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
    if password_hash.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            raw = password.encode("utf-8")
            if len(raw) > _MAX_BCRYPT_BYTES:
                return False
            return bool(bcrypt.checkpw(raw, password_hash.encode("utf-8")))
        except (ValueError, TypeError):
            return False
    return False


def needs_password_upgrade(password_hash: str) -> bool:
    return not password_hash.startswith("$argon2")


def generate_session_token() -> str:
    """Token opaco de 256 bits. Se entrega solo en cookie HttpOnly."""
    return secrets.token_urlsafe(32)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash SHA-256 deterministic para buscar sesiones sin guardar el token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)


def create_access_token(user_id: UUID) -> str:
    """Compatibilidad con clientes Bearer existentes y pruebas de integración."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "typ": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
        ) from exc
    if payload.get("typ") != "access" or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")
    try:
        return UUID(str(payload["sub"]))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.") from exc
