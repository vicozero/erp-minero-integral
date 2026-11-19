from __future__ import annotations

from fastapi import APIRouter
from fastapi import status as http_status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.session import check_database_connection

router = APIRouter(tags=["Salud"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.ENV}


@router.get("/health/db")
def health_db() -> JSONResponse:
    """Verifica la conexión a PostgreSQL sin revelar URL, usuario ni errores internos."""
    if check_database_connection():
        return JSONResponse(
            status_code=http_status.HTTP_200_OK,
            content={"status": "ok", "database": "postgresql"},
        )
    return JSONResponse(
        status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "unavailable", "database": "postgresql"},
    )


@router.get("/status")
def status() -> dict[str, str]:
    return {
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "timezone": settings.TIMEZONE,
        "inventory_authority": "CONTPAQi (sistema oficial)",
    }
