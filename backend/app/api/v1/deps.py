from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import (
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    decode_access_token,
    hash_token,
    tokens_equal,
)
from app.db.session import get_db
from app.modules.identity.models import AppUser, UserSession
from app.modules.identity.service import IdentityService

bearer = HTTPBearer(auto_error=False)
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _session_from_request(db: Session, request: Request) -> UserSession | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    session = IdentityService.session_by_token(db, token)
    if session is None or not IdentityService.is_session_valid(session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inexistente, caducada o revocada.",
        )
    if request.method in _UNSAFE_METHODS:
        supplied = request.headers.get(CSRF_HEADER_NAME, "")
        if not supplied or not tokens_equal(hash_token(supplied), session.csrf_hash):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Falta el token CSRF válido.",
            )
    return session


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> AppUser:
    """Acepta cookie de sesión (portal) o Bearer (integraciones heredadas).

    Las peticiones con cookie requieren CSRF en métodos que modifican estado.
    La autenticación por Bearer se conserva para compatibilidad con clientes
    internos de la Fase 2 y las pruebas de regresión.
    """
    # Bearer explícito gana sobre la cookie: clientes internos y pruebas de
    # integración no deben verse afectados por la cookie del portal web.
    if credentials is not None:
        user_id = decode_access_token(credentials.credentials)
        user = db.get(AppUser, user_id)
        if user is None or user.status != "ACTIVE":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo.")
        request.state.session_id = None
        return user

    session = _session_from_request(db, request)
    if session is not None:
        user = db.get(AppUser, session.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inexistente.")
        if user.status != "ACTIVE":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo.")
        session.last_seen_at = datetime.now(timezone.utc)
        request.state.session_id = session.id
        request.state.session = session
        return user

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No hay sesión activa.")


def require_permission(code: str) -> Callable[..., AppUser]:
    def dependency(
        current_user: AppUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> AppUser:
        if current_user.must_change_password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Debe cambiar su contraseña temporal antes de continuar.",
            )
        if not IdentityService.has_permission(db, current_user.id, code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso requerido: {code}",
            )
        return current_user

    return dependency


def require_any_permission(*codes: str) -> Callable[..., AppUser]:
    def dependency(
        current_user: AppUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> AppUser:
        if current_user.must_change_password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Debe cambiar su contraseña temporal antes de continuar.",
            )
        if not any(IdentityService.has_permission(db, current_user.id, code) for code in codes):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes.")
        return current_user

    return dependency
