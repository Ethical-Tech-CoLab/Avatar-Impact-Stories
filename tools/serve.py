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
import io
import json
import os
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parent.parent
MEDIA_DIR = ROOT / "final_gifs"
MANIFEST = ROOT / "stories.json"

DEFAULT_GRID = {"rows": 0, "cols": 0, "scatter": 0.16, "gapRatio": 0.16, "tilt": 4}

# Replacing the backdrop should not require editing code or JSON: drop a file
# named background.png (or .jpg/.jpeg/.webp) in the project root and it wins.
# The same applies to the ambient bed as background.mp3 (or .m4a/.ogg/.wav).
BACKGROUND_IMAGE_NAMES = ["background.png", "background.jpg", "background.jpeg",
                          "background.webp", "Crowd.png"]
BACKGROUND_AUDIO_NAMES = ["background.mp3", "background.m4a", "background.ogg",
                          "background.wav", "background testing.mp3"]

# Some exports have non-ASCII characters in their names; the default Windows
# console encoding cannot print them.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


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


def find_background() -> dict:
    """Pick the backdrop and ambient bed, preferring a drop-in replacement."""
    result = {}
    for name in BACKGROUND_IMAGE_NAMES:
        if (ROOT / name).is_file():
            result["image"] = url_for(ROOT / name)
            break
    for name in BACKGROUND_AUDIO_NAMES:
        if (ROOT / name).is_file():
            result["audio"] = url_for(ROOT / name)
            break
    return result


def discover() -> tuple[list[dict], list[str]]:
    """Return (paired stories, names of unpaired files)."""
    if not MEDIA_DIR.is_dir():
        raise SystemExit(f"Media folder not found: {MEDIA_DIR}")

    posters = {p.stem: p for p in MEDIA_DIR.glob("*.gif")}
    modern = {p.stem: p for p in MEDIA_DIR.glob("*.webp")}
    videos = {p.stem: p for p in MEDIA_DIR.glob("*.mp4")}

    stories = []
    for stem in sorted(posters.keys() & videos.keys(), key=str.lower):
        story = {
            "id": stem,
            "title": prettify(stem),
            # URL-encoded because the exports contain spaces, parentheses and
            # a '#', which a browser would otherwise read as a fragment.
            "poster": url_for(posters[stem]),
            "video": url_for(videos[stem]),
        }
        # An animated WebP is around a tenth the size of the GIF. The GIF stays
        # as the fallback for browsers that cannot decode it.
        if stem in modern:
            story["posterWebp"] = url_for(modern[stem])
        stories.append(story)

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

    # Start from defaults, keep any aesthetic tuning, then sanity-check the grid.
    grid = dict(DEFAULT_GRID)
    grid.update({k: v for k, v in existing.get("grid", {}).items() if k in grid})

    # A fixed grid with more seats than stories used to repeat stories to fill
    # the gap, which put the same face on the wall several times over. Fall back
    # to the automatic layout instead, which fits the grid to the story count.
    if grid["rows"] * grid["cols"] > len(stories):
        if grid["rows"] or grid["cols"]:
            print(f"  ! Grid {grid['rows']}x{grid['cols']} has more tiles than stories "
                  f"({len(stories)}); switching to automatic layout so no story repeats.")
        grid["rows"] = 0
        grid["cols"] = 0

    background = find_background()
    if not background.get("image"):
        print("  ! No background image found. Add background.png to the project root.")

    manifest = {
        "grid": grid,
        "background": background,
        "stories": stories,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"  {len(stories)} story pair(s) written to stories.json")
    print(f"  Background: {unquote(background.get('image', 'none'))}"
          f" + {unquote(background.get('audio', 'no audio'))}")
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
    """Static handler with HTTP range support.

    Python's SimpleHTTPRequestHandler ignores Range headers entirely, so a
    browser cannot seek and has to refetch a video from byte zero. For a
    100 MB story that shows up as stalling and stuttering. Serving 206
    responses fixes seeking and lets the player buffer incrementally.
    """

    def end_headers(self) -> None:
        self.send_header("Accept-Ranges", "bytes")
        if self.path.rstrip("/").endswith(("stories.json", "/")) or self.path == "/":
            # Stop the browser caching a stale manifest between runs.
            self.send_header("Cache-Control", "no-store")
        else:
            # Media is content-addressed by name and rarely changes; letting the
            # browser cache it is the difference between streaming a story once
            # and streaming it on every single tap.
            self.send_header("Cache-Control", "public, max-age=604800")
        super().end_headers()

    def send_head(self):
        rng = self.headers.get("Range")
        if not rng or not rng.startswith("bytes="):
            return super().send_head()

        path = self.translate_path(self.path)
        try:
            fh = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        try:
            size = os.fstat(fh.fileno()).st_size
            first, _, last = rng[6:].partition("-")
            try:
                start = int(first) if first else max(0, size - int(last))
                end = int(last) if (last and first) else size - 1
            except ValueError:
                fh.close()
                self.send_error(400, "Bad Range header")
                return None
            end = min(end, size - 1)
            if start > end or start >= size:
                fh.close()
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return None

            fh.seek(start)
            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            return _RangeReader(fh, end - start + 1)
        except Exception:
            fh.close()
            raise

    def log_message(self, fmt: str, *args) -> None:  # quieter console
        if "404" in (fmt % args):
            super().log_message(fmt, *args)


class _RangeReader(io.RawIOBase):
    """Reads at most ``remaining`` bytes so copyfile stops at the range end."""

    def __init__(self, fh, remaining: int):
        self._fh = fh
        self._remaining = remaining

    def read(self, size: int = -1) -> bytes:
        if self._remaining <= 0:
            return b""
        if size is None or size < 0 or size > self._remaining:
            size = self._remaining
        data = self._fh.read(size)
        self._remaining -= len(data)
        return data

    def readable(self) -> bool:
        return True

    def close(self) -> None:
        try:
            self._fh.close()
        finally:
            super().close()


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
