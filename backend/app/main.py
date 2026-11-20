from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routers import (
    admin,
    audit,
    auth,
    catalogs,
    documentation,
    health,
    inventory,
    purchasing,
    requisitions,
    sla,
    wms,
    wms_designer,
)
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
    return {host.strip().lower().rstrip(".") for host in settings.ALLOWED_HOSTS.split(",") if host.strip()}


def _allowed_origins() -> set[str]:
    return {origin.strip().rstrip("/").lower() for origin in settings.CORS_ALLOW_ORIGINS.split(",") if origin.strip()}


def _trusted_proxy_hosts() -> set[str]:
    return {
        host.strip().lower().rstrip(".")
        for host in settings.TRUSTED_PROXY_HOSTS.split(",")
        if host.strip()
    }


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
)


@app.middleware("http")
async def validate_host_and_origin(request: Request, call_next):
    """Valida Host y Origen completos (incluido puerto) antes de tocar la API."""
    host_header = (request.headers.get("host") or "").strip().lower().rstrip(".")
    if not host_header or host_header not in _allowed_hosts():
        return JSONResponse(status_code=400, content={"detail": "Host no permitido"})

    # Detrás del proxy local del portal, el Header Host que llega a la API es
    # el del backend configurado, mientras que el navegador usa el del portal.
    # Sólo se confía en Forwarded cuando el Host interno está en la lista
    # configurada; el esquema y el host efectivos deben seguir siendo
    # autorizados. El Origin debe coincidir con ese par o estar en la lista
    # explícita de orígenes permitidos (por ejemplo, Vite en desarrollo).
    forwarded_host = (request.headers.get("x-forwarded-host") or "").split(",", 1)[0].strip().lower().rstrip(".")
    trusted_proxy = host_header in _trusted_proxy_hosts()
    effective_host = forwarded_host if trusted_proxy and forwarded_host else host_header
    if effective_host not in _allowed_hosts():
        return JSONResponse(status_code=400, content={"detail": "Host no permitido"})

    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    effective_scheme = forwarded_proto if trusted_proxy and forwarded_proto in {"http", "https"} else request.url.scheme.lower()

    origin = request.headers.get("origin")
    if origin:
        normalized = origin.strip().rstrip("/").lower()
        expected_same_origin = f"{effective_scheme}://{effective_host}"
        if normalized != expected_same_origin and normalized not in _allowed_origins():
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
    documentation.router,
    sla.router,
    wms.router,
    wms_designer.router,
    audit.router,
):
    app.include_router(modular_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "ERP MINERO INTEGRAL", "docs": "/docs", "health": "/health"}
