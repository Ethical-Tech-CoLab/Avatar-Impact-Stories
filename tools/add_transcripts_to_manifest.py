#!/usr/bin/env python3
"""
Add transcriptions to the stories.json manifest.

Reads transcriptions from transcripts_data.json and merges them into stories.json,
adding a 'transcript' field to each story.

Usage:
    python tools/add_transcripts_to_manifest.py              # apply all
    python tools/add_transcripts_to_manifest.py --check      # preview only
    python tools/add_transcripts_to_manifest.py --clear      # remove transcripts from manifest
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime


def load_json(path: Path) -> dict:
    """Load JSON file safely."""
    if not path.exists():
        print(f"Error: {path} not found")
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error reading {path}: {e}")
        return {}


def find_story_by_name(stories: list, story_name: str) -> dict | None:
    """Find a story in the manifest by its story name."""
    for story in stories:
        # Try matching against the title or the ID
        if story.get("title", "").lower() == story_name.lower():
            return story
        if story.get("id", "").lower() == story_name.lower():
            return story
        # Also try matching the filename stem
        if Path(story.get("poster", "")).stem == story_name:
            return story
    return None


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Preview changes without writing",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Remove all transcripts from manifest",
    )
    parser.add_argument(
        "--transcript-file",
        type=Path,
        default=None,
        help="Custom path to transcripts_data.json",
    )

    args = parser.parse_args()

    # Resolve paths
    repo_root = Path(__file__).parent.parent
    manifest_path = repo_root / "stories.json"
    transcripts_path = args.transcript_file or (repo_root / "transcripts_data.json")

    # Load manifest
    manifest = load_json(manifest_path)
    if not manifest:
        return 1

    stories = manifest.get("stories", [])
    if not stories:
        print("No stories found in manifest")
        return 1

    # Handle --clear option
    if args.clear:
        removed_count = 0
        for story in stories:
            if "transcript" in story:
                del story["transcript"]
                removed_count += 1

        print(f"Removed transcripts from {removed_count} stories")

        if not args.check:
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            print(f"Manifest updated: {manifest_path}")

        return 0

    # Load transcripts
    transcripts_data = load_json(transcripts_path)
    if not transcripts_data:
        return 1

    story_transcripts = transcripts_data.get("stories", {})

    if not story_transcripts:
        print("No transcripts found")
        return 1

    # Match and add transcripts
    added_count = 0
    updated_count = 0
    not_found = []

    for story_name, transcript_data in story_transcripts.items():
        story = find_story_by_name(stories, story_name)

        if story is None:
            not_found.append(story_name)
            continue

        if "transcript" in story:
            updated_count += 1
            status = "updated"
        else:
            added_count += 1
            status = "added"

        # Add transcript field
        story["transcript"] = {
            "text": transcript_data.get("text", ""),
            "language": transcript_data.get("language", "unknown"),
            "duration": transcript_data.get("duration", 0),
            "transcribed_at": transcript_data.get("transcribed_at", ""),
        }

        if not args.check:
            print(f"  ✓ {story_name} ({status})")

    # Report
    print(f"\n{'─' * 60}")
    print(f"Added transcripts to: {added_count} stories")
    if updated_count:
        print(f"Updated transcripts for: {updated_count} stories")

    if not_found:
        print(f"\nCould not match {len(not_found)} transcript(s):")
        for name in not_found:
            print(f"  • {name}")

    # Write manifest
    if not args.check and (added_count or updated_count):
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"\n✓ Manifest updated: {manifest_path}")
    elif args.check:
        print("\n(--check mode: no changes written)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
