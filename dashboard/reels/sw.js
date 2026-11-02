/* The Briefing — service worker. Fresh when online, readable offline.
 *
 * - Precaches the app shell (+ digest.html, the old Daily Digest archive page).
 * - Network-first for HTML / JS / CSS / JSON: a daily product must never show yesterday's edition because a cache won.
 *   The cached copy is only the offline fallback. Cache keys drop the "_" cache-busting query the app adds.
 * - Cache-first for images and fonts (they don't change once published).
 * - Does NOT intercept video: no `destination === "video"`, no Range requests, no *.mp4. Media elements stream with
 *   Range requests; answering them from a service worker breaks seeking and iOS playback.
 * - Cross-origin requests other than images/fonts (e.g. source links) go straight to the network.
 * Bump CACHE whenever this file or the shell changes; activate purges every other cache (including old reels-v*).
 */
const CACHE = "briefing-v1";
const SHELL = ["./", "./index.html", "./app.css", "./app.js", "./player.js", "./manifest.json", "./digest.html",
               "./icon-180.png", "./icon-192.png", "./icon-512.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => Promise.allSettled(SHELL.map(u => c.add(new Request(u, { cache: "reload" }))))));
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

/** Cache key without the app's "_=<timestamp>" cache-buster, so the cache holds one copy per file. */
function cacheKey(url) {
  const u = new URL(url);
  u.searchParams.delete("_");
  return u.toString();
}

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Never touch media: let the browser stream it (Range requests) straight from the network.
  if (req.destination === "video" || req.destination === "audio" || req.headers.has("range") || /\.(mp4|m4v|webm|mov|m3u8)$/i.test(url.pathname)) return;

  const isFont = req.destination === "font" || /\.(woff2?|ttf|otf)$/i.test(url.pathname) || url.hostname === "fonts.gstatic.com";
  const isImage = req.destination === "image" || /\.(jpe?g|png|webp|gif|avif|svg)$/i.test(url.pathname);
  const sameOrigin = url.origin === self.location.origin;
  const isFontCss = url.hostname === "fonts.googleapis.com";

  if (!sameOrigin && !isImage && !isFont && !isFontCss) return;     // e.g. outbound source links

  if (isImage || isFont) {
    // cache-first: published images/fonts never change; opaque cross-origin responses cache fine
    e.respondWith(caches.open(CACHE).then(c => c.match(req).then(hit => hit || fetch(req).then(res => {
      if (res && (res.ok || res.type === "opaque")) c.put(req, res.clone()).catch(() => {});
      return res;
    }))));
    return;
  }

  // network-first for HTML, JS, CSS, JSON (and the Google Fonts stylesheet); cached copy only when offline
  const key = cacheKey(req.url);
  e.respondWith(
    fetch(req, { cache: "no-store" }).then(res => {
      // (the Google Fonts stylesheet is an opaque no-cors response; keep it too so fonts work offline)
      if (res && (res.ok || (isFontCss && res.type === "opaque"))) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(key, copy)).catch(() => {}); }
      return res;
    }).catch(() => caches.match(key).then(hit => hit || caches.match(req, { ignoreSearch: true })).then(hit => hit || Response.error()))
  );
});
