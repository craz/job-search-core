"""Typed runtime configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process settings for the Core HTTP server.

    The ``JOB_SEARCH_CORE_`` prefix prevents collisions with sibling services.
    Secrets are deliberately absent until PostgreSQL is introduced; future
    credentials must come from runtime environment, never committed files.
    """

    model_config = SettingsConfigDict(env_prefix="JOB_SEARCH_CORE_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
