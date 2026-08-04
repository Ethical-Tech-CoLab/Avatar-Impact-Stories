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
// Lets a warm download be cancelled the instant a story opens. Pausing alone is
// not enough: a 30 MB file already in flight would keep its connection for as
// long as it takes to finish, which is exactly the case that made the first tap
// on a cold kiosk take the best part of a minute to start.
var inFlight = null;
// A URL that keeps failing (renamed, 404, too big for the quota) must not be
// retried forever, or the worker spins on it instead of warming everything else.
var attempts = Object.create(null);
var MAX_ATTEMPTS = 3;

function cacheInBackground(cache, key) {
    if (warming.has(key.url)) return Promise.resolve(false);
    warming.add(key.url);
    var controller = typeof AbortController === 'function' ? new AbortController() : null;
    inFlight = controller;
    var options = controller ? { signal: controller.signal } : undefined;

    return fetch(key, options).then(function (response) {
        if (response && response.status === 200) {
            return cache.put(key, response).then(function () { return true; });
        }
        return false;
    }).catch(function () {
        return false;       // aborted, offline, blocked, or out of quota
    }).then(function (stored) {
        warming.delete(key.url);
        if (inFlight === controller) inFlight = null;
        return stored;
    });
}

// One file at a time, and only while nothing is playing. Anything not stored —
// because it was cancelled or simply failed — goes back on the queue, so
// warming resumes where it left off once the wall is idle again.
function drainQueue() {
    if (draining || paused || !queue.length) return;
    draining = true;
    var href = queue.shift();
    caches.open(CACHE).then(function (cache) {
        var key = new Request(href, { credentials: 'same-origin' });
        return cache.match(key).then(function (hit) {
            return hit ? true : cacheInBackground(cache, key);
        });
    }).catch(function () {
        return false;
    }).then(function (stored) {
        // If warming was suspended while this was running, the failure is our
        // own abort rather than a problem with the file.
        var aborted = paused;
        if (stored) {
            delete attempts[href];
        } else {
            // A cancelled download does not count against the retry budget:
            // it was our own doing, not a problem with the file.
            if (!aborted) attempts[href] = (attempts[href] || 0) + 1;
            if ((attempts[href] || 0) < MAX_ATTEMPTS
                    && !warming.has(href) && queue.indexOf(href) === -1) {
                queue.push(href);
            }
        }
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

    // Whole-file requests — the tile GIFs, the poster images, the ambience.
    // Cache-first, and on a miss the *same* response that goes to the page is
    // what gets stored. Fetching a second copy for the cache doubles the bytes
    // on the wire, which is what made the tiles crawl in one at a time.
    if (!range) {
        event.respondWith(
            caches.open(CACHE).then(function (cache) {
                return cache.match(key).then(function (hit) {
                    if (hit) return hit;
                    return fetch(request).then(function (response) {
                        if (response && response.status === 200 && response.type === 'basic') {
                            var copy = response.clone();
                            event.waitUntil(cache.put(key, copy).catch(function () {}));
                        }
                        return response;
                    });
                });
            }).catch(function () {
                return fetch(request);
            })
        );
        return;
    }

    // Range requests come from <video>. A hit is sliced out of the stored file;
    // a miss goes straight to the network and nothing is started alongside it.
    // Pulling the whole file down in parallel would compete with the story
    // being watched for the handful of connections a browser allows per origin
    // — that is what caused the stalling and the audio drifting out of sync.
    // Videos are cached only by the idle warm queue, which runs one file at a
    // time and stops the moment a story opens.
    event.respondWith(
        caches.open(CACHE).then(function (cache) {
            return cache.match(key).then(function (hit) {
                if (hit) return sliceForRange(hit.clone(), range);
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
        // Cancel whatever is downloading now; it will be re-queued and picked
        // up again when the wall goes idle.
        if (inFlight) {
            try { inFlight.abort(); } catch (err) { /* already settled */ }
            inFlight = null;
        }
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

