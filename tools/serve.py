#!/usr/bin/env python3
"""Serve the Many Voices kiosk locally.

Scans ``final_gifs/`` for matching ``.gif`` / ``.mp4`` pairs, refreshes
``stories.json`` (keeping any titles you have edited by hand), then serves the
project on http://localhost:8000 and opens it in your browser.

Usage:
    python tools/serve.py [--port 8000] [--no-browser] [--manifest-only]
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parent.parent
MEDIA_DIR = ROOT / "final_gifs"
MANIFEST = ROOT / "stories.json"

DEFAULT_GRID = {"rows": 5, "cols": 6, "scatter": 0.16, "gapRatio": 0.16, "tilt": 4}
DEFAULT_BACKGROUND = {"image": "Crowd.png", "audio": "background%20testing.mp3"}


def url_for(path: Path) -> str:
    """Relative, URL-encoded path usable directly as a src attribute."""
    return quote(path.relative_to(ROOT).as_posix(), safe="/")


def prettify(stem: str) -> str:
    """Turn an export filename into something presentable."""
    title = stem.replace("_s ", "'s ").replace("_", " ")
    for suffix in (" copy", " final", " FINAL"):
        if title.endswith(suffix):
            title = title[: -len(suffix)]
    return " ".join(title.split())


def discover() -> tuple[list[dict], list[str]]:
    """Return (paired stories, names of unpaired files)."""
    if not MEDIA_DIR.is_dir():
        raise SystemExit(f"Media folder not found: {MEDIA_DIR}")

    posters = {p.stem: p for p in MEDIA_DIR.glob("*.gif")}
    videos = {p.stem: p for p in MEDIA_DIR.glob("*.mp4")}

    stories = []
    for stem in sorted(posters.keys() & videos.keys(), key=str.lower):
        stories.append(
            {
                "id": stem,
                "title": prettify(stem),
                # URL-encoded because the exports contain spaces, parentheses and
                # a '#', which a browser would otherwise read as a fragment.
                "poster": url_for(posters[stem]),
                "video": url_for(videos[stem]),
            }
        )

    unpaired = sorted(
        [f"{s}.gif (no matching .mp4)" for s in posters.keys() - videos.keys()]
        + [f"{s}.mp4 (no matching .gif)" for s in videos.keys() - posters.keys()]
    )
    return stories, unpaired


def is_pointer_file(path: Path) -> bool:
    """True if the file is still an unfetched Git LFS pointer."""
    try:
        with path.open("rb") as handle:
            return handle.read(7) == b"version"
    except OSError:
        return False


def build_manifest() -> dict:
    stories, unpaired = discover()

    existing: dict = {}
    if MANIFEST.is_file():
        try:
            existing = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as err:
            print(f"  ! Ignoring unreadable stories.json ({err})")

    # Preserve hand-edited titles across regeneration.
    previous_titles = {s.get("id"): s.get("title") for s in existing.get("stories", [])}
    for story in stories:
        kept = previous_titles.get(story["id"])
        if kept:
            story["title"] = kept

    manifest = {
        "grid": existing.get("grid", DEFAULT_GRID),
        "background": existing.get("background", DEFAULT_BACKGROUND),
        "stories": stories,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"  {len(stories)} story pair(s) written to stories.json")
    for name in unpaired:
        print(f"  ! Skipped {name}")

    pointers = [s["video"] for s in stories if is_pointer_file(ROOT / unquote(s["video"]))]
    if pointers:
        print(
            f"  ! {len(pointers)} media file(s) are still Git LFS pointers. "
            "Run 'git lfs pull' to download them."
        )

    return manifest


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        # Stop the browser caching a stale manifest between runs.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:  # quieter console
        if "404" in (fmt % args):
            super().log_message(fmt, *args)


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the Many Voices kiosk.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--manifest-only", action="store_true")
    args = parser.parse_args()

    print("Many Voices - Avatar Impact Stories\n")
    build_manifest()

    if args.manifest_only:
        return 0

    url = f"http://localhost:{args.port}/"
    handler = functools.partial(Handler, directory=str(ROOT))

    try:
        server = Server(("127.0.0.1", args.port), handler)
    except OSError as err:
        print(f"\nCould not bind port {args.port}: {err}")
        print("Something else is probably using it. Try: python tools/serve.py --port 8080")
        return 1

    print(f"\n  Serving {ROOT}")
    print(f"  Open {url}")
    print("  Press Ctrl+C to stop.\n")

    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
