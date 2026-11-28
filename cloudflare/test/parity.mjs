// The preview's number against the published data. Run: node cloudflare/test/parity.mjs [docs] [world]
// Exit 1 on a miss.
//
// Without `world` (a fixture site): for every city, ?city=<id> and the city by its place id must say the
// `open` that docs/data/cities.json carries (the app's default quests on the city's newest day).
//
// With `world` (the world host's URL, e.g. https://sc-data.comentality.com/, or a folder holding its
// files): the page shows a city's and a part's newest day from the world's files, so the preview must
// say what the world's own summaries say, over the app's default quests counted in that city:
// city-quests.json for every city (and by its place id), city-parts/<city>.json for every part in
// data/parts/<city>.json (a part in `noFile` has nothing open). Those summaries are written by the world's
// publish independently of the per-place files the preview reads.
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { askFrom, previewFor } from "../src/preview.js";

const docs = process.argv[2] || path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "docs");
const worldAt = process.argv[3] || "";
const read = async (p) => { try { return JSON.parse(await readFile(path.join(docs, p), "utf8")); } catch { return null; } };
const world = !worldAt ? async () => null : /^https?:/.test(worldAt)
  ? async (p) => { const r = await fetch(new URL(p, worldAt.endsWith("/") ? worldAt : worldAt + "/")); if (r.status === 404) return null; if (!r.ok) throw new Error(`${p}: HTTP ${r.status}`); return r.json(); }
  : async (p) => { try { return JSON.parse(await readFile(path.join(worldAt, p.split("?")[0]), "utf8")); } catch { return null; } };

const quests = await read("data/quests.json");
const registry = quests.quests.map((q) => ({ name: q.name, defaultDisabled: !!q.defaultDisabled, status: q.status || {} }));
const load = { registry: async () => registry, site: read, world };
const nf = new Intl.NumberFormat("en-CA");
const cities = (await read("data/cities.json")).cities;

let missed = 0, checked = 0;
async function check(query, open, name) {
  const params = new URLSearchParams(query);
  const meta = await previewFor(askFrom(params), params, load);
  checked++;
  const says = open === 0 ? meta && meta.title === `No open StreetComplete quests in ${name}`
    : meta && (meta.title.startsWith(`${nf.format(open)} open StreetComplete quest`) || meta.title.startsWith(`Almost done: ${nf.format(open)} StreetComplete quest`))
      && meta.title.endsWith(` in ${name}`);
  if (!says) { missed++; console.log(`MISS ?${query}: expected ${open} in ${name}; the preview: ${meta ? meta.title : "none"}`); }
}

// a summary's row ({index: [open, ...]} or [[open, ...], ...]) over the default quests counted in the city
const total = (names, row, city) => names.reduce((s, q, i) => {
  const e = registry.find((x) => x.name === q);
  return e && !e.defaultDisabled && e.status[city] === "counted" ? s + ((row && row[i] && row[i][0]) || 0) : s;
}, 0);

const latest = await world("latest.json");
if (!worldAt) {
  for (const c of cities)
    for (const query of [`city=${c.id}`, c.place ? `place=${c.place}` : null].filter(Boolean)) await check(query, c.open, c.name);
  console.log(`${checked - missed} of ${checked} links say cities.json's number`);
} else {
  const v = encodeURIComponent(latest.v);
  const cq = await world(`city-quests.json?v=${v}`);
  for (const c of cities) {
    if (!cq.places[c.id]) continue;
    const open = total(cq.quests, cq.places[c.id], c.id);
    for (const query of [`city=${c.id}`, c.place ? `place=${c.place}` : null].filter(Boolean)) await check(query, open, c.name);
  }
  const cityLinks = checked;
  const jobs = [];
  for (const c of cities) {
    const [kids, names] = await Promise.all([world(`${latest.cityParts}${c.id}.json?v=${v}`), read(`data/parts/${c.id}.json`)]);
    if (!kids || !names) continue;
    for (const p of names.parts || []) {
      const row = (kids.places || {})[p.id];
      if (!row && !(kids.noFile || []).includes(p.id)) continue;
      jobs.push(() => check(`city=${c.id}&part=${p.id}`, row ? total(kids.quests, row, c.id) : 0, `${p.en || p.name}, ${c.name}`));
    }
  }
  for (let i = 0; i < jobs.length; i += 16) await Promise.all(jobs.slice(i, i + 16).map((j) => j()));
  console.log(`${checked - missed} of ${checked} links say the world's number of ${latest.date} (${cityLinks} city, ${checked - cityLinks} part)`);
}
process.exit(missed ? 1 : 0);
