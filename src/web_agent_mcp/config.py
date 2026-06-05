"""Configuration management using pydantic-settings."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WEB_AGENT_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8103
    mcp_path: str = "/mcp"

    searxng_base_url: str = "http://searxng:8080"

    cache_dir: str = "/app/cache"
    index_dir: str = "/app/index"

    # Comma-separated list of allowed local roots for local_path access
    allowed_local_roots: str = "/app/docs"

    # When True, private/loopback addresses are allowed in web_read URLs
    allow_private_network: bool = False

    @property
    def allowed_local_roots_list(self) -> list[str]:
        return [r.strip() for r in self.allowed_local_roots.split(",") if r.strip()]


settings = Settings()
