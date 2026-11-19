from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# El repositorio vive en E:\ERP_MINERO; este archivo está en
# E:\ERP_MINERO\backend\app\core\config.py. La ruta absoluta evita depender
# del directorio de trabajo al ejecutar pytest, alembic o uvicorn.
# ERP_ENV_FILE permite seleccionar un perfil alternativo (por ejemplo
# `.env.pilot`) sin sobrescribir el `.env` local existente.
DEFAULT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
ENV_FILE = Path(os.getenv("ERP_ENV_FILE", str(DEFAULT_ENV_FILE)))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_NAME: str = "ERP MINERO INTEGRAL"
    ENV: str = "local"
    API_V1_PREFIX: str = "/api/v1"
    TIMEZONE: str = "America/Mexico_City"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # El portal se sirve desde el mismo origen que la API, por lo que no
    # necesita CORS. Los orígenes por defecto solo cubren el servidor de
    # desarrollo de Vite en localhost; el perfil piloto puede dejarlos vacíos.
    CORS_ALLOW_ORIGINS: str = "http://127.0.0.1:5173,http://localhost:5173"
    SECURITY_HSTS_ENABLED: bool = False

    # Cookies de sesión del portal web. Secure debe activarse únicamente cuando
    # el ERP se sirva por HTTPS (intranet con TLS).
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SAMESITE: str = "lax"
    SESSION_COOKIE_DOMAIN: str | None = None

    DATABASE_URL: str = Field(repr=False)
    SECRET_KEY: str = Field(repr=False)
    DEMO_PASSWORD: str | None = Field(default=None, repr=False)

    # Almacenamiento controlado de adjuntos. Fuera del repositorio y de la base.
    ATTACHMENT_STORAGE_DIR: Path = Path(__file__).resolve().parents[3] / "var" / "attachments"
    ATTACHMENT_MAX_BYTES: int = Field(default=5 * 1024 * 1024, gt=0)

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL debe usar el driver postgresql+psycopg")
        if "@127.0.0.1" not in value and "@localhost" not in value:
            raise ValueError("DATABASE_URL debe apuntar a localhost (127.0.0.1)")
        return value

    @field_validator("SESSION_COOKIE_SAMESITE")
    @classmethod
    def validate_samesite(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("SESSION_COOKIE_SAMESITE debe ser lax, strict o none")
        return normalized

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        if len(value) < 16:
            raise ValueError("SECRET_KEY debe tener al menos 16 caracteres")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # Pydantic resuelve los campos desde el entorno.


settings = get_settings()
