from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError


class AssetKind(StrEnum):
    RAW = "raw"
    ANALYSIS = "analysis"
    CLIP = "clips"


@dataclass(frozen=True)
class S3BucketSet:
    raw: str
    analysis: str
    clips: str

    def for_kind(self, kind: AssetKind) -> str:
        return {
            AssetKind.RAW: self.raw,
            AssetKind.ANALYSIS: self.analysis,
            AssetKind.CLIP: self.clips,
        }[kind]


@dataclass(frozen=True)
class BucketProvisionResult:
    bucket: str
    created: bool
    retention_days: int


class S3Archive:
    def __init__(
        self,
        buckets: S3BucketSet,
        *,
        region: str = "us-east-1",
        client: Any | None = None,
    ):
        self.buckets = buckets
        self.region = region
        self.client = client or boto3.client("s3", region_name=region)

    def verify_connectivity(self) -> None:
        for bucket in (
            self.buckets.raw,
            self.buckets.analysis,
            self.buckets.clips,
        ):
            self.client.head_bucket(Bucket=bucket)

    def upload_file(
        self,
        kind: AssetKind,
        source: Path,
        *,
        object_key: str,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        if not source.is_file():
            raise FileNotFoundError(source)
        key = _validated_object_key(object_key)
        bucket = self.buckets.for_kind(kind)
        extra_args: dict[str, Any] = {
            "ContentType": content_type,
            "ServerSideEncryption": "AES256",
        }
        if metadata:
            extra_args["Metadata"] = metadata
        self.client.upload_file(
            str(source),
            bucket,
            key,
            ExtraArgs=extra_args,
        )
        return f"s3://{bucket}/{key}"

    def upload_json(
        self,
        kind: AssetKind,
        payload: dict[str, Any],
        *,
        object_key: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        key = _validated_object_key(object_key)
        bucket = self.buckets.for_kind(kind)
        request: dict[str, Any] = {
            "Bucket": bucket,
            "Key": key,
            "Body": json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(),
            "ContentType": "application/json",
            "ServerSideEncryption": "AES256",
        }
        if metadata:
            request["Metadata"] = metadata
        self.client.put_object(**request)
        return f"s3://{bucket}/{key}"

    def presigned_get(self, kind: AssetKind, object_key: str, *, expires_seconds: int = 900) -> str:
        if not 60 <= expires_seconds <= 3600:
            raise ValueError("expires_seconds must be between 60 and 3600")
        bucket = self.buckets.for_kind(kind)
        key = _validated_object_key(object_key)
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )


def provision_buckets(
    archive: S3Archive,
    *,
    raw_retention_days: int,
    analysis_retention_days: int,
    clip_retention_days: int,
) -> list[BucketProvisionResult]:
    policies = (
        (archive.buckets.raw, raw_retention_days),
        (archive.buckets.analysis, analysis_retention_days),
        (archive.buckets.clips, clip_retention_days),
    )
    return [
        _provision_bucket(archive.client, bucket, archive.region, retention_days)
        for bucket, retention_days in policies
    ]


def _provision_bucket(
    client: Any,
    bucket: str,
    region: str,
    retention_days: int,
) -> BucketProvisionResult:
    if retention_days < 1:
        raise ValueError("retention_days must be positive")
    created = False
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as error:
        status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        code = error.response.get("Error", {}).get("Code")
        if status != 404 and code not in {"404", "NoSuchBucket", "NotFound"}:
            raise
        request: dict[str, Any] = {"Bucket": bucket}
        if region != "us-east-1":
            request["CreateBucketConfiguration"] = {"LocationConstraint": region}
        client.create_bucket(**request)
        created = True

    client.put_public_access_block(
        Bucket=bucket,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    client.put_bucket_encryption(
        Bucket=bucket,
        ServerSideEncryptionConfiguration={
            "Rules": [
                {
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "AES256",
                    },
                    "BucketKeyEnabled": False,
                }
            ]
        },
    )
    client.put_bucket_lifecycle_configuration(
        Bucket=bucket,
        LifecycleConfiguration={
            "Rules": [
                {
                    "ID": "zoovision-retention",
                    "Status": "Enabled",
                    "Filter": {"Prefix": ""},
                    "Expiration": {"Days": retention_days},
                    "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1},
                }
            ]
        },
    )
    return BucketProvisionResult(
        bucket=bucket,
        created=created,
        retention_days=retention_days,
    )


def _validated_object_key(value: str) -> str:
    key = value.strip("/")
    if not key or key.startswith(".") or any(part in {"", ".", ".."} for part in key.split("/")):
        raise ValueError("object_key must be a safe relative S3 key")
    return key
