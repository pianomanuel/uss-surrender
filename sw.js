self.addEventListener('install', e => {
  e.waitUntil(caches.open('flare-3d-v1').then(c => c.addAll([
    './deck13-3d.html',
    './three.min.js',
    './manifest.webmanifest'
  ])));
});
self.addEventListener('fetch', e => {
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
