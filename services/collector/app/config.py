"""Collector configuration — all values from the environment (``COLLECTOR_`` prefix)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COLLECTOR_",
        env_file=".env",
        extra="ignore",
        protected_namespaces=(),
    )

    # Where to score flows and where to publish results.
    inference_url: str = "http://inference:8000"
    redis_url: str = "redis://redis:6379/0"

    # Generation loop cadence and how many real KDDTest+ flows to keep for replay.
    interval_seconds: float = 2.0
    real_traffic_sample: int = 4000
    kdd_test_url: str = (
        "https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTest+.txt"
    )

    # Redis keys for the live prediction stream + bounded history buffer.
    redis_channel: str = "netguard:predictions"
    redis_buffer_key: str = "netguard:predictions:recent"
    buffer_max: int = 10000


settings = Settings()
