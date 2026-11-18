from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_NAME: str = "ERP MINERO INTEGRAL"
    ENV: str = "local"
    API_V1_PREFIX: str = "/api/v1"
    TIMEZONE: str = "America/Mexico_City"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    DATABASE_URL: str
    SECRET_KEY: str
    DEMO_PASSWORD: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # Pydantic resuelve los campos desde el entorno.


settings = get_settings()
