#!/usr/bin/env python3
"""Convert the tile animations from GIF to animated WebP.

The idle wall is 22 animated GIFs. GIF is a 1987 format with no interframe
compression worth the name, and it costs roughly 4.5 MB per tile — about 81 MB
before a single story has been tapped. On anything short of a wired connection
the wall itself saturates the link, so the tiles trickle in one at a time and
the first story someone taps has no bandwidth left to stream with.

Animated WebP is the same idea in a modern format: same `<img>` element, same
looping behaviour, no video decoders and no extra memory pressure — and around
a tenth of the bytes. The GIFs stay in place as a fallback, wired up through a
`<picture>` element, so a browser that cannot do WebP still gets a wall.

Usage:
    python tools/compress_posters.py --check     # report only
    python tools/compress_posters.py --apply     # write the .webp files
    python tools/compress_posters.py --apply "New Story.gif"
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "final_gifs"

# A tile is at most 300 px tall on screen, so the source 203x360 is already
# about right; the win here is the format, not the dimensions. 12 fps is
# plenty for a background loop and halves the frame count.
FPS = 12
QUALITY = 70


def which(name: str) -> str:
    path = shutil.which(name)
    if not path:
        sys.exit(f"{name} not found on PATH. Install ffmpeg: https://ffmpeg.org/download.html")
    return path


def human(n: float) -> str:
    return f"{n / 1e6:,.1f} MB"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report only")
    mode.add_argument("--apply", action="store_true", help="write the .webp files")
    ap.add_argument("--fps", type=int, default=FPS)
    ap.add_argument("--quality", type=int, default=QUALITY)
    ap.add_argument("files", nargs="*", metavar="GIF",
                    help="specific files in final_gifs (default: every GIF)")
    args = ap.parse_args()

    which("ffmpeg")

    gifs = ([MEDIA / Path(name).name for name in args.files]
            if args.files else sorted(MEDIA.glob("*.gif")))
    invalid = [g.name for g in gifs if g.suffix.lower() != ".gif" or not g.is_file()]
    if invalid:
        sys.exit(f"GIF file(s) not found in {MEDIA}: {', '.join(invalid)}")
    if not gifs:
        sys.exit(f"No .gif files in {MEDIA}")

    before = sum(g.stat().st_size for g in gifs)
    print(f"{len(gifs)} tile animations, {human(before)} as GIF")

    if args.check:
        existing = [g for g in gifs if g.with_suffix(".webp").exists()]
        print(f"{len(existing)} already converted.")
        print(f"Expect roughly {human(before * 0.1)} as WebP.")
        print("Run with --apply to convert.")
        return 0

    after = 0
    failures = []
    for n, gif in enumerate(gifs, 1):
        out = gif.with_suffix(".webp")
        tmp = gif.with_suffix(".converting.webp")
        t0 = time.time()
        r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(gif),
             "-vcodec", "libwebp_anim", "-filter:v", f"fps={args.fps}",
             "-lossless", "0", "-q:v", str(args.quality),
             "-loop", "0", "-preset", "picture", str(tmp)],
            capture_output=True, text=True, encoding="utf-8", errors="replace")

        if r.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
            failures.append(gif.name)
            tmp.unlink(missing_ok=True)
            print(f"[{n}/{len(gifs)}] FAILED {gif.name}: {r.stderr.strip()[:160]}")
            continue

        # A WebP bigger than its GIF would be a pointless extra download.
        if tmp.stat().st_size >= gif.stat().st_size:
            tmp.unlink(missing_ok=True)
            print(f"[{n}/{len(gifs)}] skipped {gif.name} (WebP was not smaller)")
            after += gif.stat().st_size
            continue

        tmp.replace(out)
        after += out.stat().st_size
        pct = 100 * (1 - out.stat().st_size / gif.stat().st_size)
        print(f"[{n}/{len(gifs)}] {gif.name[:46]:<48} "
              f"{human(gif.stat().st_size):>9} -> {human(out.stat().st_size):>9}  "
              f"-{pct:.0f}%  ({time.time() - t0:.0f}s)")

    print(f"\nTotal {human(before)} -> {human(after)}  "
          f"(-{100 * (1 - after / max(before, 1)):.0f}%)")
    if failures:
        print(f"\n{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("\nNext: python tools/serve.py --manifest-only   # pick up the new posters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
