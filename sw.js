const CACHE = 'zw-v1';

self.addEventListener('install', () => { self.skipWaiting(); });

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  if (e.request.url.includes('tile.openstreetmap.org')) {
    e.respondWith(
      caches.open(CACHE).then((c) =>
        c.match(e.request).then((r) => r || fetch(e.request).then((res) => { c.put(e.request, res.clone()); return res; }))
      ).catch(() => fetch(e.request))
    );
    return;
  }
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
