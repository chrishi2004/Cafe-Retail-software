import enum
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class DeploymentMode(str, enum.Enum):
    LOCAL_HUB = "local_hub"
    CLOUD_GATEWAY = "cloud_gateway"


def database_target_identity(database_url: str) -> tuple[str | None, int | None, str | None]:
    """Return a password-free identity used only for target-boundary checks."""
    url = make_url(database_url)
    return (url.host, url.port, url.database)


class Settings(BaseSettings):
    app_name: str = "Hybrid Retail BI API"
    environment: str = Field(default="development")
    deployment_mode: DeploymentMode = DeploymentMode.LOCAL_HUB
    api_prefix: str = "/api"
    frontend_origin: str = "http://localhost:5173"
    frontend_extra_origins: str = "http://127.0.0.1:5173"
    api_docs_enabled: bool | None = None
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/hybrid_retail_bi"
    )
    local_database_url: str | None = None
    cloud_runtime_database_url: str | None = None
    cloud_migration_database_url: str | None = None
    cloud_gateway_base_url: str | None = None
    secret_key: str = Field(default="change-me-in-development")
    access_token_expire_minutes: int = 60
    openai_api_key: str | None = None
    security_headers_enabled: bool = True
    openai_model: str = "gpt-4.1-mini"

    # Durable Local Hub synchronization and HC2-HC4 cloud coordination.
    sync_device_id: str | None = None
    sync_device_name: str = "Local Business Hub"
    sync_device_secret: SecretStr | None = None
    sync_device_credential_ref: str = "env:SYNC_DEVICE_SECRET"
    sync_business_group_id: str | None = None
    sync_company_id: str | None = None
    sync_branch_id: str | None = None
    sync_software_version: str = "0.1.0"
    sync_batch_size: int = Field(default=50, ge=1, le=500)
    sync_poll_interval_seconds: float = Field(default=5.0, ge=0.1, le=3600)
    sync_max_attempts: int = Field(default=8, ge=1, le=100)
    sync_base_retry_delay_seconds: float = Field(default=1.0, ge=0.1, le=3600)
    sync_max_retry_delay_seconds: float = Field(default=300.0, ge=1.0, le=86400)
    sync_retry_jitter_ratio: float = Field(default=0.2, ge=0.0, le=1.0)
    heartbeat_interval_seconds: int = Field(default=30, ge=5, le=3600)
    writer_lease_seconds: int = Field(default=90, ge=15, le=86400)
    continuity_stale_after_seconds: int = Field(default=180, ge=30, le=86400)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_deployment_database_configuration(self) -> "Settings":
        if self.deployment_mode == DeploymentMode.CLOUD_GATEWAY and not self.cloud_runtime_database_url:
            raise ValueError(
                "CLOUD_RUNTIME_DATABASE_URL is required when DEPLOYMENT_MODE=cloud_gateway."
            )

        local_target = database_target_identity(self.local_runtime_database_url)
        for name, cloud_url in (
            ("CLOUD_RUNTIME_DATABASE_URL", self.cloud_runtime_database_url),
            ("CLOUD_MIGRATION_DATABASE_URL", self.cloud_migration_database_url),
        ):
            if cloud_url and database_target_identity(cloud_url) == local_target:
                raise ValueError(f"{name} must not target the Local Hub database.")

        if self.sync_base_retry_delay_seconds > self.sync_max_retry_delay_seconds:
            raise ValueError(
                "SYNC_BASE_RETRY_DELAY_SECONDS must not exceed SYNC_MAX_RETRY_DELAY_SECONDS."
            )
        return self

    @property
    def local_runtime_database_url(self) -> str:
        """Resolve the explicit local URL while preserving the legacy setting."""
        return self.local_database_url or self.database_url

    @property
    def runtime_database_url(self) -> str:
        if self.deployment_mode == DeploymentMode.CLOUD_GATEWAY:
            if not self.cloud_runtime_database_url:
                raise RuntimeError("Cloud runtime database is not configured.")
            return self.cloud_runtime_database_url
        return self.local_runtime_database_url

    @property
    def local_migration_database_url(self) -> str:
        return self.local_runtime_database_url

    @property
    def required_cloud_migration_database_url(self) -> str:
        if not self.cloud_migration_database_url:
            raise RuntimeError(
                "CLOUD_MIGRATION_DATABASE_URL is required for cloud migrations."
            )
        return self.cloud_migration_database_url

    @property
    def resolved_api_docs_enabled(self) -> bool:
        if self.api_docs_enabled is not None:
            return self.api_docs_enabled
        return self.environment.lower() not in {"production", "prod"}

    @property
    def cors_origins(self) -> list[str]:
        origins: list[str] = []
        for raw_origins in (self.frontend_origin, self.frontend_extra_origins):
            for origin in raw_origins.split(","):
                cleaned = origin.strip()
                if cleaned and cleaned not in origins:
                    origins.append(cleaned)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
