// salesdee. service worker — network-first; cache is an offline fallback only (cache-first was a
// footgun in dev: stale CSS would stick forever). Registered only on real deployments (see base.html).
const CACHE = 'salesdee-v4';
const OFFLINE = '/static/offline.html';

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.add(OFFLINE)));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;
  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res && res.ok && url.pathname.startsWith('/static/')) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() =>
        caches.match(req).then((hit) => hit || (req.mode === 'navigate' ? caches.match(OFFLINE) : Response.error()))
      )
  );
});
