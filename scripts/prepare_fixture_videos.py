from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "fixtures" / "video_sources.json"
SOURCE_DIR = ROOT / "data" / "raw" / "sources"
FIXTURE_DIR = ROOT / "data" / "raw" / "fixtures"
USER_AGENT = "ZooVision fixture preparation/1.0 (local evaluation)"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download checksum-pinned, freely licensed camera footage."
    )
    parser.add_argument(
        "--source",
        action="append",
        dest="source_ids",
        help="Prepare only this source id. May be supplied more than once.",
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Verify original files without creating extended fixtures.",
    )
    parser.add_argument("--force", action="store_true", help="Replace existing fixture outputs.")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(source: dict[str, object], destination: Path) -> None:
    expected = str(source["sha256"])
    if destination.exists():
        if sha256(destination) == expected:
            print(f"verified {destination.relative_to(ROOT)}")
            return
        raise RuntimeError(f"checksum mismatch for existing file: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = Request(str(source["download_url"]), headers={"User-Agent": USER_AGENT})
    print(f"downloading {source['id']} from Wikimedia Commons")
    with urlopen(request, timeout=60) as response, partial.open("wb") as output:
        shutil.copyfileobj(response, output)
    if sha256(partial) != expected:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"downloaded checksum mismatch for {source['id']}")
    partial.replace(destination)


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def prepare(source: dict[str, object], original: Path, destination: Path, force: bool) -> None:
    if destination.exists() and not force:
        print(f"keeping existing {destination.relative_to(ROOT)}")
        return
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg and ffprobe are required to prepare fixtures")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="zoovision-fixture-") as temporary:
        normalized = Path(temporary) / "normalized.mp4"
        staged = Path(temporary) / destination.name
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(original),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-vf",
                "setpts=PTS-STARTPTS,scale=960:-2",
                "-af",
                "asetpts=PTS-STARTPTS",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "29",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "64k",
                "-movflags",
                "+faststart",
                str(normalized),
            ]
        )
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-stream_loop",
                "-1",
                "-i",
                str(normalized),
                "-t",
                str(source["fixture_duration_seconds"]),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(staged),
            ]
        )
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(staged),
                "-map",
                "0:v:0",
                "-f",
                "null",
                "-",
            ]
        )
        staged.replace(destination)
    print(f"prepared {destination.relative_to(ROOT)}")


def main() -> int:
    args = parse_args()
    manifest = json.loads(MANIFEST_PATH.read_text())
    sources = manifest["sources"]
    selected = set(args.source_ids or ())
    unknown = selected - {source["id"] for source in sources}
    if unknown:
        raise RuntimeError(f"unknown source ids: {', '.join(sorted(unknown))}")

    for source in sources:
        if selected and source["id"] not in selected:
            continue
        original = SOURCE_DIR / source["filename"]
        download(source, original)
        if not args.download_only:
            prepare(
                source,
                original,
                FIXTURE_DIR / source["fixture_filename"],
                args.force,
            )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
