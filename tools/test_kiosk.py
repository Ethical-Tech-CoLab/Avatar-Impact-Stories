"""Regression suite covering the duplicate-tile, buffering, watermark and
background-swap work, plus the existing hang/leak protections.
"""
import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(r"c:\Dev\Kiosk - Many voices - final version")
PORT = 8078
URL = f"http://localhost:{PORT}"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"   {detail}" if detail else ""))


async def main():
    server = subprocess.Popen(
        [sys.executable, "tools/serve.py", "--port", str(PORT), "--no-browser"],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                args=["--autoplay-policy=no-user-gesture-required"])
            page = await browser.new_page(viewport={"width": 1920, "height": 1080})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            clog = []
            page.on("console", lambda m: clog.append(m.text))
            await page.goto(URL)
            await page.wait_for_timeout(1200)

            manifest = json.loads((ROOT / "stories.json").read_text(encoding="utf-8"))
            n = len(manifest["stories"])

            # --- 4. no duplicate tiles ---------------------------------------
            await page.click("text=Begin")
            await page.wait_for_timeout(1500)
            idx = await page.evaluate(
                "() => [...document.querySelectorAll('.phone-tile')]"
                ".map(t => t.dataset.storyIndex)")
            check("one tile per story", len(idx) == n, f"{len(idx)} tiles, {n} stories")
            check("no story appears twice", len(set(idx)) == len(idx),
                  f"{len(idx) - len(set(idx))} duplicates")
            check("every story is on the wall", len(set(idx)) == n)

            # Tiles must still fit the screen with the new auto grid.
            off = await page.evaluate("""() =>
                [...document.querySelectorAll('.phone-tile')].filter(t => {
                    const r = t.getBoundingClientRect();
                    return r.top < -1 || r.left < -1 ||
                           r.bottom > innerHeight + 1 || r.right > innerWidth + 1;
                }).length""")
            check("no tile escapes the viewport", off == 0, f"{off} off-screen")

            # Tiles must not overlap each other.
            overlaps = await page.evaluate("""() => {
                const r = [...document.querySelectorAll('.phone-tile')]
                    .map(t => t.getBoundingClientRect());
                let n = 0;
                for (let i = 0; i < r.length; i++)
                    for (let j = i + 1; j < r.length; j++)
                        if (!(r[i].right <= r[j].left || r[j].right <= r[i].left ||
                              r[i].bottom <= r[j].top || r[j].bottom <= r[i].top)) n++;
                return n;
            }""")
            check("no tiles overlap", overlaps == 0, f"{overlaps} overlapping pairs")

            # --- 6. AI watermark ---------------------------------------------
            await page.locator(".phone-tile").first.click()
            await page.wait_for_timeout(3500)
            state0 = await page.evaluate("""() => {
                const v = document.getElementById('player');
                return {t: v.currentTime, paused: v.paused, ready: v.readyState,
                        net: v.networkState, buffering:
                        document.getElementById('overlay').classList.contains('is-buffering'),
                        src: (v.currentSrc || '').split('/').pop()};
            }""")
            print(f"      cold-start state @3.5s: {state0}")
            badge = await page.evaluate("""() => {
                const b = document.getElementById('ai-badge');
                if (!b) return null;
                const s = getComputedStyle(b);
                const br = b.getBoundingClientRect();
                const fr = document.getElementById('player-frame').getBoundingClientRect();
                return {text: b.textContent.trim(), opacity: +s.opacity,
                        events: s.pointerEvents,
                        left: br.left - fr.left, bottomGap: fr.bottom - br.bottom,
                        w: br.width, h: br.height};
            }""")
            check("AI badge exists and reads 'AI'", badge and badge["text"] == "AI",
                  badge["text"] if badge else "missing")
            check("AI badge visible during playback", badge and badge["opacity"] > 0.5,
                  f"opacity {badge['opacity']}" if badge else "")
            check("AI badge in bottom-left of the video",
                  badge and badge["left"] < badge["w"] * 3
                  and badge["bottomGap"] < badge["h"] * 3,
                  f"left {badge['left']:.0f}px, bottom {badge['bottomGap']:.0f}px" if badge else "")
            check("AI badge does not block clicks",
                  badge and badge["events"] == "none")
            check("AI badge is semi-transparent white",
                  await page.evaluate(
                      "() => { const s = getComputedStyle(document.getElementById('ai-badge'));"
                      " return s.backgroundColor.startsWith('rgba') "
                      "&& s.color.includes('255'); }"))

            playing = await page.evaluate(
                "() => { const v = document.getElementById('player');"
                " return v.currentTime > 0.1 && !v.paused; }")
            if not playing:
                # Cold start on a large file: confirm it recovers rather than hangs.
                await page.wait_for_timeout(6000)
                playing = await page.evaluate(
                    "() => { const v = document.getElementById('player');"
                    " return v.currentTime > 0.1 && !v.paused; }")
                state1 = await page.evaluate("""() => {
                    const v = document.getElementById('player');
                    return {t: v.currentTime, paused: v.paused, ready: v.readyState};
                }""")
                print(f"      after 9.5s: {state1}")
            check("story plays", playing)
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(700)
            hidden = await page.evaluate(
                "() => +getComputedStyle(document.getElementById('ai-badge')).opacity")
            check("AI badge hidden when idle", hidden < 0.5, f"opacity {hidden}")

            # --- 3. buffering: range support + readiness gating ---------------
            # --- 3. buffering: cold-start latency must stay low ---------------
            # A cache miss must never block on downloading the whole file.
            await page.evaluate("""() => caches.keys()
                .then(k => Promise.all(k.map(n => caches.delete(n))))""")
            await page.wait_for_timeout(300)
            t0 = time.time()
            await page.locator(".phone-tile").nth(11).click()
            for _ in range(160):
                if await page.evaluate(
                        "() => { const v = document.getElementById('player');"
                        " return v.currentTime > 0.1 && !v.paused; }"):
                    break
                await page.wait_for_timeout(100)
            cold = time.time() - t0
            check("cold start under 4s (no full-file download)", cold < 4.0,
                  f"{cold:.1f}s")
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(800)

            # Second play of the same story should be served from the cache.
            t0 = time.time()
            await page.locator(".phone-tile").nth(11).click()
            for _ in range(160):
                if await page.evaluate(
                        "() => { const v = document.getElementById('player');"
                        " return v.currentTime > 0.1 && !v.paused; }"):
                    break
                await page.wait_for_timeout(100)
            warm = time.time() - t0
            check("repeat play is no slower", warm <= cold + 1.0,
                  f"{warm:.1f}s vs {cold:.1f}s cold")
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(700)

            v = manifest["stories"][0]["video"]
            r = await page.request.get(f"{URL}/{v}", headers={"Range": "bytes=100-999"})
            check("server honours range requests", r.status == 206,
                  f"status {r.status}")
            check("range response is the right size",
                  len(await r.body()) == 900, f"{len(await r.body())} bytes")
            check("server advertises Accept-Ranges",
                  r.headers.get("accept-ranges") == "bytes")
            rm = await page.request.get(f"{URL}/stories.json")
            check("manifest is not cached", "no-store" in rm.headers.get("cache-control", ""))
            rv = await page.request.get(f"{URL}/{v}")
            check("media is cacheable by the browser",
                  "max-age" in rv.headers.get("cache-control", ""),
                  rv.headers.get("cache-control", ""))
            check("service worker script is served",
                  (await page.request.get(f"{URL}/sw.js")).status == 200)
            check("player waits for data before playing",
                  "canplay" in (ROOT / "index.html").read_text(encoding="utf-8"))

            # --- leak + hang protections still hold ---------------------------
            heap0 = await page.evaluate(
                "() => performance.memory ? performance.memory.usedJSHeapSize : 0")
            ok = 0
            slow = []
            for i in range(8):
                await page.locator(".phone-tile").nth(i).click()
                started = False
                for tick in range(80):        # up to 8s
                    if await page.evaluate(
                            "() => { const v = document.getElementById('player');"
                            " return v.currentTime > 0.1 && !v.paused; }"):
                        started = True
                        if tick > 30:
                            slow.append(f"tile {i}: {tick / 10:.1f}s")
                        break
                    await page.wait_for_timeout(100)
                ok += 1 if started else 0
                if not started:
                    st = await page.evaluate("""() => {
                        const v = document.getElementById('player');
                        const o = document.getElementById('overlay');
                        return {t: v.currentTime, paused: v.paused, ready: v.readyState,
                                net: v.networkState, err: v.error && v.error.code,
                                open: o.classList.contains('is-open'),
                                buffering: o.classList.contains('is-buffering'),
                                src: decodeURIComponent((v.currentSrc||'').split('/').pop())};
                    }""")
                    print(f"      STUCK tile {i}: {st}")
                    for _l in clog[-14:]:
                        print("        | " + _l.replace(chr(10), " / ")[:260])
                    slow.append(f"tile {i}: never started")
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(600)
            check("8 consecutive stories play", ok == 8,
                  f"{ok}/8" + (f"; slow: {', '.join(slow)}" if slow else ""))
            check("single <video> reused", await page.locator("video").count() == 1)
            heap1 = await page.evaluate(
                "() => performance.memory ? performance.memory.usedJSHeapSize : 0")
            check("JS heap flat across plays", (heap1 - heap0) / 1e6 < 8,
                  f"{heap0/1e6:.1f} -> {heap1/1e6:.1f} MB")

            check("no uncaught page errors", not errors, "; ".join(errors[:2]))
            await browser.close()
    finally:
        server.terminate()

    print(f"\n{sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


sys.exit(asyncio.run(main()))

