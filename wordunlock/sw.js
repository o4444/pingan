// WordUnlock 離線快取。更新 index.html 後，請把版本號 v2 改成 v3、v4…，手機才會抓到新版。
const C = 'wordunlock-v3';
const A = ['./', 'index.html', 'manifest.webmanifest', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png', 'apple-touch-icon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(C).then(c => Promise.all(A.map(u => c.add(u).catch(() => {})))).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('wordunlock-') && k !== C).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

// 先用快取（離線也能開），同時在背景更新
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  // 網頁本身：先抓網路上的新版，沒網路才用快取
  if (e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request).then(r => { const copy = r.clone(); caches.open(C).then(c => c.put('index.html', copy)); return r; })
      .catch(() => caches.match('index.html')));
    return;
  }
  e.respondWith(
    caches.match(e.request, { ignoreSearch: true }).then(hit => {
      const net = fetch(e.request).then(r => {
        if (r && r.ok) { const copy = r.clone(); caches.open(C).then(c => c.put(e.request, copy)); }
        return r;
      }).catch(() => hit || caches.match('index.html'));
      return hit || net;
    })
  );
});
