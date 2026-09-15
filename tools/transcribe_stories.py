#!/usr/bin/env python3
"""
Transcribe audio from story videos to text using OpenAI's Whisper.

Processes all MP4 files in final_gifs/ and outputs transcriptions as:
- Markdown files in transcripts/ folder (human-readable)
- JSON in transcripts_data.json (structured for manifest integration)

Usage:
    python tools/transcribe_stories.py              # transcribe all stories
    python tools/transcribe_stories.py --check      # preview without writing
    python tools/transcribe_stories.py story.mp4    # transcribe specific files
    python tools/transcribe_stories.py --model large --language en

Options:
    --check              Preview what would be transcribed, don't write
    --model MODEL        Whisper model size: tiny, base, small, medium, large (default: base)
    --language LANG      ISO-639-1 language code (e.g., en, es, fr). Auto-detect if not set
    --output-dir DIR     Write to custom directory (default: transcripts/)
    --format FORMAT      Output format: md, txt, json (default: all three)
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

try:
    import whisper
except ImportError:
    print(
        "whisper not installed. Install with:\n"
        "  pip install openai-whisper"
    )
    sys.exit(1)

# Add parent directory to path so we can import serve utilities
sys.path.insert(0, str(Path(__file__).parent))


def find_stories(media_dir: Path) -> list[Path]:
    """Find all MP4 files in the media directory."""
    videos = sorted(media_dir.glob("*.mp4"))
    if not videos:
        print(f"No MP4 files found in {media_dir}")
        return []
    return videos


def extract_story_name(video_path: Path) -> str:
    """Extract clean story name from filename."""
    name = video_path.stem  # Remove .mp4
    return name


def transcribe_file(
    video_path: Path, model, language: str = None
) -> dict:
    """
    Transcribe a single video file using Whisper.

    Args:
        video_path: Path to MP4 file
        model: Loaded Whisper model
        language: ISO-639-1 language code (optional)

    Returns:
        Dictionary with transcription data
    """
    print(f"  Transcribing: {video_path.name}...", end=" ", flush=True)

    try:
        # Transcribe with optional language hint
        result = model.transcribe(
            str(video_path),
            language=language,
            verbose=False
        )

        text = result.get("text", "").strip()
        detected_language = result.get("language", "unknown")

        print(f"✓ ({len(text)} chars, {detected_language})")

        return {
            "path": str(video_path.relative_to(video_path.parent.parent)),
            "filename": video_path.name,
            "story_name": extract_story_name(video_path),
            "text": text,
            "language": detected_language,
            "duration": result.get("duration", 0),
            "transcribed_at": datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"✗ Error: {e}")
        return {
            "path": str(video_path.relative_to(video_path.parent.parent)),
            "filename": video_path.name,
            "story_name": extract_story_name(video_path),
            "text": "",
            "language": "unknown",
            "error": str(e),
            "transcribed_at": datetime.now().isoformat(),
        }


def write_markdown(output_dir: Path, transcript: dict) -> None:
    """Write transcription as a readable Markdown file."""
    md_path = output_dir / f"{transcript['story_name']}.md"

    md_content = f"""# {transcript['story_name']}

**Source:** `{transcript['filename']}`
**Language:** {transcript['language']}
**Duration:** {transcript['duration']:.1f}s
**Transcribed:** {transcript['transcribed_at']}

---

## Transcript

{transcript['text']}

---

*This is an automated transcription created using OpenAI's Whisper model. Please review for accuracy.*
"""

    md_path.write_text(md_content, encoding="utf-8")


def write_plaintext(output_dir: Path, transcript: dict) -> None:
    """Write transcription as plain text file."""
    txt_path = output_dir / f"{transcript['story_name']}.txt"
    txt_path.write_text(transcript['text'], encoding="utf-8")


def write_json_manifest(output_dir: Path, transcripts: list[dict]) -> None:
    """Write all transcriptions as a single JSON manifest."""
    json_path = output_dir.parent / "transcripts_data.json"

    # Group by story name for easy lookup
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "total_stories": len(transcripts),
        "transcribed_count": sum(1 for t in transcripts if t.get("text")),
        "stories": {t["story_name"]: t for t in transcripts},
    }

    json_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"\nManifest written to: {json_path}")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Specific MP4 files to transcribe (default: all)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Preview only, don't write files",
    )
    parser.add_argument(
        "--model",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base)",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="ISO-639-1 language code (e.g., en, es, fr)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for transcripts (default: transcripts/)",
    )
    parser.add_argument(
        "--format",
        default="all",
        choices=["md", "txt", "json", "all"],
        help="Output format (default: all three)",
    )

    args = parser.parse_args()

    # Resolve paths
    repo_root = Path(__file__).parent.parent
    media_dir = repo_root / "final_gifs"
    output_dir = args.output_dir or (repo_root / "transcripts")

    # Create output directory
    if not args.check:
        output_dir.mkdir(exist_ok=True)

    # Find stories
    if args.files:
        videos = [media_dir / f for f in args.files]
        videos = [v for v in videos if v.exists()]
    else:
        videos = find_stories(media_dir)

    if not videos:
        print("No videos to process.")
        return 1

    print(f"Found {len(videos)} video(s) to transcribe")
    print(f"Model: whisper-{args.model}")
    if args.language:
        print(f"Language: {args.language}")
    print()

    if args.check:
        print("(--check mode: preview only, no files written)\n")

    # Load model
    print(f"Loading whisper-{args.model} model...")
    model = whisper.load_model(args.model)
    print()

    # Transcribe
    transcripts = []
    for video_path in videos:
        result = transcribe_file(video_path, model, args.language)
        transcripts.append(result)

    # Write output
    if not args.check and transcripts:
        print(f"\nWriting transcripts to: {output_dir}\n")

        for transcript in transcripts:
            if not transcript.get("error"):
                if args.format in ("md", "all"):
                    write_markdown(output_dir, transcript)
                    print(f"  ✓ {transcript['story_name']}.md")

                if args.format in ("txt", "all"):
                    write_plaintext(output_dir, transcript)
                    print(f"  ✓ {transcript['story_name']}.txt")

        if args.format in ("json", "all"):
            write_json_manifest(output_dir, transcripts)

    # Summary
    success_count = sum(1 for t in transcripts if not t.get("error"))
    error_count = len(transcripts) - success_count

    print(f"\n{'─' * 60}")
    print(f"Transcribed: {success_count}/{len(transcripts)}")
    if error_count:
        print(f"Errors: {error_count}")
        for t in transcripts:
            if t.get("error"):
                print(f"  • {t['filename']}: {t['error']}")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
