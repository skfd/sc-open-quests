// The site at street-complete-statistics.comentality.com: every path is an object in the R2 bucket
// sc-open-quests, which `python tools/cloud_publish.py` keeps equal to docs/. No build step.
// "/" and any path ending in "/" serve that folder's index.html. A missing object is a real 404,
// never index.html, so a chart that asks for a city the archive lacks fails the way it does on Pages.

const TYPES = {
  html: "text/html; charset=utf-8",
  js: "text/javascript; charset=utf-8",
  css: "text/css; charset=utf-8",
  json: "application/json; charset=utf-8",
  geojson: "application/geo+json; charset=utf-8",
  svg: "image/svg+xml",
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  webp: "image/webp",
  ico: "image/x-icon",
  txt: "text/plain; charset=utf-8",
  csv: "text/csv; charset=utf-8",
  md: "text/markdown; charset=utf-8",
  woff2: "font/woff2",
};

function contentType(key) {
  const ext = key.slice(key.lastIndexOf(".") + 1).toLowerCase();
  return TYPES[ext] || "application/octet-stream";
}

// The data changes once a day and the page with it; five minutes keeps a fresh run visible soon after
// upload while repeat visits revalidate cheaply by ETag.
const CACHE = "public, max-age=300";

export default {
  async fetch(request, env) {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method not allowed", { status: 405, headers: { Allow: "GET, HEAD" } });
    }
    const url = new URL(request.url);
    let key;
    try {
      key = decodeURIComponent(url.pathname).replace(/^\/+/, "");
    } catch {
      return new Response("Bad path", { status: 400 });
    }
    if (key === "" || key.endsWith("/")) key += "index.html";
    if (key.split("/").some((p) => p === ".." || p === ".")) {
      return new Response("Bad path", { status: 400 });
    }

    const object = await env.SITE.get(key, { onlyIf: request.headers });
    if (object === null) {
      // a folder asked for without its slash: send it to the slash, as Pages does
      if (!key.endsWith("index.html") && !key.slice(key.lastIndexOf("/") + 1).includes(".")) {
        const index = await env.SITE.head(key + "/index.html");
        if (index) return Response.redirect(url.origin + url.pathname + "/" + url.search, 301);
      }
      return new Response("Not found", {
        status: 404,
        headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" },
      });
    }

    const headers = new Headers();
    headers.set("Content-Type", contentType(key));
    headers.set("Cache-Control", CACHE);
    headers.set("ETag", object.httpEtag);
    headers.set("Last-Modified", object.uploaded.toUTCString());
    headers.set("X-Content-Type-Options", "nosniff");

    // onlyIf matched no precondition: the body is absent and the client's copy is current
    if (!("body" in object) || object.body === undefined) {
      return new Response(null, { status: 304, headers });
    }
    return new Response(request.method === "HEAD" ? null : object.body, { headers });
  },
};
