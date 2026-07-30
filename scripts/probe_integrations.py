from __future__ import annotations

import json
from contextlib import suppress

from openai import OpenAI
from zoovision.graph import Neo4jGraphWriter
from zoovision.settings import get_settings


def main() -> int:
    settings = get_settings()
    result: dict[str, dict[str, object]] = {}

    if settings.openai_api_key:
        try:
            models = {
                model.id for model in OpenAI(api_key=settings.openai_api_key).models.list().data
            }
            required = {settings.openai_merge_model, settings.openai_report_model}
            result["openai"] = {
                "configured": True,
                "healthy": required.issubset(models),
                "models_visible": sorted(required & models),
            }
        except Exception as error:
            result["openai"] = {
                "configured": True,
                "healthy": False,
                "error_type": type(error).__name__,
            }
    else:
        result["openai"] = {"configured": False, "healthy": False}

    if settings.neo4j_uri and settings.neo4j_username and settings.neo4j_password:
        writer = Neo4jGraphWriter(
            settings.neo4j_uri,
            settings.neo4j_username,
            settings.neo4j_password,
        )
        try:
            writer.verify_connectivity()
            result["neo4j"] = {"configured": True, "healthy": True}
        except Exception as error:
            result["neo4j"] = {
                "configured": True,
                "healthy": False,
                "error_type": type(error).__name__,
            }
        finally:
            with suppress(Exception):
                writer.close()
    else:
        result["neo4j"] = {"configured": False, "healthy": False}

    result["twelvelabs"] = {
        "configured": bool(settings.twelvelabs_api_key),
        "healthy": None,
        "note": "not probed without a media analysis request",
    }
    result["slack"] = {
        "configured": bool(settings.slack_webhook_url),
        "healthy": None,
        "note": "not probed because webhook verification would send a message",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["openai"]["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
