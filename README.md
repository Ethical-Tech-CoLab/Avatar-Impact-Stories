# Avatar Impact Stories — "Many Voices" Kiosk

An interactive kiosk / dashboard experience that surfaces first-person impact stories told
through AI-generated avatars. A wall of phone-shaped tiles loops silent GIF previews over a
crowd backdrop; tapping a tile enlarges it and plays the full story video with audio, then
returns the wall to its idle state.

This repository is the working home for the experience so the team can iterate on it and
publish updated demos to the website.

> Previously known as `bnf-msft-avatar-dashboard`.

---

## Contents

| Path | Description |
| --- | --- |
| `index.html` | The complete kiosk application — layout, tile grid, interaction and playback logic. No build step, no dependencies. |
| `final_gifs/` | Story media. Each story ships as a matched pair: a `.gif` loop used for the idle tile and an `.mp4` with audio used for full playback. |
| `Crowd.png` | Full-bleed background image for the tile wall. |
| `background testing.mp3` | Ambient crowd audio looped while the wall is idle. |
| `phone1.png` | Phone-frame reference art. |

## Running the kiosk

The app uses the **File System Access API** (`window.showDirectoryPicker`), which is only
available in Chromium-based browsers (Chrome, Edge) served over `http://localhost` or HTTPS.

1. Serve the repository root:

   ```bash
   python -m http.server 8000
   # or:  npx serve .
   ```

2. Open <http://localhost:8000/index.html> in Chrome or Edge.
3. Click **Select Directory** and choose the `final_gifs` folder, then grant read access.
4. The wall builds itself and the ambient audio starts. Click any tile to play its story.

> Opening `index.html` directly from the filesystem (`file://`) will not work — the directory
> picker and audio autoplay both require a served origin.

## How it works

- On directory selection, every `.mp4` and `.gif` in the chosen folder is read and paired by
  filename stem into a `videoGifMap`. Pairing is name-based, so **a GIF and its MP4 must share
  the exact same base filename.**
- A `ROWS x COLS` grid (default `5 x 6` = 30 tiles) is laid out with a small random position
  offset and rotation per tile so the wall reads as organic rather than gridded. Stories repeat
  if there are fewer stories than tiles.
- Clicking a tile pauses the ambient audio, scales the tile to center, waits `1500 ms`, then
  plays the paired MP4. On `ended`, the tile returns to its original position and rotation and
  the ambient bed resumes.

### Common tweaks

All of these live in `index.html`:

| What | Where |
| --- | --- |
| Grid size | `var ROWS = 5; var COLS = 6;` |
| Tile size | `tileWidth` / `tileHeight` in `calculateGridLayout()`, and `.phone-tile` width/height in CSS |
| Tile scatter & tilt | `randomX` / `randomY` / `rotation` multipliers in `createTiles()` |
| Zoom amount | `.enlarged` `scale()` in CSS and the inline `scale(4)` in `enlargeTile()` |
| Delay before playback | the `setTimeout(..., 1500)` in `enlargeTile()` |
| Background image / ambient track | `#output` `background-image` and the `#background-audio` `src` |

### Known issues / backlog

- `.enlarged` (CSS `scale(6.5)`) and the inline transform in `enlargeTile()` (`scale(4)`) disagree;
  the inline style wins. Consolidate to one source of truth.
- There is no way to dismiss an enlarged tile early — playback must finish. An escape/tap-out
  handler would help in a live kiosk.
- `TRIM.gif` currently has no matching `TRIM.mp4`, so that tile has nothing to play.
- Story filenames contain spaces, parentheses and typos (e.g. `Jaoanese`); worth normalizing
  before wiring these into a website.

## Working with the media (Git LFS)

The story GIFs and MP4s are large, so they are tracked with [Git LFS](https://git-lfs.com).
Install it once per machine before cloning:

```bash
git lfs install
git clone https://github.com/Ethical-Tech-CoLab/Avatar-Impact-Stories.git
```

If you cloned before installing LFS, run `git lfs pull` to fetch the real media files.

Adding a new story:

1. Export a matched pair with identical base filenames — `My Story.gif` and `My Story.mp4`.
2. Drop both into `final_gifs/`.
3. `git add final_gifs/ && git commit && git push` — LFS picks them up automatically via
   `.gitattributes`.

Zip archives are ignored by `.gitignore`; `final_gifs/` is the single source of truth.

## Content note

These stories depict human trafficking, forced and child labour, domestic violence and forced
conscription. Handle the media with care in any public-facing deployment.

