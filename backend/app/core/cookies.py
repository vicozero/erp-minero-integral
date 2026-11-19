from __future__ import annotations

from datetime import datetime, timezone
from math import ceil

from fastapi import Response

from app.core.config import settings
from app.core.security import CSRF_COOKIE_NAME, SESSION_COOKIE_NAME


def _common_kwargs(max_age: int) -> dict:
    kwargs: dict = {
        "path": "/",
        "max_age": max_age,
        "samesite": settings.SESSION_COOKIE_SAMESITE,
        "secure": settings.SESSION_COOKIE_SECURE,
    }
    if settings.SESSION_COOKIE_DOMAIN:
        kwargs["domain"] = settings.SESSION_COOKIE_DOMAIN
    return kwargs


def set_session_cookies(response: Response, session_token: str, csrf_token: str, expires_at: datetime) -> None:
    """Cookie de sesión HttpOnly y cookie CSRF legible por el frontend."""
    remaining = max(1, ceil((expires_at - datetime.now(timezone.utc)).total_seconds()))
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_token,
        httponly=True,
        **_common_kwargs(remaining),
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        httponly=False,
        **_common_kwargs(remaining),
    )


def delete_session_cookies(response: Response) -> None:
    for name in (SESSION_COOKIE_NAME, CSRF_COOKIE_NAME):
        kwargs = _common_kwargs(0)
        response.delete_cookie(
            name,
            path=kwargs["path"],
            samesite=kwargs["samesite"],
            secure=kwargs["secure"],
            domain=kwargs.get("domain"),
        )
