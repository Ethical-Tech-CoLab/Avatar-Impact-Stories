#!/usr/bin/env python3
"""Generate short looping GIF tile animations from story videos.

Only videos without a matching GIF are selected by default. Existing posters
are never overwritten unless --force is supplied.

Usage:
    python tools/generate_posters.py --check
    python tools/generate_posters.py --apply
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

WIDTH = 203
HEIGHT = 360
FPS = 25
DURATION = 3.0


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
    mode.add_argument("--apply", action="store_true", help="write the .gif files")
    ap.add_argument("--force", action="store_true", help="replace existing GIF posters")
    ap.add_argument("--duration", type=float, default=DURATION,
                    help="loop duration in seconds (default %(default)s)")
    ap.add_argument("--fps", type=int, default=FPS,
                    help="frames per second (default %(default)s)")
    args = ap.parse_args()

    which("ffmpeg")
    if args.duration <= 0:
        ap.error("--duration must be greater than zero")
    if args.fps <= 0:
        ap.error("--fps must be greater than zero")

    videos = sorted(MEDIA.glob("*.mp4"))
    selected = [v for v in videos if args.force or not v.with_suffix(".gif").exists()]
    if not selected:
        print("Every MP4 already has a matching GIF poster.")
        return 0

    print(f"{len(selected)} GIF poster(s) to generate at "
          f"{WIDTH}x{HEIGHT}, {args.fps} fps, {args.duration:g} seconds")
    for video in selected:
        print(f"  {video.name} -> {video.with_suffix('.gif').name}")

    if args.check:
        print("Run with --apply to generate.")
        return 0

    failures = []
    total = 0
    for n, video in enumerate(selected, 1):
        out = video.with_suffix(".gif")
        tmp = video.with_suffix(".generating.gif")
        t0 = time.time()
        scale_crop = (
            f"fps={args.fps},"
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={WIDTH}:{HEIGHT}"
        )
        filters = (
            f"{scale_crop},split[frames][palette_source];"
            "[palette_source]palettegen=stats_mode=diff[palette];"
            "[frames][palette]paletteuse=dither=sierra2_4a:diff_mode=rectangle"
        )
        r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(video),
             "-t", str(args.duration), "-filter_complex", filters,
             "-loop", "0", str(tmp)],
            capture_output=True, text=True, encoding="utf-8", errors="replace")

        if r.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
            failures.append(video.name)
            tmp.unlink(missing_ok=True)
            print(f"[{n}/{len(selected)}] FAILED {video.name}: {r.stderr.strip()[:160]}")
            continue

        tmp.replace(out)
        total += out.stat().st_size
        print(f"[{n}/{len(selected)}] {out.name[:52]:<54} "
              f"{human(out.stat().st_size):>9}  ({time.time() - t0:.0f}s)")

    if failures:
        print(f"\n{len(failures)} failed: {', '.join(failures)}")
        return 1
    print(f"\nGenerated {len(selected)} GIF poster(s), {human(total)} total.")
    print("Next: python tools/compress_posters.py --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
