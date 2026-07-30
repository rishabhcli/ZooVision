from __future__ import annotations

import json
import math

import boto3
from zoovision.bedrock import BedrockMarengoEmbedder
from zoovision.settings import get_settings


def main() -> int:
    settings = get_settings()
    session = boto3.Session(**settings.bedrock_session_kwargs)
    identity = session.client("sts").get_caller_identity()
    vector = BedrockMarengoEmbedder(
        model_id=settings.bedrock_marengo_model,
        region=settings.aws_region,
        client=session.client("bedrock-runtime"),
    ).embed_text("African painted dog pacing near a water bowl at night")
    result = {
        "account": identity["Account"],
        "all_finite": all(math.isfinite(value) for value in vector.embedding),
        "dimension": vector.dimension,
        "model": settings.bedrock_marengo_model,
        "provider": "aws-bedrock",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_finite"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
