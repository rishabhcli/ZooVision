from zoovision.settings import Settings


def test_aws_session_uses_explicit_local_credentials_when_configured():
    settings = Settings(
        AWS_ACCESS_KEY_ID="test-access",
        AWS_SECRET_ACCESS_KEY="test-secret",
        AWS_SESSION_TOKEN="test-session",
        AWS_REGION="us-west-2",
        _env_file=None,
    )

    assert settings.aws_session_kwargs == {
        "aws_access_key_id": "test-access",
        "aws_secret_access_key": "test-secret",
        "aws_session_token": "test-session",
        "region_name": "us-west-2",
    }


def test_aws_session_preserves_role_chain_when_keys_are_absent():
    settings = Settings(AWS_REGION="us-east-1", _env_file=None)

    assert settings.aws_session_kwargs == {"region_name": "us-east-1"}


def test_bedrock_can_use_a_separate_workshop_profile():
    settings = Settings(
        AWS_ACCESS_KEY_ID="storage-access",
        AWS_SECRET_ACCESS_KEY="storage-secret",
        AWS_BEDROCK_PROFILE="hackathon",
        AWS_REGION="us-east-1",
        _env_file=None,
    )

    assert settings.bedrock_session_kwargs == {
        "profile_name": "hackathon",
        "region_name": "us-east-1",
    }


def test_bedrock_explicit_credentials_take_precedence_over_profile():
    settings = Settings(
        AWS_BEDROCK_ACCESS_KEY_ID="bedrock-access",
        AWS_BEDROCK_SECRET_ACCESS_KEY="bedrock-secret",
        AWS_BEDROCK_SESSION_TOKEN="bedrock-session",
        AWS_BEDROCK_PROFILE="ignored-profile",
        AWS_REGION="us-east-1",
        _env_file=None,
    )

    assert settings.bedrock_session_kwargs == {
        "aws_access_key_id": "bedrock-access",
        "aws_secret_access_key": "bedrock-secret",
        "aws_session_token": "bedrock-session",
        "region_name": "us-east-1",
    }
