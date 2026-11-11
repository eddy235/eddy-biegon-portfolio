const CACHE="tulia-v1-static";
const PAGES=["/","/register","/my-visit","/reception","/assets/styles.css","/assets/app.js","/assets/icon.svg"];
self.addEventListener("install", event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(PAGES)));self.skipWaiting()});
self.addEventListener("activate",event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))));self.clients.claim()});
self.addEventListener("fetch",event=>{
  if(event.request.method!=="GET"||new URL(event.request.url).pathname.startsWith("/api/"))return;
  event.respondWith(fetch(event.request).then(response=>{
    if(response.ok&&new URL(event.request.url).origin===self.location.origin){
      const copy=response.clone();caches.open(CACHE).then(c=>c.put(event.request,copy));
    }return response;
  }).catch(()=>caches.match(event.request)))
});
