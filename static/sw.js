const CACHE = 'wishhub-v2';
const STATIC = [
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC).catch(() => {})));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});

// ── Клик по уведомлению → открыть приложение ──────────────────────────────
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const targetUrl = (e.notification.data && e.notification.data.url) || '/';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(cs => {
      // Если приложение уже открыто — фокусируемся на нём
      const existing = cs.find(c => new URL(c.url).origin === self.location.origin);
      if (existing) return existing.focus();
      return clients.openWindow(targetUrl);
    })
  );
});

// ── Входящий Push (для будущего Web Push с сервера) ───────────────────────
self.addEventListener('push', e => {
  if (!e.data) return;
  let data = {};
  try { data = e.data.json(); } catch(_) { data = { title: 'WishHub', body: e.data.text() }; }
  e.waitUntil(
    self.registration.showNotification(data.title || 'WishHub 🎁', {
      body:    data.body || '',
      icon:    '/static/icon-192.png',
      badge:   '/static/icon-192.png',
      vibrate: [300, 100, 300],
      tag:     data.tag || 'wishhub',
      data:    { url: data.url || '/' },
    })
  );
});
