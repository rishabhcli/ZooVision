from pathlib import Path

import pytest
from botocore.exceptions import ClientError
from zoovision.aws_storage import (
    AssetKind,
    S3Archive,
    S3BucketSet,
    provision_buckets,
)


class FakeS3:
    def __init__(self, existing: set[str] | None = None):
        self.existing = existing or set()
        self.calls: list[tuple[str, dict]] = []

    def head_bucket(self, **kwargs):
        self.calls.append(("head_bucket", kwargs))
        if kwargs["Bucket"] not in self.existing:
            raise ClientError(
                {
                    "Error": {"Code": "404", "Message": "missing"},
                    "ResponseMetadata": {"HTTPStatusCode": 404},
                },
                "HeadBucket",
            )

    def create_bucket(self, **kwargs):
        self.calls.append(("create_bucket", kwargs))
        self.existing.add(kwargs["Bucket"])

    def put_public_access_block(self, **kwargs):
        self.calls.append(("put_public_access_block", kwargs))

    def put_bucket_encryption(self, **kwargs):
        self.calls.append(("put_bucket_encryption", kwargs))

    def put_bucket_lifecycle_configuration(self, **kwargs):
        self.calls.append(("put_bucket_lifecycle_configuration", kwargs))

    def upload_file(self, *args, **kwargs):
        self.calls.append(("upload_file", {"args": args, **kwargs}))

    def generate_presigned_url(self, *args, **kwargs):
        self.calls.append(("generate_presigned_url", {"args": args, **kwargs}))
        return "https://example.invalid/signed"

    def put_object(self, **kwargs):
        self.calls.append(("put_object", kwargs))


@pytest.fixture
def buckets():
    return S3BucketSet(raw="raw-bucket", analysis="analysis-bucket", clips="clips-bucket")


def test_provision_creates_private_buckets_with_independent_retention(buckets):
    client = FakeS3()
    results = provision_buckets(
        S3Archive(buckets, client=client),
        raw_retention_days=7,
        analysis_retention_days=30,
        clip_retention_days=90,
    )

    assert [result.created for result in results] == [True, True, True]
    lifecycle_calls = [
        payload
        for operation, payload in client.calls
        if operation == "put_bucket_lifecycle_configuration"
    ]
    assert [
        call["LifecycleConfiguration"]["Rules"][0]["Expiration"]["Days"] for call in lifecycle_calls
    ] == [7, 30, 90]
    assert all(
        call["PublicAccessBlockConfiguration"]["RestrictPublicBuckets"]
        for operation, call in client.calls
        if operation == "put_public_access_block"
    )


def test_provision_is_idempotent_for_existing_buckets(buckets):
    client = FakeS3(existing={"raw-bucket", "analysis-bucket", "clips-bucket"})
    results = provision_buckets(
        S3Archive(buckets, client=client),
        raw_retention_days=7,
        analysis_retention_days=30,
        clip_retention_days=90,
    )

    assert not any(result.created for result in results)
    assert all(operation != "create_bucket" for operation, _ in client.calls)


def test_upload_preserves_kind_and_encryption(tmp_path: Path, buckets):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")
    client = FakeS3(existing={"raw-bucket", "analysis-bucket", "clips-bucket"})
    archive = S3Archive(buckets, client=client)

    uri = archive.upload_file(
        AssetKind.CLIP,
        source,
        object_key="event-123/evidence.mp4",
        content_type="video/mp4",
        metadata={"event-id": "event-123"},
    )

    assert uri == "s3://clips-bucket/event-123/evidence.mp4"
    upload = next(payload for operation, payload in client.calls if operation == "upload_file")
    assert upload["ExtraArgs"]["ServerSideEncryption"] == "AES256"


def test_object_keys_and_presigned_expiry_are_bounded(buckets):
    archive = S3Archive(buckets, client=FakeS3())

    with pytest.raises(ValueError):
        archive.presigned_get(AssetKind.CLIP, "../secret")
    with pytest.raises(ValueError):
        archive.presigned_get(AssetKind.CLIP, "clip.mp4", expires_seconds=7200)


def test_json_upload_is_encrypted_and_canonical(buckets):
    client = FakeS3(existing={"raw-bucket", "analysis-bucket", "clips-bucket"})
    archive = S3Archive(buckets, client=client)

    uri = archive.upload_json(
        AssetKind.ANALYSIS,
        {"observations": [], "coverage_complete": True},
        object_key="animal-1/chunk-1.json",
    )

    assert uri == "s3://analysis-bucket/animal-1/chunk-1.json"
    upload = next(payload for operation, payload in client.calls if operation == "put_object")
    assert upload["ServerSideEncryption"] == "AES256"
    assert upload["ContentType"] == "application/json"
    assert upload["Body"] == b'{"coverage_complete":true,"observations":[]}'
