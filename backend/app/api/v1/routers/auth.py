from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.config import settings
from app.core.cookies import delete_session_cookies, set_session_cookies
from app.core.security import (
    create_access_token,
    credential_version,
    generate_csrf_token,
    generate_session_token,
    hash_token,
)
from app.db.session import get_db
from app.modules.identity.models import AppUser, UserSession
from app.modules.audit.service import AuditService, hash_ip
from app.modules.identity.schemas import (
    ChangePasswordIn,
    LoginRequest,
    SessionOut,
    SessionResponse,
    UserOut,
    UsernameIn,
)
from app.modules.identity.service import AuthenticationError, IdentityService

router = APIRouter(prefix="/auth", tags=["Seguridad"])


@router.post("/login", response_model=SessionResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    """Inicio de sesión. Devuelve además un JWT heredado para clientes internos."""
    try:
        result = IdentityService.authenticate(
            db,
            payload.username,
            payload.password,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except AuthenticationError as exc:
        # Se confirma el registro del intento fallido; nunca se guarda la
        # contraseña, solo el motivo y el hash de IP.
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.detail) from exc

    db.commit()
    set_session_cookies(response, result.session_token, result.csrf_token, result.expires_at)
    return SessionResponse(
        access_token=create_access_token(
            result.user.id,
            result.session.id,
            credential_version(result.user.password_changed_at),
        ),
        token_type="bearer",
        csrf_token=result.csrf_token,
        expires_at=result.expires_at,
        must_change_password=bool(result.user.must_change_password),
        user=UserOut(**IdentityService.user_out(db, result.user)),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    session = getattr(request.state, "session", None)
    if isinstance(session, UserSession):
        IdentityService.revoke_session(db, session, current_user.id)
        AuditService.record(
            db,
            action="LOGOUT",
            entity_type="AppUser",
            entity_id=current_user.id,
            actor_id=current_user.id,
            actor_username=current_user.username,
        )
        db.commit()
    delete_session_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
def me(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    return UserOut(**IdentityService.user_out(db, current_user))


@router.patch("/username", response_model=UserOut)
def change_username(
    payload: UsernameIn,
    request: Request,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    """Cambia el usuario propio, exige contraseña actual y cierra otras sesiones."""
    session = getattr(request.state, "session", None)
    keep_session_id = session.id if isinstance(session, UserSession) else None
    updated = IdentityService.change_username(
        db,
        current_user.id,
        payload,
        current_user.id,
        keep_session_id=keep_session_id,
    )
    db.commit()
    return UserOut(**IdentityService.user_out(db, updated))


@router.post("/change-password", response_model=SessionResponse)
def change_password(
    payload: ChangePasswordIn,
    request: Request,
    response: Response,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionResponse:
    IdentityService.change_password(
        db,
        current_user.id,
        payload.current_password,
        payload.new_password,
        current_user.id,
    )
    # Se emite una sesión nueva: las anteriores quedan revocadas y el Bearer
    # anterior deja de ser aceptado porque apuntaba a una sesión revocada.
    now = datetime.now(timezone.utc)
    session_token = generate_session_token()
    csrf_token = generate_csrf_token()
    expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    new_session = UserSession(
        user_id=current_user.id,
        token_hash=hash_token(session_token),
        csrf_hash=hash_token(csrf_token),
        credential_version=credential_version(current_user.password_changed_at),
        created_at=now,
        expires_at=expires_at,
        last_seen_at=now,
        ip_hash=hash_ip(request.client.host if request.client else None),
        user_agent_hash=None,
    )
    db.add(new_session)
    db.flush()
    db.commit()
    set_session_cookies(response, session_token, csrf_token, expires_at)
    return SessionResponse(
        access_token=create_access_token(
            current_user.id,
            new_session.id,
            credential_version(current_user.password_changed_at),
        ),
        csrf_token=csrf_token,
        expires_at=expires_at,
        must_change_password=False,
        user=UserOut(**IdentityService.user_out(db, current_user)),
    )


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.execute(
        select(UserSession)
        .where(UserSession.user_id == current_user.id, UserSession.revoked_at.is_(None))
        .order_by(UserSession.created_at.desc())
    ).scalars()
    return [
        {
            "id": str(row.id),
            "user_id": str(row.user_id),
            "created_at": row.created_at,
            "expires_at": row.expires_at,
            "last_seen_at": row.last_seen_at,
            "revoked_at": row.revoked_at,
        }
        for row in rows
    ]


@router.post("/sessions/{session_id}/revoke", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: uuid.UUID,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    session = db.get(UserSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión inexistente.")
    IdentityService.revoke_session(db, session, current_user.id)
    AuditService.record(
        db,
        action="SESSION_REVOKED",
        entity_type="UserSession",
        entity_id=session.id,
        actor_id=current_user.id,
        actor_username=current_user.username,
    )
    db.commit()
