from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = REPO_ROOT / "storage" / "expedientes" / "legalize_mx.db"


class Settings(BaseSettings):
    app_name: str = "legalize-mx expediente backend"
    api_prefix: str = "/api/v1"
    database_url: str = Field(default=f"sqlite+pysqlite:///{DEFAULT_SQLITE_PATH}")
    storage_root: Path = Field(default=REPO_ROOT / "storage" / "expedientes")
    allow_sqlite_fallback: bool = Field(default=True)

    model_config = SettingsConfigDict(
        env_prefix="LEGALIZE_MX_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
