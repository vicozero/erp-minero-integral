from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["Salud"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.ENV}


@router.get("/status")
def status() -> dict[str, str]:
    return {
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "timezone": settings.TIMEZONE,
        "inventory_authority": "CONTPAQi (sistema oficial)",
    }
