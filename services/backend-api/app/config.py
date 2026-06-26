"""backend-api configuration — all values from the environment (``API_`` prefix)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="API_",
        env_file=".env",
        extra="ignore",
        protected_namespaces=(),
    )

    redis_url: str = "redis://redis:6379/0"
    inference_url: str = "http://inference:8000"
    aiops_url: str = "http://aiops-engine:8000"
    # Optional observability backends; empty = feature disabled (proxy returns a clear error).
    prometheus_url: str = ""
    loki_url: str = ""

    cors_origins: list[str] = []
    redis_channel: str = "netguard:predictions"
    redis_buffer_key: str = "netguard:predictions:recent"
    buffer_read_limit: int = 500


settings = Settings()
