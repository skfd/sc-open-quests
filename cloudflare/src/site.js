// The site's one script (wrangler.previews.jsonc): it runs for the page itself, "/" and "/index.html",
// and for nothing else. A link to a place gets that place's og:title and og:description written into
// the head, so a network's crawler, which never runs app.js, shows "1,284 open StreetComplete quests in
// Agincourt North, Toronto" instead of the site's name. Every other path is a static asset served
// without this script. DESIGN.md, "Share previews: a Worker's text for every place".
//
// It can only add: on any failure, a slow host or a link that names no place, the page goes out as the
// asset is, byte for byte.

import { askFrom, previewFor } from "./preview.js";

const TIMEOUT_MS = 1500;          // the preview's whole budget; past it the reader gets the plain page
const MEMO_MS = 600000;           // the quest list and the cities change once a day
const MAX_JSON = 4 << 20;         // no file the preview reads is near this; a larger one is not parsed

const memo = new Map();           // path -> { at, value }, per isolate
async function memoized(path, read) {
  const hit = memo.get(path);
  if (hit && Date.now() - hit.at < MEMO_MS) return hit.value;
  const value = await read();
  if (value != null) memo.set(path, { at: Date.now(), value });
  return value;
}

async function jsonOf(response) {
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  if (Number(response.headers.get("Content-Length") || 0) > MAX_JSON) return null;
  return response.json();
}

function loaders(env, origin, signal) {
  const site = async (path) => jsonOf(await env.ASSETS.fetch(new Request(new URL("/" + path, origin)), { signal }));
  const world = async (path) => (env.WORLD_HOST ? jsonOf(await fetch(env.WORLD_HOST + path, { signal })) : null);
  return {
    // quests.json carries every city's status per quest; the preview needs two fields of each
    registry: () => memoized("registry", async () => {
      const q = await site("data/quests.json");
      return q && q.quests.map((x) => ({ name: x.name, defaultDisabled: !!x.defaultDisabled }));
    }),
    site: (path) => (path === "data/cities.json" ? memoized(path, () => site(path)) : site(path)),
    world,
  };
}

async function previewWithin(ms, ask, params, env, origin) {
  const ctl = new AbortController();
  let timer;
  const late = new Promise((resolve) => { timer = setTimeout(() => { ctl.abort(); resolve(null); }, ms); });
  try {
    return await Promise.race([previewFor(ask, params, loaders(env, origin, ctl.signal)), late]);
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

// The rewriter escapes an attribute's quotes and leaves & < > as they are: harmless inside the quotes, but
// a name holding "&amp;" would be read back as "&", so they are escaped here.
const attr = (value) => value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const content = (value) => ({ element(e) { e.setAttribute("content", attr(value)); } });

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const page = url.pathname === "/" || url.pathname === "/index.html";
    const ask = page && request.method === "GET" ? askFrom(url.searchParams) : null;
    if (!ask) return env.ASSETS.fetch(request);
    const meta = await previewWithin(TIMEOUT_MS, ask, url.searchParams, env, url.origin);
    if (!meta) return env.ASSETS.fetch(request);

    // The page asked afresh: a reader's If-None-Match is the asset's, and the head now follows the data, so it
    // goes out without the asset's validators (a revalidation can then never answer 304 onto an older
    // number) but with the asset's Cache-Control: the page is still asked for every time (docs/_headers).
    // <title> is left alone: app.js never sets it, so a rewritten one would stay on the tab after the
    // reader moves to another place. Networks read the og: tags.
    try {
      const asset = await env.ASSETS.fetch(new Request(new URL("/index.html", url.origin)));
      if (!asset.ok) return env.ASSETS.fetch(request);
      const headers = new Headers(asset.headers);
      for (const h of ["ETag", "Last-Modified", "Content-Length"]) headers.delete(h);
      // names are OpenStreetMap's text: they go in as attribute values only, escaped
      return new HTMLRewriter()
        .on('meta[property="og:title"]', content(meta.title))
        .on('meta[property="og:description"]', content(meta.description))
        .transform(new Response(asset.body, { status: 200, headers }));
    } catch {
      return env.ASSETS.fetch(request);
    }
  },
};
