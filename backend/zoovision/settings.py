from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator
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
    yolo_enabled: bool = Field(default=True, alias="ZOOVISION_YOLO_ENABLED")
    yolo_model: str = Field(default="yolo11m.pt", alias="ZOOVISION_YOLO_MODEL")
    yolo_device: str = Field(default="auto", alias="ZOOVISION_YOLO_DEVICE")
    yolo_sample_fps: float = Field(
        default=5.0,
        gt=0,
        le=30,
        alias="ZOOVISION_YOLO_SAMPLE_FPS",
    )
    yolo_confidence: float = Field(
        default=0.15,
        ge=0.01,
        le=1,
        alias="ZOOVISION_YOLO_CONFIDENCE",
    )
    yolo_image_size: int = Field(
        default=640,
        ge=320,
        le=1280,
        multiple_of=32,
        alias="ZOOVISION_YOLO_IMAGE_SIZE",
    )
    yolo_batch_size: int = Field(
        default=8,
        ge=1,
        le=64,
        alias="ZOOVISION_YOLO_BATCH_SIZE",
    )
    detection_frame_max_edge: int = Field(
        default=960,
        ge=320,
        le=2160,
        alias="ZOOVISION_DETECTION_FRAME_MAX_EDGE",
    )
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
    bedrock_embedding_enabled: bool = Field(
        default=False,
        alias="ZOOVISION_BEDROCK_EMBEDDING_ENABLED",
    )
    eventbridge_scheduler_enabled: bool = Field(
        default=False,
        alias="ZOOVISION_EVENTBRIDGE_SCHEDULER_ENABLED",
    )
    eventbridge_scheduler_target_arn: str | None = Field(
        default=None,
        alias="ZOOVISION_EVENTBRIDGE_SCHEDULER_TARGET_ARN",
    )
    eventbridge_scheduler_role_arn: str | None = Field(
        default=None,
        alias="ZOOVISION_EVENTBRIDGE_SCHEDULER_ROLE_ARN",
    )
    eventbridge_scheduler_group: str = Field(
        default="default",
        alias="ZOOVISION_EVENTBRIDGE_SCHEDULER_GROUP",
    )
    agentcore_runtime_arn: str | None = Field(
        default=None,
        alias="ZOOVISION_AGENTCORE_RUNTIME_ARN",
    )
    neo4j_uri: str | None = Field(default=None, alias="NEO4J_URI")
    neo4j_username: str | None = Field(default=None, alias="NEO4J_USERNAME")
    neo4j_password: str | None = Field(default=None, alias="NEO4J_PASSWORD")
    neo4j_read_username: str | None = Field(default=None, alias="NEO4J_READ_USERNAME")
    neo4j_read_password: str | None = Field(default=None, alias="NEO4J_READ_PASSWORD")
    proxy_shared_secret: str | None = Field(
        default=None,
        min_length=32,
        alias="ZOOVISION_PROXY_SHARED_SECRET",
    )
    operator_identity_required: bool = Field(
        default=False,
        alias="ZOOVISION_OPERATOR_IDENTITY_REQUIRED",
    )
    slack_webhook_url: str | None = Field(default=None, alias="SLACK_WEBHOOK_URL")
    alert_delivery_enabled: bool = Field(
        default=False,
        alias="ZOOVISION_ALERT_DELIVERY_ENABLED",
    )

    @model_validator(mode="after")
    def validate_production_integrations(self) -> Settings:
        if self.environment.lower() != "production":
            return self
        if self.fixture_mode:
            raise ValueError("production cannot run with fixture mode enabled")

        missing: list[str] = []
        if not self.twelvelabs_api_key:
            missing.append("TWELVELABS_API_KEY")
        if not self.yolo_enabled:
            missing.append("ZOOVISION_YOLO_ENABLED")
        if not all((self.neo4j_uri, self.neo4j_username, self.neo4j_password)):
            missing.append("NEO4J_URI/NEO4J_USERNAME/NEO4J_PASSWORD")
        if not self.aws_storage_enabled or not self.aws_storage_configured:
            missing.append("ZOOVISION_AWS_STORAGE_ENABLED/S3 bucket configuration")
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if not self.openai_enrichment_enabled:
            missing.append("ZOOVISION_OPENAI_ENRICHMENT_ENABLED")
        if not self.bedrock_embedding_enabled:
            missing.append("ZOOVISION_BEDROCK_EMBEDDING_ENABLED")
        if not self.proxy_shared_secret:
            missing.append("ZOOVISION_PROXY_SHARED_SECRET")
        if not self.operator_identity_required:
            missing.append("ZOOVISION_OPERATOR_IDENTITY_REQUIRED")
        if self.alert_delivery_enabled and not self.eventbridge_scheduler_configured:
            missing.append("ZOOVISION_EVENTBRIDGE_SCHEDULER_ENABLED/target ARN/role ARN")
        if missing:
            raise ValueError("production integrations are incomplete: " + ", ".join(missing))
        return self

    @property
    def production_mode(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    @property
    def database_path(self) -> Path:
        return self.storage_root / "zoovision.db"

    @property
    def detector_config(self):
        from .detection import DetectorConfig

        return DetectorConfig(
            sample_fps=self.yolo_sample_fps,
            yolo_enabled=self.yolo_enabled,
            yolo_model=self.yolo_model,
            yolo_device=self.yolo_device,
            yolo_confidence=self.yolo_confidence,
            yolo_image_size=self.yolo_image_size,
            yolo_batch_size=self.yolo_batch_size,
            frame_max_edge=self.detection_frame_max_edge,
        )

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
    def eventbridge_scheduler_configured(self) -> bool:
        return bool(
            self.eventbridge_scheduler_enabled
            and self.eventbridge_scheduler_target_arn
            and self.eventbridge_scheduler_role_arn
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
