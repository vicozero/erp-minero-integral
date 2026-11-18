from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.modules.identity.models import AppUser
from app.modules.identity.schemas import LoginRequest, TokenResponse, UserOut
from app.modules.identity.service import IdentityService

router = APIRouter(prefix="/auth", tags=["Seguridad"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    user = IdentityService.authenticate(
        db,
        payload.username,
        payload.password,
        ip=request.client.host if request.client else None,
    )
    if user is None:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas.")
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(current_user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    return UserOut(
        id=str(current_user.id),
        username=current_user.username,
        full_name=current_user.full_name,
        roles=IdentityService.role_codes(db, current_user.id),
    )
