from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    environment: str = "development"
    # Comma-separated list, e.g. "https://app.example.com,https://staging.example.com".
    # Defaults to the local frontend dev server only — set this explicitly
    # in any deployment with a real frontend origin (see docs/DEPLOYMENT.md).
    cors_allowed_origins_raw: str = Field(default="http://localhost:3000", alias="CORS_ALLOWED_ORIGINS")

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    database_url: str = ""

    redis_url: str = "redis://localhost:6379/0"
    api_rate_limit_per_minute: int = 120
    webhook_signing_secret: str = "change-me-dev-only"

    # Only reachable when the full stack runs locally (backend joins lab-net).
    # Left unset in production deployments of the hosted platform.
    lab_database_url: str = ""
    verification_rate_limit_per_minute: int = 3

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins_raw.split(",") if o.strip()]


settings = Settings()
