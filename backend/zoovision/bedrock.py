from __future__ import annotations

import json
from typing import Any

import boto3
from pydantic import BaseModel, ConfigDict, Field


class EmbeddingVector(BaseModel):
    model_config = ConfigDict(extra="allow")

    embedding: list[float] = Field(min_length=1)
    embedding_option: str | None = Field(default=None, alias="embeddingOption")
    embedding_scope: str | None = Field(default=None, alias="embeddingScope")
    start_seconds: float | None = Field(default=None, alias="startSec")
    end_seconds: float | None = Field(default=None, alias="endSec")

    @property
    def dimension(self) -> int:
        return len(self.embedding)


class AsyncEmbeddingJob(BaseModel):
    invocation_arn: str = Field(alias="invocationArn")


class BedrockMarengoEmbedder:
    def __init__(
        self,
        *,
        model_id: str = "twelvelabs.marengo-embed-3-0-v1:0",
        region: str = "us-east-1",
        client: Any | None = None,
    ):
        self.model_id = model_id
        self.region = region
        self.client = client or boto3.client("bedrock-runtime", region_name=region)

    def embed_text(self, text: str) -> EmbeddingVector:
        normalized = text.strip()
        if not normalized:
            raise ValueError("text must not be empty")
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(
                {
                    "inputType": "text",
                    "text": {"inputText": normalized},
                }
            ),
            accept="application/json",
            contentType="application/json",
        )
        payload = json.loads(response["body"].read())
        data = payload.get("data")
        if isinstance(data, list):
            if len(data) != 1:
                raise ValueError("text embedding response must contain one vector")
            data = data[0]
        return EmbeddingVector.model_validate(data)

    def start_video_embedding(
        self,
        *,
        input_s3_uri: str,
        output_s3_uri: str,
        bucket_owner: str,
        start_seconds: float = 0,
        end_seconds: float | None = None,
    ) -> AsyncEmbeddingJob:
        if not input_s3_uri.startswith("s3://") or not output_s3_uri.startswith("s3://"):
            raise ValueError("video input and output must use s3:// URIs")
        video: dict[str, Any] = {
            "mediaSource": {
                "s3Location": {
                    "uri": input_s3_uri,
                    "bucketOwner": bucket_owner,
                }
            },
            "startSec": start_seconds,
            "segmentation": {
                "method": "fixed",
                "fixed": {"durationSec": 5},
            },
            "embeddingOption": ["visual"],
            "embeddingType": ["separate_embedding"],
            "embeddingScope": ["clip", "asset"],
        }
        if end_seconds is not None:
            if end_seconds <= start_seconds:
                raise ValueError("end_seconds must be after start_seconds")
            video["endSec"] = end_seconds
        response = self.client.start_async_invoke(
            modelId=self.model_id,
            modelInput={
                "inputType": "video",
                "video": video,
            },
            outputDataConfig={
                "s3OutputDataConfig": {
                    "s3Uri": output_s3_uri,
                }
            },
        )
        return AsyncEmbeddingJob.model_validate(response)
