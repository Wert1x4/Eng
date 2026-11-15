const CACHE = "lumen-app-2";
const FILES = [
  "/",
  "/index.html",
  "/css/app.css",
  "/js/app.js",
  "/js/i18n.js",
  "/js/device.js",
  "/pack.json",
  "/manifest.webmanifest",
  "/icon.svg",
  "/icon-180.png",
  "/icon-192.png",
  "/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => Promise.all(FILES.map((file) => cache.add(file).catch(() => {})))).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname === "/join.svg") return;
  event.respondWith(caches.match(event.request).then((hit) => hit || fetch(event.request)));
});
