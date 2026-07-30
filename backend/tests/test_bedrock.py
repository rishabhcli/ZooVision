import json

import pytest
from zoovision.bedrock import BedrockMarengoEmbedder


class Body:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()


class FakeBedrock:
    def __init__(self):
        self.invoke_request = None
        self.async_request = None

    def invoke_model(self, **kwargs):
        self.invoke_request = kwargs
        return {"body": Body({"data": {"embedding": [0.1, 0.2, 0.3]}})}

    def start_async_invoke(self, **kwargs):
        self.async_request = kwargs
        return {"invocationArn": "arn:aws:bedrock:us-east-1:123:async-invoke/job"}


def test_text_embedding_uses_nested_marengo_3_contract_and_discovers_dimension():
    client = FakeBedrock()
    result = BedrockMarengoEmbedder(client=client).embed_text(" painted dog pacing ")

    assert result.dimension == 3
    assert json.loads(client.invoke_request["body"]) == {
        "inputType": "text",
        "text": {"inputText": "painted dog pacing"},
    }


def test_video_embedding_uses_s3_and_async_fixed_segments():
    client = FakeBedrock()
    job = BedrockMarengoEmbedder(client=client).start_video_embedding(
        input_s3_uri="s3://raw/chunks/enc07.mp4",
        output_s3_uri="s3://analysis/embeddings/",
        bucket_owner="123456789012",
        start_seconds=10,
        end_seconds=20,
    )

    assert job.invocation_arn.endswith("/job")
    video = client.async_request["modelInput"]["video"]
    assert video["mediaSource"]["s3Location"]["bucketOwner"] == "123456789012"
    assert video["segmentation"]["fixed"]["durationSec"] == 5
    assert video["embeddingOption"] == ["visual"]


def test_video_embedding_rejects_invalid_ranges_and_non_s3_locations():
    embedder = BedrockMarengoEmbedder(client=FakeBedrock())

    with pytest.raises(ValueError):
        embedder.start_video_embedding(
            input_s3_uri="https://example.com/video.mp4",
            output_s3_uri="s3://analysis/embeddings/",
            bucket_owner="123456789012",
        )
    with pytest.raises(ValueError):
        embedder.start_video_embedding(
            input_s3_uri="s3://raw/video.mp4",
            output_s3_uri="s3://analysis/embeddings/",
            bucket_owner="123456789012",
            start_seconds=20,
            end_seconds=10,
        )
