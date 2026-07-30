from datetime import UTC, datetime, timedelta
from os import utime

from zoovision.retention import RetentionPolicy, enforce_retention


def test_retention_dry_run_and_enforcement(tmp_path):
    directory = tmp_path / "raw"
    directory.mkdir()
    old = directory / "old.mp4"
    fresh = directory / "fresh.mp4"
    old.write_bytes(b"old")
    fresh.write_bytes(b"fresh")
    now = datetime(2026, 7, 30, tzinfo=UTC)
    old_time = (now - timedelta(days=8)).timestamp()
    fresh_time = (now - timedelta(days=2)).timestamp()
    utime(old, (old_time, old_time))
    utime(fresh, (fresh_time, fresh_time))
    policy = RetentionPolicy(directory=directory, days=7)

    assert enforce_retention([policy], now=now, dry_run=True) == [old]
    assert old.exists()
    assert enforce_retention([policy], now=now, dry_run=False) == [old]
    assert not old.exists()
    assert fresh.exists()
