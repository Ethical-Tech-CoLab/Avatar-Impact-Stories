#!/usr/bin/env python3
"""Re-encode the story videos so they actually play over a real connection.

The source exports are wildly over-encoded for what they contain: single
talking-head avatars on static backgrounds, delivered at up to 11.4 Mbps. That
is near Blu-ray bitrate for the easiest content a codec will ever see.

Two things matter here, and only one of them is file size:

* **Peak bitrate.** A stream only plays smoothly if its bitrate comfortably
  fits the viewer's connection. Encoding on quality alone (CRF with no cap)
  left the tallest videos at 4.5 Mbps, which stalls every few seconds on
  ordinary venue wifi or mobile data and pushes audio out of sync. Every
  encode is now capped, so the worst case is roughly half a typical
  connection rather than all of it.
* **Resolution.** These play in a phone-shaped tile, and full screen on a
  kiosk. 720 on the short side is the standard bar for talking-head video and
  is indistinguishable at viewing distance; 1080 simply spends bytes that
  make the story stall.

Usage:
    python tools/compress_media.py --check     # report only, encodes nothing
    python tools/compress_media.py --apply     # re-encode in place
    python tools/compress_media.py --apply --keep-originals ../originals
    python tools/compress_media.py --apply "New Story.mp4"
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "final_gifs"

CRF = 22          # quality floor; the bitrate cap below is what bounds the peak
PRESET = "medium"
AUDIO_KBPS = "96k"

# Peak bitrate ceiling. Streaming needs headroom: a stream that exactly fills
# the connection has none, and rebuffers on the first hiccup. 1.8 Mbps plays
# comfortably on the ~4 Mbps that a busy venue or a phone realistically gets.
MAXRATE_K = 1800

# Long and short side limits. 1080x1920 becomes 720x1280; 1920x1080 becomes
# 1280x720; anything already smaller is left alone.
MAX_LONG = 1280
MAX_SHORT = 720

# Talking-head footage gains nothing from 60 fps, and it costs bitrate that
# would otherwise go to keeping the picture sharp.
MAX_FPS = 30


def target_size(w: int, h: int) -> tuple[int, int]:
    """Scale factor that respects both limits, rounded to even dimensions."""
    scale = min(1.0, MAX_LONG / max(w, h), MAX_SHORT / min(w, h))
    if scale >= 1.0:
        return w, h
    # x264 needs even dimensions for yuv420p.
    return max(2, int(round(w * scale / 2)) * 2), max(2, int(round(h * scale / 2)) * 2)


def which(name: str) -> str:
    path = shutil.which(name)
    if not path:
        sys.exit(f"{name} not found on PATH. Install ffmpeg: https://ffmpeg.org/download.html")
    return path


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def probe(path: Path) -> dict | None:
    r = run(["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(path)])
    if r.returncode != 0:
        return None
    try:
        d = json.loads(r.stdout)
        v = next(s for s in d["streams"] if s["codec_type"] == "video")
    except (ValueError, StopIteration):
        return None
    num, _, den = v.get("avg_frame_rate", "0/1").partition("/")
    fps = float(num) / float(den) if den and float(den) else 0.0
    return {
        "size": int(d["format"]["size"]),
        "dur": float(d["format"].get("duration", 0) or 0),
        "w": int(v["width"]),
        "h": int(v["height"]),
        "fps": fps,
        "kbps": int(d["format"].get("bit_rate", 0) or 0) // 1000,
        "audio": any(s["codec_type"] == "audio" for s in d["streams"]),
    }


def human(n: float) -> str:
    return f"{n / 1e6:,.0f} MB"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report only")
    mode.add_argument("--apply", action="store_true", help="re-encode in place")
    ap.add_argument("--crf", type=int, default=CRF)
    ap.add_argument("--preset", default=PRESET)
    ap.add_argument("--maxrate", type=int, default=MAXRATE_K,
                    help="peak video bitrate ceiling in kbps (default %(default)s)")
    ap.add_argument("--keep-originals", metavar="DIR",
                    help="move each original here instead of deleting it")
    ap.add_argument("files", nargs="*", metavar="MP4",
                    help="specific files in final_gifs (default: every MP4)")
    args = ap.parse_args()

    which("ffmpeg")
    which("ffprobe")

    videos = ([MEDIA / Path(name).name for name in args.files]
              if args.files else sorted(MEDIA.glob("*.mp4")))
    invalid = [v.name for v in videos if v.suffix.lower() != ".mp4" or not v.is_file()]
    if invalid:
        sys.exit(f"MP4 file(s) not found in {MEDIA}: {', '.join(invalid)}")
    if not videos:
        sys.exit(f"No .mp4 files in {MEDIA}")

    plans = []
    for v in videos:
        info = probe(v)
        if info is None:
            print(f"  !! cannot probe {v.name} (Git LFS pointer? run: git lfs pull)")
            continue
        plans.append((v, info))

    if not plans:
        sys.exit("Nothing to do.")

    total = sum(i["size"] for _, i in plans)
    print(f"{len(plans)} videos, {human(total)}\n")
    print(f"{'file':<44}{'size':>9}{'WxH':>12}{'fps':>5}{'Mbps':>7}{'-> WxH':>12}")
    print("-" * 92)
    over = []
    for v, i in plans:
        geo = f"{i['w']}x{i['h']}"
        mbps = (i["size"] * 8 / i["dur"] / 1e6) if i["dur"] else 0
        tw, th = target_size(i["w"], i["h"])
        new_geo = f"{tw}x{th}" if (tw, th) != (i["w"], i["h"]) else "-"
        flag = "  <-- stalls" if mbps * 1000 > args.maxrate else ""
        if flag:
            over.append(v.name)
        print(f"{v.name[:43]:<44}{human(i['size']):>9}{geo:>12}"
              f"{i['fps']:>5.0f}{mbps:>7.2f}{new_geo:>12}{flag}")

    if args.check:
        print(f"\n{len(over)} of {len(plans)} exceed the {args.maxrate} kbps ceiling "
              f"and are the ones that stall on a real connection.")
        print(f"Estimated result at CRF {args.crf} with the cap: roughly "
              f"{human(total * 0.35)} ({human(total)} today).")
        print("Run with --apply to perform the re-encode.")
        return 0

    keep = Path(args.keep_originals).resolve() if args.keep_originals else None
    if keep:
        keep.mkdir(parents=True, exist_ok=True)

    print(f"\nRe-encoding at CRF {args.crf}, preset {args.preset}. "
          f"This takes a while — it is a one-time cost.\n")

    done_before = done_after = 0
    failures = []
    for n, (v, info) in enumerate(plans, 1):
        tmp = v.with_suffix(".compressing.mp4")
        t0 = time.time()
        tw, th = target_size(info["w"], info["h"])
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(v),
               "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
               "-maxrate", f"{args.maxrate}k", "-bufsize", f"{args.maxrate * 2}k",
               "-profile:v", "high", "-pix_fmt", "yuv420p"]
        if (tw, th) != (info["w"], info["h"]):
            cmd += ["-vf", f"scale={tw}:{th}:flags=lanczos"]
        if info["fps"] > MAX_FPS + 0.5:
            cmd += ["-r", str(MAX_FPS)]
        cmd += (["-c:a", "aac", "-b:a", AUDIO_KBPS, "-ac", "1", "-ar", "48000"]
                if info["audio"] else ["-an"])
        cmd += ["-movflags", "+faststart", str(tmp)]

        r = run(cmd)
        new = probe(tmp) if tmp.exists() else None
        if r.returncode != 0 or new is None or new["size"] == 0:
            failures.append(v.name)
            tmp.unlink(missing_ok=True)
            print(f"[{n}/{len(plans)}] FAILED {v.name}: {r.stderr.strip()[:160]}")
            continue

        # Never make a file bigger than it started.
        if new["size"] >= info["size"]:
            tmp.unlink(missing_ok=True)
            print(f"[{n}/{len(plans)}] kept original {v.name} (re-encode was larger)")
            done_before += info["size"]
            done_after += info["size"]
            continue

        if keep:
            shutil.move(str(v), str(keep / v.name))
        else:
            v.unlink()
        tmp.rename(v)

        done_before += info["size"]
        done_after += new["size"]
        pct = 100 * (1 - new["size"] / info["size"])
        print(f"[{n}/{len(plans)}] {v.name[:48]:<50} "
              f"{human(info['size']):>9} -> {human(new['size']):>9}  "
              f"-{pct:.0f}%  ({time.time() - t0:.0f}s)")

    print(f"\nTotal {human(done_before)} -> {human(done_after)}  "
          f"(-{100 * (1 - done_after / max(done_before, 1)):.0f}%)")
    if failures:
        print(f"\n{len(failures)} failed and were left untouched: {', '.join(failures)}")
        return 1
    print("\nNext: python tools/serve.py --manifest-only && ./start.sh  # verify playback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
