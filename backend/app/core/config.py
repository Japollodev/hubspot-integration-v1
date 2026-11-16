"""Typed application settings loaded from environment variables / .env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "HubSpot CRM Importer"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    log_json: bool = True

    # Directory containing the built React app (index.html + assets/).
    frontend_dist: Path = REPO_ROOT / "frontend" / "dist"
    # Extra CORS origins; only needed if the frontend is served from another origin.
    cors_origins: list[str] = Field(default_factory=list)

    # Upload limits (used from Step 1).
    max_upload_mb: int = 10

    # Postgres. Local Docker in dev/CI; Neon / RDS / Cloud SQL in production.
    # Accepts postgres://, postgresql:// or postgresql+asyncpg:// URLs (sslmode= is honoured).
    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://importer:importer@localhost:5432/importer"
    )
    # Direct (non-pooled) URL for Alembic migrations; falls back to database_url.
    database_url_direct: SecretStr | None = None
    # True when database_url goes through PgBouncer/Neon pooler. None = auto-detect "-pooler".
    db_pooled: bool | None = None
    db_pool_size: int = 5
    db_max_overflow: int = 5

    # Integrations.
    # OpenAI (Step 3). Users bring their own key (X-OpenAI-Key header from the browser).
    # openai_api_key is a DEV-ONLY fallback, ignored when environment == "production".
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"  # must support vision + structured outputs
    openai_api_base: str = "https://api.openai.com/v1"
    openai_timeout_s: float = 60.0
    openai_max_image_px: int = 2048  # long-edge cap for the copy sent to OpenAI
    # HubSpot private-app token (test account). Needs the `files` scope from Step 1.
    hubspot_access_token: SecretStr | None = None
    hubspot_api_base: str = "https://api.hubapi.com"
    hubspot_files_folder: str = "/crm-importer/uploads"
    hubspot_timeout_s: float = 30.0

    @property
    def server_openai_key(self) -> str | None:
        """The .env key, only outside production (prod must never use a developer key)."""
        if self.environment == "production" or self.openai_api_key is None:
            return None
        return self.openai_api_key.get_secret_value() or None

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
