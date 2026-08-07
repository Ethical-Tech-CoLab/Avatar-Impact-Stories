#!/usr/bin/env python3
"""Apply hand-written tile captions from tools/rename_titles.json.

Usage:
    python tools/apply_titles.py --dry-run
    python tools/apply_titles.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "stories.json"
RENAMES = ROOT / "tools" / "rename_titles.json"


def load(path: Path) -> dict:
    if not path.is_file():
        sys.exit(f"Not found: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="preview without writing")
    args = ap.parse_args()

    manifest = load(MANIFEST)
    renames = load(RENAMES)
    by_id = {story.get("id"): story for story in manifest.get("stories", [])}
    rows = renames.get("titles", [])
    if not rows:
        sys.exit("rename_titles.json has no 'titles' list.")

    changed = []
    unchanged = 0
    missing = []
    for row in rows:
        story_id = row.get("id")
        new_title = row.get("newTitle")
        if story_id not in by_id:
            missing.append(story_id)
            continue
        if new_title is None or new_title == "":
            unchanged += 1
            continue
        if not isinstance(new_title, str) or not new_title.strip():
            sys.exit(f"Blank or invalid newTitle for {story_id!r}")

        new_title = new_title.strip()
        old_title = by_id[story_id].get("title", "")
        if old_title == new_title:
            unchanged += 1
            continue
        changed.append((story_id, old_title, new_title))
        if not args.dry_run:
            by_id[story_id]["title"] = new_title

    for story_id in missing:
        print(f"  ! NO SUCH STORY: {story_id!r} - caption not applied")
    for story_id, old_title, new_title in changed:
        print(f"  {story_id}\n      {old_title!r} -> {new_title!r}")
    print(f"\n{len(changed)} changed, {unchanged} unchanged, {len(missing)} unmatched")

    if args.dry_run:
        print("dry run - nothing written")
    elif changed:
        with MANIFEST.open("w", encoding="utf-8", newline="\n") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print("wrote stories.json")
    else:
        print("nothing to write")

    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
