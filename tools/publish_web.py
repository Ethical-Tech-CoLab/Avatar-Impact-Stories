#!/usr/bin/env python3
"""Publish the story videos as GitHub release assets and build the web manifest.

GitHub Pages cannot serve Git LFS files, and the video set is far too large for
a Pages site anyway. So the published build is split:

  * Pages serves the page, the background, and the small GIF posters (~80 MB).
  * A GitHub release hosts the MP4s (~840 MB) and streams them on demand.

This script uploads the videos under clean, web-safe names, reads the real asset
URLs back from the API, and writes ``stories.web.json`` for the Pages build.

Usage:
    python tools/publish_web.py --check      # report what would happen
    python tools/publish_web.py --upload     # upload missing assets, write manifest
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
MEDIA_DIR = ROOT / "final_gifs"
MANIFEST = ROOT / "stories.json"
WEB_MANIFEST = ROOT / "stories.web.json"

DEFAULT_REPO = "Ethical-Tech-CoLab/Avatar-Impact-Stories"
DEFAULT_TAG = "media-v1"

# Some exports have non-ASCII characters in their names; the default Windows
# console encoding cannot print them.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def slugify(value: str) -> str:
    """Web-safe asset name. GitHub rewrites spaces and punctuation in asset
    filenames, so we normalise up front rather than guess what it will do."""
    value = value.replace("_s ", "s ").replace("&", " and ")
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return re.sub(r"-{2,}", "-", value) or "story"


def gh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if check and result.returncode != 0:
        raise SystemExit(f"gh {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result


def load_stories() -> list[dict]:
    if not MANIFEST.is_file():
        raise SystemExit("stories.json not found. Run: python tools/serve.py --manifest-only")
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    stories = data.get("stories", [])
    if not stories:
        raise SystemExit("stories.json has no stories.")
    return stories


def unique_slugs(stories: list[dict]) -> dict[str, str]:
    """Map story id -> asset stem, guaranteed collision-free."""
    seen: dict[str, int] = {}
    slugs: dict[str, str] = {}
    for story in stories:
        base = slugify(story["id"])
        if base in seen:
            seen[base] += 1
            base = f"{base}-{seen[base]}"
        else:
            seen[base] = 1
        slugs[story["id"]] = base
    return slugs


def ensure_release(repo: str, tag: str) -> None:
    if gh("release", "view", tag, "--repo", repo, check=False).returncode == 0:
        print(f"  Release '{tag}' already exists.")
        return
    print(f"  Creating release '{tag}'...")
    gh(
        "release", "create", tag,
        "--repo", repo,
        "--title", "Story media",
        "--notes",
            "Video assets for the Many Voices kiosk, hosted here because GitHub Pages "
            "cannot serve Git LFS files. Referenced by stories.json in the published site.",
    )


def existing_assets(repo: str, tag: str) -> dict[str, str]:
    result = gh(
        "release", "view", tag, "--repo", repo,
        "--json", "assets", "--jq", ".assets[] | .name",
        check=False,
    )
    if result.returncode != 0:
        return {}
    return {name: name for name in result.stdout.split() if name}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--tag", default=DEFAULT_TAG)
    parser.add_argument("--upload", action="store_true", help="actually upload the videos")
    parser.add_argument("--check", action="store_true", help="report only, change nothing")
    args = parser.parse_args()

    stories = load_stories()
    slugs = unique_slugs(stories)

    total = 0
    plan = []
    for story in stories:
        source = ROOT / unquote(story["video"])
        if not source.is_file():
            raise SystemExit(f"Missing video file: {source}")
        size = source.stat().st_size
        total += size
        plan.append((story, source, slugs[story["id"]] + source.suffix, size))

    print(f"Repo   {args.repo}")
    print(f"Tag    {args.tag}")
    print(f"Videos {len(plan)}  ({total / 1_000_000:.0f} MB)\n")

    if args.check:
        for story, source, asset, size in plan:
            print(f"  {size / 1_000_000:7.0f} MB  {source.name}  ->  {asset}")
        posters = sum((ROOT / unquote(s["poster"])).stat().st_size for s in stories)
        print(f"\n  Pages artifact would be about {posters / 1_000_000:.0f} MB of posters "
              f"plus the page itself - comfortably under the 1 GB Pages limit.")
        return 0

    if not args.upload:
        print("Nothing to do. Pass --check to preview or --upload to publish.")
        return 0

    ensure_release(args.repo, args.tag)
    already = existing_assets(args.repo, args.tag)

    with tempfile.TemporaryDirectory() as staging_dir:
        staging = Path(staging_dir)
        for story, source, asset, size in plan:
            if asset in already:
                print(f"  = {asset} (already uploaded)")
                continue
            # Copy to the web-safe name first: the asset name comes from the
            # file's basename, so this is the only way to control it.
            staged = staging / asset
            print(f"  + {asset}  ({size / 1_000_000:.0f} MB)")
            shutil.copy2(source, staged)
            gh("release", "upload", args.tag, str(staged), "--repo", args.repo, "--clobber")
            staged.unlink()

    # Read the real URLs back rather than assuming the format.
    result = gh(
        "release", "view", args.tag, "--repo", args.repo,
        "--json", "assets", "--jq", ".assets[] | .name + \"\\t\" + .url",
    )
    urls = {}
    for line in result.stdout.splitlines():
        if "\t" in line:
            name, url = line.split("\t", 1)
            urls[name.strip()] = url.strip()

    base = json.loads(MANIFEST.read_text(encoding="utf-8"))
    web_stories = []
    for story, source, asset, size in plan:
        url = urls.get(asset)
        if not url:
            raise SystemExit(f"Asset {asset} is missing from the release after upload.")
        web_stories.append({
            "id": story["id"],
            "title": story["title"],
            "poster": story["poster"],   # relative: served by Pages
            "video": url,                # absolute: served by the release
        })

    WEB_MANIFEST.write_text(
        json.dumps(
            {
                "mediaBase": "",
                "grid": base.get("grid", {}),
                "background": base.get("background", {}),
                "stories": web_stories,
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {WEB_MANIFEST.name} with {len(web_stories)} stories.")
    print("Commit it, then let the Pages workflow deploy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
