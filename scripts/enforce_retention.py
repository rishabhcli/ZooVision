from __future__ import annotations

import argparse

from zoovision.retention import RetentionPolicy, enforce_retention
from zoovision.settings import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply configured ZooVision media retention.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete expired files. Without this flag, only print the candidates.",
    )
    args = parser.parse_args()
    settings = get_settings()
    policies = [
        RetentionPolicy(
            settings.storage_root / "raw",
            settings.raw_retention_days,
        ),
        RetentionPolicy(
            settings.storage_root / "analysis",
            settings.analysis_retention_days,
        ),
        RetentionPolicy(
            settings.storage_root / "clips",
            settings.clip_retention_days,
        ),
    ]
    expired = enforce_retention(policies, dry_run=not args.apply)
    action = "deleted" if args.apply else "would delete"
    for path in expired:
        print(f"{action}: {path}")
    print(f"{action}: {len(expired)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
