from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routers import audit, auth, catalogs, health, inventory, purchasing, requisitions
from app.core.config import settings
from app.core.context import request_id_var

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="ERP local para requisiciones, almacén y compras de prueba.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
for modular_router in (auth.router, catalogs.router, requisitions.router, inventory.router, purchasing.router, audit.router):
    app.include_router(modular_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "ERP MINERO INTEGRAL", "docs": "/docs", "health": "/health"}
