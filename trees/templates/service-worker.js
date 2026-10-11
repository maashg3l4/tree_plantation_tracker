const CACHE_NAME = "tree-garden-v2";
const APP_SHELL = [
  "/static/trees/app.css",
  "/static/trees/icons/garden.svg",
  "/static/trees/manifest.webmanifest",
  "/offline/",
];
const PUBLIC_PAGE_PREFIXES = ["/community/", "/u/"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((response) => {
        if (!response.ok) return response;
        return caches.open(CACHE_NAME).then((cache) => cache.put(request, response.clone()))
          .then(() => response);
      })),
    );
    return;
  }

  if (PUBLIC_PAGE_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (
            !response.ok ||
            response.type !== "basic" ||
            response.headers.get("X-Public-Offline-Cacheable") !== "true"
          ) return response;
          return caches.open(CACHE_NAME)
            .then((cache) => cache.put(request, response.clone()))
            .then(() => response);
        })
        .catch(async () => (await caches.match(request)) || (await caches.match("/offline/"))),
    );
  }
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") self.skipWaiting();
});
