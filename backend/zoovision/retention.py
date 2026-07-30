from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class RetentionPolicy:
    directory: Path
    days: int


def expired_files(
    policies: list[RetentionPolicy],
    *,
    now: datetime | None = None,
) -> list[Path]:
    reference = now or datetime.now(UTC)
    expired = []
    for policy in policies:
        if policy.days < 1 or not policy.directory.exists():
            continue
        cutoff = reference - timedelta(days=policy.days)
        for candidate in policy.directory.rglob("*"):
            if not candidate.is_file():
                continue
            modified = datetime.fromtimestamp(candidate.stat().st_mtime, tz=UTC)
            if modified < cutoff:
                expired.append(candidate)
    return sorted(expired)


def enforce_retention(
    policies: list[RetentionPolicy],
    *,
    now: datetime | None = None,
    dry_run: bool = True,
) -> list[Path]:
    expired = expired_files(policies, now=now)
    if not dry_run:
        for path in expired:
            path.unlink(missing_ok=True)
    return expired
