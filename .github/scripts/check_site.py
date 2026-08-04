#!/usr/bin/env python3
"""Verify the assembled _site before it is published.

Catches the failure mode that is invisible until someone taps a tile: a story
listed in the manifest whose media never made it into the artifact.
"""
import json
import os
import sys
import urllib.parse

SITE = "_site"


def main() -> int:
    with open(os.path.join(SITE, "stories.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)

    stories = manifest.get("stories", [])
    if not stories:
        print("::error::The manifest contains no stories.")
        return 1

    base = manifest.get("mediaBase", "")
    missing = []
    checked = 0
    for story in stories:
        for key in ("poster", "video"):
            ref = story.get(key, "")
            if not ref:
                missing.append(f"{story.get('title', '?')}: empty {key}")
                continue
            if ref.startswith(("http://", "https://")) or base:
                continue  # hosted off-site; not ours to verify here
            path = os.path.join(SITE, urllib.parse.unquote(ref))
            checked += 1
            if not os.path.isfile(path):
                missing.append(ref)

    if missing:
        print("::error::The manifest references files that were not published:")
        for ref in missing:
            print(f"  {ref}")
        return 1

    where = "off-site" if base else f"{checked} local files"
    print(f"All {len(stories)} stories resolved ({where}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
