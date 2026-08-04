#!/usr/bin/env python3
"""Verify the assembled _site before it is published.

Catches the failure mode that is invisible until someone taps a tile: a story
listed in the manifest whose media never made it into the artifact.
"""
import json
import os
import re
import sys
import urllib.parse

SITE = "_site"
PAGES = ("index.html", "about.html")


def check_pages() -> list:
    """Every page must ship, and their links to each other must resolve.

    The provenance page is reachable only by a link from the wall, so a
    missing file or a stale href is invisible until a visitor clicks it.
    """
    problems = []
    for page in PAGES:
        if not os.path.isfile(os.path.join(SITE, page)):
            problems.append(f"page missing from the artifact: {page}")

    for page in PAGES:
        path = os.path.join(SITE, page)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            html = fh.read()
        for href in re.findall(r'href="([^"#?]+)"', html):
            if href.startswith(("http://", "https://", "mailto:", "//", "data:")):
                continue
            target = os.path.join(SITE, urllib.parse.unquote(href))
            if not os.path.isfile(target):
                problems.append(f"{page} links to a missing file: {href}")
    return problems


def main() -> int:
    with open(os.path.join(SITE, "stories.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)

    stories = manifest.get("stories", [])
    if not stories:
        print("::error::The manifest contains no stories.")
        return 1

    base = manifest.get("mediaBase", "")
    missing = check_pages()
    checked = 0

    # The backdrop is easy to forget when swapping it, and a missing one leaves
    # the wall on a black screen rather than failing loudly.
    for key, label in (("image", "background image"), ("audio", "ambient audio")):
        ref = manifest.get("background", {}).get(key, "")
        if not ref or ref.startswith(("http://", "https://")):
            continue
        if not os.path.isfile(os.path.join(SITE, urllib.parse.unquote(ref))):
            missing.append(f"{label}: {ref}")

    for story in stories:
        for key in ("poster", "posterWebp", "video"):
            ref = story.get(key, "")
            if not ref:
                # Only the WebP tile is optional; it is a faster alternative to
                # the GIF, not a replacement for it.
                if key != "posterWebp":
                    missing.append(f"{story.get('title', '?')}: empty {key}")
                continue
            if ref.startswith(("http://", "https://")) or base:
                continue  # hosted off-site; not ours to verify here
            path = os.path.join(SITE, urllib.parse.unquote(ref))
            checked += 1
            if not os.path.isfile(path):
                missing.append(ref)

    if missing:
        print("::error::The published site is incomplete:")
        for ref in missing:
            print(f"  {ref}")
        return 1

    where = "off-site" if base else f"{checked} local files"
    print(f"All {len(stories)} stories resolved ({where}). Pages: {', '.join(PAGES)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
