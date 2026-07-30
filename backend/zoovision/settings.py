from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = Field(default="development", alias="ZOOVISION_ENV")
    fixture_mode: bool = Field(default=True, alias="ZOOVISION_FIXTURE_MODE")
    timezone_name: str = Field(default="America/Los_Angeles", alias="ZOOVISION_TIMEZONE")
    storage_root: Path = Field(default=Path("./data"), alias="ZOOVISION_STORAGE_ROOT")
    raw_retention_days: int = Field(default=7, alias="ZOOVISION_RAW_RETENTION_DAYS")
    analysis_retention_days: int = Field(default=30, alias="ZOOVISION_ANALYSIS_RETENTION_DAYS")
    clip_retention_days: int = Field(default=90, alias="ZOOVISION_CLIP_RETENTION_DAYS")
    alert_ack_minutes: int = Field(default=20, alias="ZOOVISION_ALERT_ACK_MINUTES")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_merge_model: str = Field(default="gpt-5.6-luna", alias="OPENAI_MERGE_MODEL")
    openai_report_model: str = Field(default="gpt-5.6-terra", alias="OPENAI_REPORT_MODEL")
    twelvelabs_api_key: str | None = Field(default=None, alias="TWELVELABS_API_KEY")
    neo4j_uri: str | None = Field(default=None, alias="NEO4J_URI")
    neo4j_username: str | None = Field(default=None, alias="NEO4J_USERNAME")
    neo4j_password: str | None = Field(default=None, alias="NEO4J_PASSWORD")
    slack_webhook_url: str | None = Field(default=None, alias="SLACK_WEBHOOK_URL")

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    @property
    def database_path(self) -> Path:
        return self.storage_root / "zoovision.db"


def get_settings() -> Settings:
    return Settings()
