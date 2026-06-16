from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from the environment (12-factor). No secrets in code."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Job Finder"
    environment: str = "development"
    log_level: str = "INFO"

    postgres_user: str = "jobfinder"
    postgres_password: str = "jobfinder"
    postgres_db: str = "jobfinder"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    redis_url: str = "redis://redis:6379/0"

    # Source credentials
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    # LLM provider — either/or, selected at runtime (used from Phase 2 onward).
    # Set LLM_PROVIDER and the matching key + a model valid for that provider; the
    # other provider's key is ignored. Both SDKs are installed so switching is
    # config-only (no rebuild), but only one provider is ever active at a time.
    llm_provider: str = "anthropic"  # "anthropic" | "openai"
    llm_model: str = "claude-sonnet-4-6"  # a model id valid for the selected provider
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
