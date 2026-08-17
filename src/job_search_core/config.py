"""Typed runtime configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process settings for the Core HTTP server.

    The ``JOB_SEARCH_CORE_`` prefix prevents collisions with sibling services.
    PostgreSQL credentials come from the runtime database URL. The development
    default is intentionally local-only and must be replaced by deployment
    secret injection outside a developer workstation.
    """

    model_config = SettingsConfigDict(env_prefix="JOB_SEARCH_CORE_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://job_search:job_search@127.0.0.1:5432/job_search"
