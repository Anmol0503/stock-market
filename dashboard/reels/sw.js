/* Reels service worker — fresh when online, readable offline.
 *
 * This is a DAILY-updated app, so the cache must never win over the network when we're online.
 * Strategy = network-first for everything except immutable icons:
 *   - HTML shell, glossary.js, JSON  -> try network, cache the copy, fall back to cache offline.
 *     => a reload always shows today's deck + the latest UI when you have signal.
 *   - icons (*.png)                  -> cache-first (they don't change between versions).
 * Bump CACHE whenever this file changes so old caches are purged on activate.
 */
const CACHE = "reels-v5";   // bump on any UI change → activate purges the old cache so stale pages can't linger
const SHELL = ["./", "./index.html", "./manifest.json", "../glossary.js",
               "./icon-192.png", "./icon-512.png", "./icon-180.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => Promise.allSettled(SHELL.map(u => c.add(u)))));
  self.skipWaiting();                 // take over as soon as the new SW is installed
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))   // purge old versions
  ).then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const isIcon = /\.png$/.test(new URL(req.url).pathname);

  if (isIcon) {
    // cache-first: icons are effectively immutable
    e.respondWith(
      caches.match(req).then(hit => hit || fetch(req).then(res => {
        const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); return res;
      }))
    );
  } else {
    // network-first: HTML, glossary, and JSON are always fresh when online; cached copy is the
    // offline fallback only. `cache:"no-store"` bypasses the HTTP disk cache so we hit the CDN.
    e.respondWith(
      fetch(req, { cache: "no-store" }).then(res => {
        const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); return res;
      }).catch(() => caches.match(req, { ignoreSearch: true }))
    );
  }
});
