from __future__ import annotations

from pathlib import Path

from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = REPO_ROOT / "storage" / "expedientes" / "legalize_mx.db"


class Settings(BaseSettings):
    app_name: str = "legalize-mx expediente backend"
    api_prefix: str = "/api/v1"
    database_url: str = Field(default=f"sqlite+pysqlite:///{DEFAULT_SQLITE_PATH}")
    storage_root: Path = Field(default=REPO_ROOT / "storage" / "expedientes")
    allow_sqlite_fallback: bool = Field(default=True)
    mcp_enabled: bool = False
    oauth_issuer: str | None = None
    oauth_jwks_url: str | None = None
    oauth_resource_url: str | None = None
    oauth_algorithms: list[str] = Field(default_factory=lambda: ["RS256"])
    release_evidence_max_age_seconds: int = Field(default=900, ge=60, le=86400)

    @model_validator(mode="after")
    def validate_mcp_auth(self) -> "Settings":
        if self.mcp_enabled:
            for name in ("oauth_issuer", "oauth_jwks_url", "oauth_resource_url"):
                value = getattr(self, name)
                url = urlsplit(value or "")
                if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
                    raise ValueError(f"{name} must be an explicit HTTPS URL without credentials, query or fragment")
            if not self.oauth_algorithms or not set(self.oauth_algorithms) <= {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "EdDSA"}:
                raise ValueError("oauth_algorithms must contain supported asymmetric algorithms")
            if urlsplit(self.oauth_resource_url).path != "/mcp":
                raise ValueError("oauth_resource_url must identify the /mcp endpoint")
        return self

    model_config = SettingsConfigDict(
        env_prefix="LEGALIZE_MX_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
