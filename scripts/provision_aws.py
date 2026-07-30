from __future__ import annotations

import json

import boto3
from zoovision.aws_storage import S3Archive, S3BucketSet, provision_buckets
from zoovision.settings import get_settings


def main() -> int:
    settings = get_settings()
    if not settings.aws_storage_configured:
        raise SystemExit(
            "Set ZOOVISION_S3_RAW_BUCKET, ZOOVISION_S3_ANALYSIS_BUCKET, "
            "and ZOOVISION_S3_CLIPS_BUCKET first."
        )
    session = boto3.Session(**settings.aws_session_kwargs)
    archive = S3Archive(
        S3BucketSet(
            raw=settings.s3_raw_bucket,
            analysis=settings.s3_analysis_bucket,
            clips=settings.s3_clips_bucket,
        ),
        region=settings.aws_region,
        client=session.client("s3"),
    )
    results = provision_buckets(
        archive,
        raw_retention_days=settings.raw_retention_days,
        analysis_retention_days=settings.analysis_retention_days,
        clip_retention_days=settings.clip_retention_days,
    )
    print(
        json.dumps(
            {
                "region": settings.aws_region,
                "buckets": [
                    {
                        "name": result.bucket,
                        "created": result.created,
                        "retention_days": result.retention_days,
                    }
                    for result in results
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
