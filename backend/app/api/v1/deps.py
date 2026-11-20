from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import (
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    credential_version,
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
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> AppUser:
    """Acepta cookie de sesión o Bearer ligado a esa misma sesión.

    No existen dos autoridades de autenticación: el Bearer sólo identifica una
    sesión de `seg.user_session`. Si la sesión se revoca, caduca o cambia la
    contraseña, el token deja de servir aunque su `exp` no haya vencido.
    """
    if credentials is not None:
        claims = decode_access_token(credentials.credentials)
        user = db.get(AppUser, claims.user_id)
        if user is None or user.status != "ACTIVE":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo.")
        session = db.get(UserSession, claims.session_id)
        if (
            session is None
            or session.user_id != user.id
            or not IdentityService.is_session_valid(session)
            or credential_version(user.password_changed_at) != claims.credential_version
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión revocada, caducada o credencial modificada.",
            )
        session.last_seen_at = datetime.now(timezone.utc)
        background_tasks.add_task(IdentityService.touch_session, session.id)
        request.state.session_id = session.id
        request.state.session = session
        return user

    session = _session_from_request(db, request)
    if session is not None:
        user = db.get(AppUser, session.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inexistente.")
        if user.status != "ACTIVE":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo.")
        if (
            session.credential_version is None
            or session.credential_version != credential_version(user.password_changed_at)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión revocada, caducada o credencial modificada.",
            )
        session.last_seen_at = datetime.now(timezone.utc)
        background_tasks.add_task(IdentityService.touch_session, session.id)
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
