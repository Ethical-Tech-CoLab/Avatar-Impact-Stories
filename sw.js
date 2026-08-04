/* Many Voices — offline media cache.
 *
 * The kiosk streams 5-30 MB videos on demand. Over a venue's Wi-Fi that shows
 * up as stalling part-way through a testimony, which is the worst possible
 * moment to lose someone's attention.
 *
 * This worker keeps the media in the Cache API, so the second play of any
 * story — and every play after a warm-up pass — is served from local disk at
 * disk speed. It deliberately does NOT use blob URLs: holding a 30 MB blob per
 * story in JS memory is what used to make the kiosk die after a few hours.
 *
 * The only real subtlety is range requests. A <video> element asks for byte
 * ranges, and the Cache API stores whole responses, so a cached hit has to be
 * sliced into a synthetic 206 by hand. Safari refuses to play if it asks for a
 * range and gets a 200 back.
 */

var CACHE = 'many-voices-media-v1';
var MEDIA = /\.(mp4|gif|png|jpg|jpeg|webp|mp3|m4a|ogg|wav)$/i;

self.addEventListener('install', function (event) {
    self.skipWaiting();
});

self.addEventListener('activate', function (event) {
    event.waitUntil(
        caches.keys().then(function (names) {
            return Promise.all(names.map(function (name) {
                return name === CACHE ? null : caches.delete(name);
            }));
        }).then(function () {
            return self.clients.claim();
        })
    );
});

function sliceForRange(response, rangeHeader) {
    return response.arrayBuffer().then(function (buffer) {
        var total = buffer.byteLength;
        var match = /bytes=(\d*)-(\d*)/.exec(rangeHeader || '');
        if (!match) {
            return new Response(buffer, {
                status: 200,
                headers: {
                    'Content-Type': response.headers.get('Content-Type') || 'application/octet-stream',
                    'Content-Length': String(total),
                    'Accept-Ranges': 'bytes'
                }
            });
        }

        var start;
        var end;
        if (match[1] === '') {
            // "bytes=-500" means the last 500 bytes.
            start = Math.max(0, total - parseInt(match[2], 10));
            end = total - 1;
        } else {
            start = parseInt(match[1], 10);
            end = match[2] === '' ? total - 1 : parseInt(match[2], 10);
        }
        end = Math.min(end, total - 1);

        if (isNaN(start) || start > end || start >= total) {
            return new Response(null, {
                status: 416,
                headers: { 'Content-Range': 'bytes */' + total }
            });
        }

        return new Response(buffer.slice(start, end + 1), {
            status: 206,
            statusText: 'Partial Content',
            headers: {
                'Content-Type': response.headers.get('Content-Type') || 'application/octet-stream',
                'Content-Range': 'bytes ' + start + '-' + end + '/' + total,
                'Content-Length': String(end - start + 1),
                'Accept-Ranges': 'bytes'
            }
        });
    });
}

// URLs currently being pulled into the cache in the background, so a burst of
// range requests for the same video does not start a dozen parallel downloads.
var warming = new Set();

// Warming is suspended while a story is on screen. A browser allows only a
// handful of connections per origin, so a background download will happily
// starve the range requests the <video> element is making for the story someone
// is actually watching — which surfaces as a mid-sentence stall, or as an
// outright read failure that drops the visitor back to the wall.
var paused = false;
var queue = [];
var draining = false;

function cacheInBackground(cache, key) {
    if (warming.has(key.url)) return Promise.resolve();
    warming.add(key.url);
    return fetch(key).then(function (response) {
        if (response && response.status === 200) {
            return cache.put(key, response);
        }
        return null;
    }).catch(function () {
        return null;        // offline, blocked, or out of quota; try again later
    }).then(function () {
        warming.delete(key.url);
    });
}

// One file at a time, and only while nothing is playing. The queue survives a
// pause, so warming picks up where it left off once the wall is idle again.
function drainQueue() {
    if (draining || paused || !queue.length) return;
    draining = true;
    var href = queue.shift();
    caches.open(CACHE).then(function (cache) {
        var key = new Request(href, { credentials: 'same-origin' });
        return cache.match(key).then(function (hit) {
            return hit ? null : cacheInBackground(cache, key);
        });
    }).catch(function () {
        return null;
    }).then(function () {
        draining = false;
        drainQueue();
    });
}

self.addEventListener('fetch', function (event) {
    var request = event.request;
    if (request.method !== 'GET') return;

    var url;
    try {
        url = new URL(request.url);
    } catch (err) {
        return;
    }
    if (url.origin !== self.location.origin) return;
    if (!MEDIA.test(url.pathname)) return;

    var range = request.headers.get('range');
    // Range requests are never matched directly; the cache holds whole files.
    var key = new Request(url.href, { credentials: 'same-origin' });

    event.respondWith(
        caches.open(CACHE).then(function (cache) {
            return cache.match(key).then(function (hit) {
                if (hit) {
                    return range ? sliceForRange(hit.clone(), range) : hit;
                }

                // Cache miss. Do NOT make the viewer wait for the whole file:
                // blocking a range request on a full download is slower than no
                // cache at all, and it is exactly what makes the first play of a
                // story stall. Serve this request straight from the network and
                // populate the cache alongside it, so the *next* play is local.
                //
                // While a story is playing the extra download would compete with
                // it for the connection budget, so it is queued for later
                // instead.
                if (paused) {
                    if (queue.indexOf(key.url) === -1) queue.push(key.url);
                } else {
                    event.waitUntil(cacheInBackground(cache, key));
                }
                return fetch(request);
            });
        }).catch(function () {
            return fetch(request);
        })
    );
});

// The page drives warming: it asks for stories to be cached while the wall is
// idle, and suspends that work for as long as a story is on screen.
self.addEventListener('message', function (event) {
    var data = event.data || {};

    if (data.type === 'pause') {
        paused = true;
        return;
    }
    if (data.type === 'resume') {
        paused = false;
        drainQueue();
        return;
    }
    if (data.type !== 'warm' || !Array.isArray(data.urls)) return;

    data.urls.forEach(function (href) {
        if (queue.indexOf(href) === -1) queue.push(href);
    });
    drainQueue();
});
