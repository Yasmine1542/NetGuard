"""aiops-engine configuration.

The lifted ``aiops`` package reads some env vars directly (the agents/tools use
``GROQ_API_KEY``, ``GROQ_MODEL``, ``PROMETHEUS_URL``, ``LOKI_URL``, ``AIOPS_DB_URL``).
This Settings object only surfaces the few values the service wrapper needs and
makes the missing-secret situation explicit at startup.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        protected_namespaces=(),
    )

    # Read with explicit aliases (no prefix) so they match what the lifted
    # package already expects from the environment.
    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")
    groq_model: str = Field(default="openai/gpt-oss-120b", validation_alias="GROQ_MODEL")
    db_url: str = Field(default="", validation_alias="AIOPS_DB_URL")
    cors_origins: list[str] = Field(default_factory=list, validation_alias="AIOPS_CORS_ORIGINS")
    # Shared secret for the Alertmanager webhook. Empty = open (local dev); when
    # set, callers must send `Authorization: Bearer <token>`.
    webhook_token: str = Field(default="", validation_alias="AIOPS_WEBHOOK_TOKEN")


settings = Settings()
