# Avatar Impact Stories — "Many Voices"

An interactive kiosk that surfaces first-person impact stories told through AI-generated
avatars. A wall of phone-shaped tiles loops silent previews over a crowd backdrop; tapping a
tile plays that person's full story with audio, then returns the wall to its idle state.

<sub>Previously known as `bnf-msft-avatar-dashboard`.</sub>

---

## ▶ Start the experience

```bash
git lfs install          # once per machine — the media lives in Git LFS
git clone https://github.com/Ethical-Tech-CoLab/Avatar-Impact-Stories.git
cd Avatar-Impact-Stories
```

Then run the launcher for your platform:

| Platform | Command |
| --- | --- |
| Windows | `start.cmd` — or just double-click **start.cmd** in Explorer |
| macOS / Linux | `./start.sh` |

Your browser opens automatically at **<http://localhost:8000>**. Click **Begin**, then click any
phone to play its story.

That's the whole setup — no build, no install, no dependencies beyond Python 3, which ships
with macOS and most Linux distributions. On Windows, get it from
[python.org/downloads](https://www.python.org/downloads/).

<details>
<summary>Serving it some other way</summary>

Any static file server works — the app is one HTML file plus a JSON manifest:

```bash
python -m http.server 8000     # then open http://localhost:8000
npx serve .
```

If you skip `tools/serve.py` you must generate the manifest yourself at least once:

```bash
python tools/serve.py --manifest-only
```

It cannot be opened as a `file://` URL: the browser blocks `fetch()` of `stories.json` from the
local file system. The app detects this and tells you what to do.

</details>

## Contents

| Path | Description |
| --- | --- |
| `index.html` | The entire kiosk — layout, interaction and playback. No build step, no dependencies. |
| `stories.json` | Manifest of playable stories, plus grid and background settings. Generated, but safe to hand-edit. |
| `tools/serve.py` | Regenerates the manifest, serves the folder, opens the browser. |
| `start.cmd` / `start.sh` | One-click wrappers around `tools/serve.py`. |
| `final_gifs/` | Story media. Each story is a pair: a `.gif` loop for the idle tile and an `.mp4` with audio for playback. |
| `Crowd.png` | Background image for the wall. |
| `background testing.mp3` | Ambient audio looped while the wall is idle. |
| `phone1.png` | Phone-frame reference art. |

## How it works

- `stories.json` lists every story that has **both** a poster GIF and a playable MP4. Anything
  unpaired is left out of the manifest, so a half-finished export can never reach the wall.
- The grid (`5 × 6` = 30 tiles by default) is laid out with a small random offset and tilt per
  tile so the wall reads as organic rather than gridded. Story order is shuffled, and stories
  repeat if there are fewer than there are tiles.
- Tile size is derived from the viewport, so the wall fits any kiosk display without rows
  colliding.
- Videos use `preload="none"` and stream on demand — none of the ~860 MB of MP4 is fetched
  until someone actually taps a phone.
- Tapping a tile fades in a centred player that animates out from the tile's position and plays
  at full resolution. On finish it animates back and the ambient bed resumes.

### Adding a story

1. Export a matched pair with **identical base filenames** — `My Story.gif` and `My Story.mp4`.
2. Drop both into `final_gifs/`.
3. Run `start.cmd` / `./start.sh`. The manifest picks the pair up automatically and prints a
   warning for anything left unpaired.
4. Commit both files; `.gitattributes` routes them into Git LFS for you.

Titles are auto-derived from the filename. Edit the `title` field in `stories.json` to change
what appears under the player — regenerating the manifest preserves your edits.

### Tuning the wall

Grid settings live in `stories.json`, so you can adjust them without touching the code:

```jsonc
"grid": {
  "rows": 5,
  "cols": 6,
  "scatter": 0.16,   // positional jitter, as a fraction of tile size
  "gapRatio": 0.16,  // spacing between tiles, as a fraction of tile size
  "tilt": 4          // max rotation, degrees
}
```

Anything else — colours, timings, the copy on the start screen — is in `index.html`.

## Operating it as a kiosk

- Press <kbd>F11</kbd> for fullscreen, or launch Chrome/Edge with
  `--kiosk http://localhost:8000`.
- A story can always be dismissed with <kbd>Esc</kbd>, the **×** button, or a click outside the
  player.
- The wall self-heals: if a video fails to load, errors, or stalls, a watchdog restores the
  idle state instead of leaving the kiosk stuck on one tile.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Tiles are blank or videos won't play | The media is still Git LFS pointers. Run `git lfs pull`. `tools/serve.py` warns when it detects this. |
| "This page has to be served over http" | You opened `index.html` directly. Run `start.cmd` / `./start.sh`. |
| `Could not bind port 8000` | Something else is using it: `python tools/serve.py --port 8080`. |
| A story is missing from the wall | It has no matching `.mp4` (or no matching `.gif`). The launcher prints which files it skipped. |
| No ambient audio | Browsers block autoplay until you interact — click **Begin** first. |

## Known gaps

- `TRIM.gif` has no paired MP4, so it is excluded from the wall. Either export the video or
  delete the GIF.
- Filenames contain spaces, parentheses and a typo (`Jaoanese`). They work, but are worth
  normalising before these are wired into the public website.
- There is no attract/idle loop — the wall waits indefinitely between visitors.

## Content note

These stories depict human trafficking, forced and child labour, domestic violence and forced
conscription. Handle the media with care in any public-facing deployment.
