# Transcription Guide

This guide explains how to transcribe audio from the avatar stories to text.

## Overview

Two Python utilities work together to transcribe stories:

1. **`transcribe_stories.py`** — Extracts audio and converts to text using OpenAI's Whisper
2. **`add_transcripts_to_manifest.py`** — Merges transcriptions into `stories.json`

Output is generated in three formats:
- **Markdown files** (`transcripts/*.md`) — Human-readable, one file per story
- **Plain text** (`transcripts/*.txt`) — Raw transcription text only
- **JSON manifest** (`transcripts_data.json`) — Structured data for integration

## Installation

First, install Whisper:

```bash
pip install openai-whisper
```

You may also need ffmpeg (for audio extraction):

```bash
# macOS (with Homebrew)
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows (with Chocolatey)
choco install ffmpeg

# Or download from https://ffmpeg.org/download.html
```

## Basic Usage

### 1. Transcribe All Stories

```bash
python tools/transcribe_stories.py
```

This will:
- Load the Whisper model
- Process all MP4 files in `final_gifs/`
- Auto-detect language for each story
- Write transcripts to `transcripts/` folder
- Generate `transcripts_data.json` manifest

### 2. Specify Language

If stories are in a specific language, you can hint it (faster and more accurate):

```bash
# Spanish stories
python tools/transcribe_stories.py --language es

# French stories
python tools/transcribe_stories.py --language fr
```

Language codes: `en`, `es`, `fr`, `de`, `it`, `pt`, `ru`, `zh`, `ja`, `ko`, etc.

### 3. Use a Larger Model

The default `base` model is fast and accurate. For better accuracy, use a larger model:

```bash
python tools/transcribe_stories.py --model medium
python tools/transcribe_stories.py --model large
```

**Model comparison:**

| Model | Size | Speed | Accuracy | Memory |
| --- | --- | --- | --- | --- |
| tiny | 39 MB | Very fast | Lower | ~1 GB |
| base | 140 MB | Fast | Good | ~2 GB |
| small | 466 MB | Moderate | Very good | ~3 GB |
| medium | 1.5 GB | Slower | Excellent | ~5 GB |
| large | 2.9 GB | Very slow | Best | ~10 GB |

### 4. Transcribe Specific Stories Only

```bash
python tools/transcribe_stories.py "Adam (Child Labour) - Alexa.mp4" "Amala (Child Labour) - Alexa.mp4"
```

### 5. Preview Without Writing

```bash
python tools/transcribe_stories.py --check
```

Shows what would be transcribed without creating any files.

### 6. Custom Output Directory

```bash
python tools/transcribe_stories.py --output-dir ./my_transcripts
```

### 7. Specific Output Formats

```bash
# Markdown only
python tools/transcribe_stories.py --format md

# Plain text only
python tools/transcribe_stories.py --format txt

# JSON only
python tools/transcribe_stories.py --format json

# All three (default)
python tools/transcribe_stories.py --format all
```

## Integrating Transcripts into the Manifest

Once transcriptions are complete, add them to `stories.json`:

```bash
python tools/add_transcripts_to_manifest.py
```

This adds a `transcript` field to each story with:
- Full text
- Detected language
- Duration
- Timestamp

### Preview Changes

```bash
python tools/add_transcripts_to_manifest.py --check
```

### Remove Transcripts

```bash
python tools/add_transcripts_to_manifest.py --clear
```

## Output Format

### Markdown Transcript (`transcripts/Story Name.md`)

```markdown
# Story Name

**Source:** `filename.mp4`  
**Language:** en  
**Duration:** 45.2s  
**Transcribed:** 2025-09-14T10:30:00

---

## Transcript

[Full transcribed text here...]

---

*This is an automated transcription created using OpenAI's Whisper model. Please review for accuracy.*
```

### JSON Manifest (`transcripts_data.json`)

```json
{
  "generated_at": "2025-09-14T10:30:00",
  "total_stories": 23,
  "transcribed_count": 23,
  "stories": {
    "Adam - child laborer": {
      "text": "...",
      "language": "en",
      "duration": 52.3,
      "transcribed_at": "2025-09-14T10:30:00"
    },
    ...
  }
}
```

### stories.json with Transcripts

```json
{
  "stories": [
    {
      "id": "Adam (Child Labour) - Alexa",
      "title": "Adam - child laborer",
      "poster": "...",
      "video": "...",
      "transcript": {
        "text": "My name is Adam. I was born in...",
        "language": "en",
        "duration": 52.3,
        "transcribed_at": "2025-09-14T10:30:00"
      }
    }
  ]
}
```

## Accuracy Notes

- Whisper is highly accurate for clear speech but may have issues with:
  - Heavy accents or dialectal speech
  - Background noise (crowd audio, music)
  - Multiple speakers
  - Technical or specialized terminology
  
**Always review transcripts manually** before publishing, especially for legal or sensitive content.

## Performance

Approximate transcription times (on a typical laptop):

- **Tiny model:** 30 stories in ~3 minutes
- **Base model:** 30 stories in ~8 minutes
- **Medium model:** 30 stories in ~25 minutes
- **Large model:** 30 stories in ~60+ minutes

GPU acceleration is available if you have CUDA or Metal support — Whisper will use it automatically.

## Troubleshooting

### "whisper command not found"

Install the package:
```bash
pip install openai-whisper
```

### "ffmpeg not found"

Install ffmpeg (see Installation section above).

### Model takes too long to download

Whisper downloads models on first run (~100-3000 MB depending on model size). This is cached locally, so subsequent runs are faster.

### Transcription quality is poor

- Try a larger model (`--model large`)
- Specify the language (`--language en`)
- Check if audio quality is good (listen to a story first)

### Transcripts don't match any stories

The matching algorithm looks for stories by:
1. Title field in stories.json
2. Story ID
3. Filename stem

If matching fails, you can manually edit `transcripts_data.json` to rename story keys, or use `add_transcripts_to_manifest.py --check` to preview the matching logic.

## Updating Transcripts

To re-transcribe after adding new stories:

```bash
# Transcribe only new stories
python tools/transcribe_stories.py new_story1.mp4 new_story2.mp4

# Then merge with existing manifest
python tools/add_transcripts_to_manifest.py
```

To update with a better model:

```bash
# Remove old transcripts
python tools/add_transcripts_to_manifest.py --clear

# Re-transcribe with better model
python tools/transcribe_stories.py --model large

# Re-merge
python tools/add_transcripts_to_manifest.py
```

## Next Steps

- Use transcripts for accessibility (closed captions)
- Add to searchable indexes or databases
- Generate reading materials or educational content
- Create multilingual versions
