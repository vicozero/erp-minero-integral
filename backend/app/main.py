from __future__ import annotations

import uuid
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routers import admin, audit, auth, catalogs, health, inventory, purchasing, requisitions, wms
from app.core.config import settings
from app.core.context import request_id_var

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="ERP local para requisiciones, almacén y compras de prueba.",
)

def _cors_origins() -> list[str]:
    return [origin.strip() for origin in settings.CORS_ALLOW_ORIGINS.split(",") if origin.strip()]


def _allowed_hosts() -> set[str]:
    return {host.strip().lower() for host in settings.ALLOWED_HOSTS.split(",") if host.strip()}


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
)


@app.middleware("http")
async def validate_host_and_origin(request: Request, call_next):
    """Rechaza Host desconocidos y Origen cross-site antes de tocar la API."""
    allowed_hosts = _allowed_hosts()
    host = (request.url.hostname or "").lower()
    if not host or host not in allowed_hosts:
        return JSONResponse(status_code=400, content={"detail": "Host no permitido"})

    origin = request.headers.get("origin")
    if origin:
        try:
            origin_host = (urlsplit(origin).hostname or "").lower()
        except ValueError:
            origin_host = ""
        if not origin_host or origin_host not in allowed_hosts:
            return JSONResponse(status_code=403, content={"detail": "Origen no permitido"})
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Cabeceras mínimas para servir la API y el portal desde el mismo origen."""
    response = await call_next(request)
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Content-Security-Policy": (
            "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; "
            "form-action 'self'; object-src 'none'; connect-src 'self'; "
            "img-src 'self' data: blob:; script-src 'self'; style-src 'self' 'unsafe-inline'"
        ),
    }
    if settings.SECURITY_HSTS_ENABLED:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    for name, value in headers.items():
        if name not in response.headers:
            response.headers[name] = value
    return response


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = request_id_var.set(request_id)
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(health.router)
for modular_router in (
    auth.router,
    admin.router,
    catalogs.router,
    requisitions.router,
    inventory.router,
    purchasing.router,
    wms.router,
    audit.router,
):
    app.include_router(modular_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "ERP MINERO INTEGRAL", "docs": "/docs", "health": "/health"}
