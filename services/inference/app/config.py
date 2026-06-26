"""Inference service configuration — all values come from the environment.

No secret or environment-specific value is hardcoded; every field below has a
safe, non-secret default that can be overridden via an ``INFERENCE_`` env var.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # protected_namespaces=() silences pydantic's warning about the ``model_`` prefix.
    model_config = SettingsConfigDict(
        env_prefix="INFERENCE_",
        env_file=".env",
        extra="ignore",
        protected_namespaces=(),
    )

    # Directory holding model.pkl, encoders.pkl and the *.json metadata files.
    model_dir: str = "/models"
    # Allowed CORS origins. Empty list = same-origin only (the service sits behind
    # the backend-api gateway, so cross-origin is normally unnecessary).
    cors_origins: list[str] = []
    log_level: str = "INFO"


settings = Settings()
