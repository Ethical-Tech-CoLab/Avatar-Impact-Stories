# Avatar Impact Stories — "Many Voices"

An interactive kiosk that surfaces first-person impact stories told through AI-generated
avatars. A wall of phone-shaped tiles loops silent previews over a crowd backdrop; tapping a
tile plays that person's full story with audio, then returns the wall to its idle state.

<sub>Previously known as `bnf-msft-avatar-dashboard`.</sub>

---

## ▶ Start the experience

**Live demo: <https://ethical-tech-colab.github.io/Avatar-Impact-Stories/>** — nothing to install.

To run it locally as a kiosk:

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

## About the project

**"Many Voices" was inspired by the Generative AI for Good programme and the work of
[Shiran Mlamdovsky Somech](https://www.generativeaiforgood.com/), whose advocacy for applying
generative AI to social impact is the reason this project exists.**

> The project leverages generative AI to create realistic avatars that deliver authentic survivor
> testimonies. This technology allows for the sharing of crucial, attention-grabbing stories while
> protecting survivors' identities, demonstrating how AI can be ethically applied to address
> pressing social issues and create empathy without compromising safety or dignity.
>
> — [Generative AI for Good](https://www.generativeaiforgood.com/)

That idea is the whole premise of this wall. Survivor testimony is the most persuasive evidence
there is, and it is also the most dangerous thing a survivor can give. Publishing a real face
alongside an account of trafficking or forced labour can expose someone to retaliation from the
very people they escaped. The conventional workarounds — silhouettes, voice modulation, an actor's
dramatic reading — all cost the thing that makes testimony land. A synthetic presenter breaks that
trade-off: the account stays first-person and human, while the identity behind it stays protected.

### How it was made

The avatars were produced in **Fall 2025** using **[D-ID](https://www.d-id.com/)**, which drives a
photorealistic presenter from a still image and a voice track. Each story is a matched pair — a
short silent GIF loop that lives on the idle wall, and the full MP4 with audio that plays when a
visitor taps it.

The work was done by students in the Fall 2025 cohort, advised by Shiran at Generative AI for
Good. They were taught not just the tooling but the craft and the ethics around it:

- **The tooling** — generating and directing an avatar, and the practical limits of what it can
  carry convincingly.
- **Researching the stories** — sourcing survivor accounts and other first-person material, and
  staying faithful to them.
- **Story length** — an avatar holds attention for a much shorter window than a human speaker.
  Testimony has to be tightened to that budget without flattening it. The stories here run roughly
  40 seconds to 2 minutes.
- **Cultural sensitivity** — matching presentation, language and delivery to the community a story
  comes from rather than defaulting to a Western frame. The wall includes stories in and from
  multiple languages and regions.
- **Ethical usage** — where synthesis is legitimate and where it is not: representing a real
  person's account without inventing one, keeping the account traceable to its source, and never
  passing a synthetic presenter off as the survivor themselves.

The stories collected here span human trafficking, forced and child labour, domestic violence,
forced conscription and cobalt mining — presented together so that no single account has to stand
in for the whole problem.

### Why a kiosk

The wall is built for a room, not a browser tab. Thirty phones loop silently over a crowd
backdrop — the visual argument is that these accounts are everywhere and mostly unheard. Nothing
plays until someone chooses it, which makes engagement a deliberate act rather than something
autoplayed at a passer-by. When a story ends, the wall returns to its idle state and waits.

## Contents

| Path | Description |
| --- | --- |
| `index.html` | The entire kiosk — layout, interaction and playback. No build step, no dependencies. |
| `sw.js` | Service worker that caches media locally so stories play from disk, not the network. |
| `stories.json` | Manifest of playable stories, plus grid and background settings. Generated, but safe to hand-edit. |
| `stories.web.json` | Published variant: posters from Pages, videos from release assets. Generated by `tools/publish_web.py`. |
| `tools/serve.py` | Regenerates the manifest, serves the folder, opens the browser. |
| `tools/compress_media.py` | Re-encodes the story videos to sane bitrates. |
| `tools/compress_posters.py` | Converts the tile GIFs to animated WebP (a tenth the size). |
| `tools/publish_web.py` | Uploads the videos as release assets and builds the web manifest. |
| `tools/test_kiosk.py` | End-to-end regression suite (see [Running the tests](#running-the-tests)). |
| `.github/workflows/pages.yml` | Builds and deploys the GitHub Pages demo. |
| `start.cmd` / `start.sh` | One-click wrappers around `tools/serve.py`. |
| `final_gifs/` | Story media. Each story is a set: a `.webp` loop for the idle tile (with a `.gif` fallback) and an `.mp4` with audio for playback. |
| `Crowd.png` | Default background image for the wall. Drop in `background.png` to override it. |
| `background testing.mp3` | Default ambient audio, looped while the wall is idle. Override with `background.mp3`. |
| `phone1.png` | Phone-frame reference art. |

## How it works

- `stories.json` lists every story that has **both** a poster GIF and a playable MP4. Anything
  unpaired is left out of the manifest, so a half-finished export can never reach the wall.
- The grid is **derived from how many stories exist**, and exactly one tile is created per story.
  A wall called *Many Voices* must never show the same face twice, so tiles are never padded out
  with repeats. Layout is chosen to match the display's shape, and a short final row is centred.
- Story order is shuffled on every load, with a small random offset and tilt per tile so the wall
  reads as organic rather than gridded.
- Tile size is derived from the viewport, so the wall fits any kiosk display without rows
  colliding.
- Media is cached locally by a service worker (`sw.js`), so a story plays from disk after its
  first fetch instead of re-streaming. Cache misses stream straight from the network — the cache
  fills in the background and never delays playback.
- Playback starts when the video is actually ready rather than on a fixed timer, and the
  watchdog is re-armed against the time remaining, so a slow network can't truncate a testimony.
- Tapping a tile fades in a centred player that animates out from the tile's position and plays
  at full resolution. On finish it animates back and the ambient bed resumes.
- An **AI** watermark sits over the bottom-left of every playing video: the presenter is
  synthetic, and the viewer should never have to guess.

### Replacing the background

Drop a file named **`background.png`** in the project root and restart. That's it — it takes
precedence over `Crowd.png` automatically, no code or JSON to edit.

| Drop in | Replaces |
| --- | --- |
| `background.png` (or `.jpg`, `.jpeg`, `.webp`) | The crowd backdrop behind the wall |
| `background.mp3` (or `.m4a`, `.ogg`, `.wav`) | The ambient audio bed |

The launcher prints which background it picked, so you can confirm it took effect:

```
Background: background.png + background testing.mp3
```

The image is drawn as `center / cover`, so anything at or above the kiosk's resolution works;
match the display's aspect ratio to avoid cropping. To go back to the original, delete or rename
your `background.png`. For a file kept somewhere else entirely, set `background.image` in
`stories.json` to any path or absolute URL — hand edits there are preserved.


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
  "rows": 0,         // 0 = fit the grid to the number of stories (recommended)
  "cols": 0,         // set both to force a fixed grid
  "scatter": 0.16,   // positional jitter, as a fraction of tile size
  "gapRatio": 0.16,  // spacing between tiles, as a fraction of tile size
  "tilt": 4          // max rotation, degrees
}
```

Leave `rows`/`cols` at `0` unless you have a reason not to. A fixed grid with more seats than
stories is what used to put the same person on the wall several times over; the generator now
detects that case and reverts to the automatic layout rather than padding with repeats. If you do
force a grid, surplus seats are left empty instead of duplicated.

Anything else — colours, timings, the copy on the start screen, the watermark — is in
`index.html`.

## Playback and buffering

Stories used to stutter, and they stuttered mid-testimony — the worst possible moment to lose
someone. There were seven separate causes, all now fixed:

1. **The local server ignored range requests.** Python's `SimpleHTTPRequestHandler` has no
   `Range` support at all, so the browser could not seek and had to refetch from byte zero.
   `tools/serve.py` now serves proper `206 Partial Content` responses.
2. **Playback started on a blind 550 ms timer**, regardless of whether anything had buffered.
   It now waits for the player to report it can actually play, with the open animation as a
   floor and the watchdog as the ceiling.
3. **The watchdog was armed from the video's duration** plus 8 seconds. Any stall longer than
   that cut the story off before the end. It is now re-armed against the time *remaining*, so
   buffering extends the deadline instead of truncating the testimony.
4. **Nothing was cached.** Every play re-streamed the whole file, even the same story twice in
   a row.
5. **Cache warming starved the story being watched.** Browsers allow only a handful of
   connections per origin, so background downloads queued ahead of the range requests the
   player was making. Stories failed with a network read error partway through opening, and
   the tile appeared to do nothing. Warming is now suspended — and any download already in
   flight is cancelled — for as long as a story is on screen.
6. **Every cached file was downloaded twice.** On a cache miss the worker fetched the file for
   the page *and* fetched a second copy to store, doubling the bytes on the wire. With 22 tile
   animations that alone was an extra 81 MB, which is why the wall trickled in one tile at a
   time. The response given to the page is now the one that gets stored.
7. **The media was too big for a real connection.** The tallest videos ran at 4.5 Mbps and the
   tile animations were 81 MB of GIF. Together they needed more bandwidth than an ordinary
   connection has — see [Media encoding](#media-encoding).

`sw.js` keeps media in the Cache API, so a story plays from local disk once fetched. While the
wall sits idle it warms a few stories ahead, one file at a time. The page sends the worker
`pause` when a story opens and `resume` when it closes; the warm queue survives the pause and
picks up where it left off, so warming can never compete with a story someone is actually
watching. Warming is skipped entirely on a metered or slow connection, and does not begin until
the tiles themselves have finished loading. `warmAhead` in `stories.json` controls how many
stories are pre-fetched — set it to the number of stories for a permanently installed kiosk on a
wired network, or `0` to turn it off. Media is served with a week-long `Cache-Control`, and the
manifest with `no-store` so it is never stale.

Two deliberate design choices worth knowing if you change this:

- **No blob URLs.** Caching via `URL.createObjectURL` would pin tens of megabytes of JS heap per
  story — that is the leak that used to kill the kiosk after a few hours. Going through a
  service worker keeps the bytes on disk and out of the heap.
- **A cache miss never blocks on the full download.** An earlier version fetched the whole file
  before releasing a single byte to the player, which made the *first* play slower than having
  no cache at all. Misses now stream straight from the network while the cache fills alongside.

The service worker needs a secure context, so it is active on GitHub Pages and on
`localhost`, and silently inactive elsewhere — playback still works, just without the cache.
Bump `CACHE` in `sw.js` if you ever need to invalidate everything.

## Running the tests

`tools/test_kiosk.py` drives a real browser against a real server and checks the things that
have actually broken before: duplicate tiles, the watermark, range support, cold and warm start
times, JS heap growth across plays, and eight stories played back to back.

```bash
pip install playwright
playwright install chromium
python tools/test_kiosk.py
```

It expects the media in `final_gifs/`, starts its own server, and prints a pass/fail line per
check. Several of the bugs it covers were intermittent, so if you are chasing a regression it is
worth running it a few times rather than once.

## Media encoding


The original exports were badly over-encoded — single talking-head avatars on static backgrounds
delivered at up to **11.4 Mbps**, which is near Blu-ray bitrate for the easiest content a codec
will ever see. Encoder settings were also inconsistent across the set: the same kind of shot
ranged from 640 kbps to 11,367 kbps depending on which export it came from.

`tools/compress_media.py` re-encodes everything at a constant quality target (x264 CRF 22) with a
hard bitrate ceiling, so each video gets the bitrate its content needs and no video can exceed
what a real connection will carry. Quality at the equivalent settings was verified with **VMAF**
against the original files — the same metric Netflix uses — where ≥ 95 is the accepted threshold
for *visually indistinguishable*:

| Sample | CRF 18 | CRF 20 | CRF 23 |
| --- | --- | --- | --- |
| Chocolate (9,549 kbps source) | **−73%, VMAF 95.7** | −79%, VMAF 94.8 | −86%, VMAF 93.1 |
| arabic (11,367 kbps source) | **−79%, VMAF 94.7** | −84%, VMAF 94.0 | −90%, VMAF 92.3 |
| Amala (9,580 kbps source) | — | −76%, VMAF 96.4 | −84%, VMAF 94.8 |
| Domestic Violence 3 (640 kbps source) | — | −62%, VMAF 96.4 | −69%, VMAF 95.7 |

The last row is the telling one: even the *smallest* file in the set, already at 640 kbps, still
had 62% of its bytes removed at VMAF 96.4. Nothing here was efficiently encoded.

Those figures measure quality against the source at full resolution. The shipped encode also
caps resolution and peak bitrate, which trades a little of that headroom for playback that
actually holds together on a real connection — a story that stalls every few seconds is worth
far less than one at 720p that does not.

Two deliberate choices:

- **A hard bitrate ceiling, not just a quality target.** Encoding on quality alone left the
  tallest videos at 4.5 Mbps. A stream only plays smoothly when its bitrate comfortably *fits*
  the viewer's connection, and one that exactly fills the link has no headroom — it rebuffers on
  the first hiccup and the audio drifts out of sync. Every encode is now capped at 1.8 Mbps, so
  the worst case is about half a typical connection rather than all of it.
- **Capped at 720 on the short side, and 30 fps.** These play in a phone-shaped tile, and full
  screen on a kiosk; 720 is the standard bar for talking-head video and is indistinguishable at
  viewing distance. `arabic.mp4` was also 60 fps, which spends bitrate on motion that a static
  avatar does not have.
- **Audio normalised** to mono AAC 96 kbps at 48 kHz. Sources ranged from 58–148 kbps at sample
  rates between 24 and 48 kHz, so levels and quality varied audibly between stories.

Result across the 21 stories: **371 MB → 120 MB**, peak bitrate **4.51 → 1.37 Mbps**, median
**1.30 → 0.42 Mbps**.

```bash
python tools/compress_media.py --check    # report only; flags what would stall
python tools/compress_media.py --apply --keep-originals ../originals
```

The tool never overwrites a file with a larger one, skips anything it can't probe (LFS pointers),
and writes to a temporary file so an interrupted run can't corrupt the media.

### The tile animations

The idle wall was 22 animated GIFs at roughly 4.5 MB each — **81 MB before a single story was
tapped**. GIF has no interframe compression worth the name, and on anything short of a wired
connection the wall itself saturated the link: tiles trickled in one at a time, and the first
story tapped had no bandwidth left to stream with.

`tools/compress_posters.py` converts them to animated WebP: the same `<img>`, the same looping
behaviour, no video decoders and no extra memory pressure — **81 MB → 10.6 MB (−87%)**. The GIFs
stay in place as a fallback, wired up through a `<picture>` element, so a browser that cannot
decode WebP still gets a wall.

```bash
python tools/compress_posters.py --apply
python tools/serve.py --manifest-only     # pick up the new posters
```

### Does it actually load faster?

Yes, and it is the difference between working and not working. Measured in Chromium throttled to
4 Mbps — an ordinary busy-venue or mobile connection:

| | Before | After |
| --- | --- | --- |
| Wall ready | tiles trickling in | 24.6 s, all 21 tiles |
| First story starts | **never** (gave up at 65 s) | 5.0 s |
| Second and third | — | 1.0 s, 0.9 s |
| Stalls during 20 s of playback | — | **0** |
| Buffered ahead | — | 28–60 s |
| Published artifact | 436 MB | 206 MB |

Before these changes the videos simply could not play at 4 Mbps: the tile GIFs and a 4.5 Mbps
stream together needed more bandwidth than the connection had.

## Publishing the demo to the web

The demo is live at **<https://ethical-tech-colab.github.io/Avatar-Impact-Stories/>** and
redeploys automatically on every push to `main`.

There is one non-obvious constraint worth knowing before you change anything here: GitHub's own
docs are explicit that *"Git LFS cannot be used with GitHub Pages sites"*. Point Pages at this
branch directly and every tile renders as a broken image, because Pages serves the ~130-byte LFS
*pointer file* instead of the media.

`.github/workflows/pages.yml` gets around that by checking out with `lfs: true`, so LFS is
resolved **at build time** and the artifact uploaded to Pages contains real bytes. Compression
also brought the media from 914 MB down to ~436 MB, comfortably inside the 1 GB Pages limit — so
the published site is entirely self-contained. No release assets, no CDN, no second manifest.

The workflow refuses to publish a broken site: it fails if any file is still an LFS pointer, if
the manifest references media that didn't ship, or if the artifact would exceed 1 GB.

### If the media outgrows the 1 GB limit

Adding another ~570 MB of stories would push it over. At that point move the videos off the site
and leave only the posters:

```bash
python tools/publish_web.py --check     # preview: names, sizes, artifact size
python tools/publish_web.py --upload    # create the release, upload, write stories.web.json
git add stories.web.json && git commit -m "Host media as release assets" && git push
```

The workflow detects `stories.web.json` and automatically switches to poster-only publishing.
`index.html` supports absolute media URLs, so nothing about the app changes — only the manifest
does. Release assets serve `206 Partial Content` with `Accept-Ranges: bytes`, so seeking and
streaming behave exactly as they do locally.

### Updating the demo later

Add a story as described under **Adding a story**, run `python tools/compress_media.py --apply`
so it matches the rest of the set, then commit and push. The site redeploys automatically.

<details>
<summary>Hosting the media somewhere other than releases</summary>

Set `mediaBase` in the manifest and use relative paths for everything else:

```jsonc
{
  "mediaBase": "https://cdn.example.org/many-voices/",
  "stories": [{ "poster": "final_gifs/x.gif", "video": "x.mp4" }]
}
```

Absolute URLs in a story's `poster` or `video` always win over `mediaBase`. Any static host
works, provided it supports range requests — Azure Blob Storage, Cloudflare R2 and S3 all do.
This is the better option for a high-traffic public site; release assets are subject to
fair-use bandwidth limits.

</details>

## Operating it as a kiosk

- Press <kbd>F11</kbd> for fullscreen, or launch Chrome/Edge with
  `--kiosk http://localhost:8000`.
- A story can always be dismissed with <kbd>Esc</kbd>, the **×** button, or a click outside the
  player.
- The wall self-heals: if a video fails to load, errors, or stalls, a watchdog restores the
  idle state instead of leaving the kiosk stuck on one tile.
- Let the wall sit for a minute after starting: the cache warms in the background, after which
  every story opens instantly and the kiosk keeps working even if the network drops.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Tiles are blank or videos won't play | The media is still Git LFS pointers. Run `git lfs pull`. `tools/serve.py` warns when it detects this. |
| "This page has to be served over http" | You opened `index.html` directly. Run `start.cmd` / `./start.sh`. |
| `Could not bind port 8000` | Something else is using it: `python tools/serve.py --port 8080`. |
| A story is missing from the wall | It has no matching `.mp4` (or no matching `.gif`). The launcher prints which files it skipped. |
| The same person appears twice | A fixed `rows`/`cols` in `stories.json` has more seats than stories. Set both to `0`, or rerun the launcher — it migrates this automatically. |
| No ambient audio | Browsers block autoplay until you interact — click **Begin** first. |
| Background change didn't apply | The launcher prints which background it picked. Check the filename is exactly `background.png` and sits in the project root, not `final_gifs/`. |
| Stories still buffer | Confirm the service worker is active (DevTools → Application → Service Workers). It needs `https` or `localhost`; on a plain-http LAN address it is disabled by the browser. |
| Stale media after replacing a file | The cache is keyed by URL. Bump `CACHE` in `sw.js`, or clear site data. |
| Published site shows broken tiles | Pages is serving LFS pointers. Deploy via the included Actions workflow rather than pointing Pages at a branch. |

## Known gaps

- `TRIM.gif` has no paired MP4, so it is excluded from the wall. Either export the video or
  delete the GIF.
- Filenames contain spaces, parentheses and a typo (`Jaoanese`). They work, but are worth
  normalising before these are wired into the public website.
- Several stories are unnamed or weakly named (`vid`, `zoti`, `zoti (1)`, `zoti (2)`, `arabic`).
  They are distinct testimonies, but the titles shown under the player come from the filenames,
  so these read poorly on a public wall. Edit the `title` field in `stories.json` — regenerating
  the manifest preserves your edits.
- There is no attract/idle loop — the wall waits indefinitely between visitors.

## Content note

These stories depict human trafficking, forced and child labour, domestic violence and forced
conscription. Handle the media with care in any public-facing deployment.
