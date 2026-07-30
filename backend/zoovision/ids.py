from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import datetime

from .domain import Behavior


def stable_id(prefix: str, *parts: object) -> str:
    payload = json.dumps(parts, separators=(",", ":"), sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def chunk_id(
    facility_id: str,
    enclosure_id: str,
    camera_id: str,
    chunk_start: datetime,
    source_name: str,
) -> str:
    return stable_id(
        "chk",
        facility_id,
        enclosure_id,
        camera_id,
        chunk_start.isoformat(),
        source_name,
    )


def observation_id(
    source_chunk_id: str,
    behavior: Behavior,
    *,
    provider_item_id: str | None,
    ordinal: int,
) -> str:
    stable_item = provider_item_id if provider_item_id is not None else f"ordinal:{ordinal}"
    return stable_id("obs", source_chunk_id, stable_item, behavior.value)


def event_id(
    animal_id: str,
    behavior: Behavior,
    source_observation_ids: Iterable[str],
    rule_version: str,
) -> str:
    return stable_id(
        "evt",
        animal_id,
        behavior.value,
        sorted(source_observation_ids),
        rule_version,
    )
