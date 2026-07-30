# Evaluation video fixtures

`video_sources.json` records the exact source URL, creator, license, checksum, and
verified media duration for each freely licensed recording. Original and derived
media stay under ignored `data/raw/` paths and must not be committed.

Prepare every source and long-form fixture:

```bash
uv run python scripts/prepare_fixture_videos.py
```

Prepare one source, or only verify the original downloads:

```bash
uv run python scripts/prepare_fixture_videos.py --source condor-nest-camera
uv run python scripts/prepare_fixture_videos.py --download-only
```

The long MP4s are controlled evaluation media made by repeating the source after
normalizing its timestamps. They resemble continuous fixed-camera feeds, but
they are not continuous original recordings and are not annotated behavior
ground truth. Any synthetic observation scenario must be labeled separately.
