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
    openai_enrichment_enabled: bool = Field(
        default=False,
        alias="ZOOVISION_OPENAI_ENRICHMENT_ENABLED",
    )
    openai_merge_model: str = Field(default="gpt-5.6-luna", alias="OPENAI_MERGE_MODEL")
    openai_report_model: str = Field(default="gpt-5.6-terra", alias="OPENAI_REPORT_MODEL")
    twelvelabs_api_key: str | None = Field(default=None, alias="TWELVELABS_API_KEY")
    twelvelabs_model: str = Field(default="pegasus1.5", alias="TWELVELABS_MODEL")
    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    aws_session_token: str | None = Field(default=None, alias="AWS_SESSION_TOKEN")
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    aws_account_id: str | None = Field(default=None, alias="AWS_ACCOUNT_ID")
    aws_bedrock_profile: str | None = Field(default=None, alias="AWS_BEDROCK_PROFILE")
    aws_bedrock_access_key_id: str | None = Field(
        default=None,
        alias="AWS_BEDROCK_ACCESS_KEY_ID",
    )
    aws_bedrock_secret_access_key: str | None = Field(
        default=None,
        alias="AWS_BEDROCK_SECRET_ACCESS_KEY",
    )
    aws_bedrock_session_token: str | None = Field(
        default=None,
        alias="AWS_BEDROCK_SESSION_TOKEN",
    )
    aws_storage_enabled: bool = Field(default=False, alias="ZOOVISION_AWS_STORAGE_ENABLED")
    s3_raw_bucket: str | None = Field(default=None, alias="ZOOVISION_S3_RAW_BUCKET")
    s3_analysis_bucket: str | None = Field(
        default=None,
        alias="ZOOVISION_S3_ANALYSIS_BUCKET",
    )
    s3_clips_bucket: str | None = Field(default=None, alias="ZOOVISION_S3_CLIPS_BUCKET")
    bedrock_marengo_model: str = Field(
        default="twelvelabs.marengo-embed-3-0-v1:0",
        alias="ZOOVISION_BEDROCK_MARENGO_MODEL",
    )
    neo4j_uri: str | None = Field(default=None, alias="NEO4J_URI")
    neo4j_username: str | None = Field(default=None, alias="NEO4J_USERNAME")
    neo4j_password: str | None = Field(default=None, alias="NEO4J_PASSWORD")
    neo4j_read_username: str | None = Field(default=None, alias="NEO4J_READ_USERNAME")
    neo4j_read_password: str | None = Field(default=None, alias="NEO4J_READ_PASSWORD")
    slack_webhook_url: str | None = Field(default=None, alias="SLACK_WEBHOOK_URL")
    alert_delivery_enabled: bool = Field(
        default=False,
        alias="ZOOVISION_ALERT_DELIVERY_ENABLED",
    )

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    @property
    def database_path(self) -> Path:
        return self.storage_root / "zoovision.db"

    @property
    def aws_storage_configured(self) -> bool:
        return all(
            (
                self.s3_raw_bucket,
                self.s3_analysis_bucket,
                self.s3_clips_bucket,
            )
        )

    @property
    def aws_session_kwargs(self) -> dict[str, str]:
        credentials = {}
        if self.aws_access_key_id and self.aws_secret_access_key:
            credentials = {
                "aws_access_key_id": self.aws_access_key_id,
                "aws_secret_access_key": self.aws_secret_access_key,
            }
            if self.aws_session_token:
                credentials["aws_session_token"] = self.aws_session_token
        return {"region_name": self.aws_region, **credentials}

    @property
    def bedrock_session_kwargs(self) -> dict[str, str]:
        if self.aws_bedrock_access_key_id and self.aws_bedrock_secret_access_key:
            credentials = {
                "aws_access_key_id": self.aws_bedrock_access_key_id,
                "aws_secret_access_key": self.aws_bedrock_secret_access_key,
            }
            if self.aws_bedrock_session_token:
                credentials["aws_session_token"] = self.aws_bedrock_session_token
            return {"region_name": self.aws_region, **credentials}
        if self.aws_bedrock_profile:
            return {
                "profile_name": self.aws_bedrock_profile,
                "region_name": self.aws_region,
            }
        return self.aws_session_kwargs


def get_settings() -> Settings:
    return Settings()
