// What a link's preview says: the title and description a network shows for a link to a place
// (DESIGN.md, "Share previews: a Worker's text for every place"). Pure functions, no Worker API, so node
// tests them (cloudflare/test/). The numbers are the page's: each function here follows the one in
// docs/app.js it names, and tests/test_preview_worker.py holds them to the published data.

const WEEKS4 = 28;                           // app.js WEEKS4: the place's 4-week change, in days
const SEL_BASES = ["app", "none", "all"];
const CITY_ID = /^[a-z0-9][a-z0-9-]{0,63}$/;
const PLACE_ID = /^[0-9a-f]{12}$/;
const SHARD = /^[a-z0-9_-]{1,16}\/[a-z0-9_-]{1,32}$/;
const DAY = /^\d{4}-\d\d-\d\d$/;
const R = { id: 0, name: 1, parent: 3, en: 8, counted: 9 };   // a name-layer row (app.js R)
const COUNTED = /^[a-z0-9][a-z0-9-]{0,63}(\/[0-9a-f]{12})?$/;   // a row's counted column: "toronto", "toronto/<part id>"

const nf = new Intl.NumberFormat("en-CA");
const dayTs = (d) => Date.UTC(+d.slice(0, 4), +d.slice(5, 7) - 1, +d.slice(8, 10)) / 1000;
const addDays = (d, n) => new Date((dayTs(d) + n * 86400) * 1e3).toISOString().slice(0, 10);
const shortDate = (d) => new Date(dayTs(d) * 1e3).toLocaleDateString("en-CA", { month: "short", day: "numeric", timeZone: "UTC" });
const names = (v) => (v || "").split(",").filter(Boolean);

// Which place a link shows, as app.js readURL decides it: ?place= wins, the compare and map views are no
// place, else ?city= with its ?part=. Null for the home page, for a link with the test hooks (?data=,
// ?world=) and for ids that are not ids, so no path is ever built from a reader's text.
export function askFrom(params) {
  if (params.has("data") || params.has("world")) return null;
  const place = params.get("place");
  if (place) {
    if (!PLACE_ID.test(place)) return null;    // a country addressed by its code has no world file
    const placeIn = params.get("in") || "";
    return { kind: "place", place, placeIn: SHARD.test(placeIn) ? placeIn : "" };
  }
  if (params.get("view")) return null;
  const city = params.get("city");
  if (!city || !CITY_ID.test(city)) return null;
  const part = params.get("part") || "";
  if (part && !PLACE_ID.test(part)) return null;
  return { kind: "city", city, part };
}

// The quests the link counts (app.js resolveSelection): ?base= app (the app's defaults), none or all,
// then ?on= ticked on top and ?off= unticked. registry is [{name, defaultDisabled}].
export function selectionFrom(params, registry) {
  const base = SEL_BASES.includes(params.get("base")) ? params.get("base") : "app";
  const known = new Set(registry.map((q) => q.name));
  const s = new Set(registry.filter((q) => base === "all" || (base === "app" && !q.defaultDisabled)).map((q) => q.name));
  for (const n of names(params.get("on"))) if (known.has(n)) s.add(n);
  for (const n of names(params.get("off"))) s.delete(n);
  return s;
}

// A city's or part's series at its newest date and 4 weeks before it (app.js renderTiles): the newest
// count at least 28 days older, else the first count ("young", a part's starts 2026-10-27). Per quest
// [open, aged] on each of the two dates, null where the quest was not counted then.
export function seriesPairs(h) {
  const n = h && Array.isArray(h.dates) ? h.dates.length : 0;
  if (!n || !h.quests) return null;
  const i = n - 1;
  let j = -1;
  for (let k = 0; k < i; k++) if (h.dates[k] <= addDays(h.dates[i], -WEEKS4)) j = k;
  const young = j < 0;
  if (young) j = 0;
  const at = (s, k) => (s.open[k] == null ? null : [s.open[k], s.agedOnly ? s.agedOnly[k] : null]);
  const pairs = new Map();
  for (const [name, s] of Object.entries(h.quests)) pairs.set(name, { now: at(s, i), then: n > 1 ? at(s, j) : null });
  return { date: h.dates[i], since: n > 1 && young ? h.dates[j] : null, compared: n > 1, pairs };
}

// Change points [[day, open, aged], ...] at day k (app.js pointAt): 0 before the first, nothing past k.
function pointAt(points, k) {
  let v = [0, 0];
  for (const [i, open, aged] of points || []) { if (i > k) break; v = [open, aged]; }
  return v;
}

// Is this a latest.json the page would read (app.js worldPlace)?
export function worldLatestOk(latest) {
  return !!latest && latest.schema === 2 && latest.v != null && !!latest.place && !!latest.children &&
    Array.isArray(latest.quests) && [latest.date, latest.first, latest.back].every((d) => DAY.test(d));
}

// A world place's file at latest.date and 4 weeks before it (app.js worldSeries, then renderTiles): the
// days run from the place's first counted day (`from`) through latest.date, and a point past latest.date
// is not read. Null when the place was first counted after latest.date.
export function worldPairs(latest, pf) {
  const last = Math.round((dayTs(latest.date) - dayTs(latest.first)) / 86400);
  const from = Number.isInteger(pf.from) && pf.from > 0 ? pf.from : 0;
  if (!(last >= from)) return null;
  const young = last - WEEKS4 < from;
  const j = young ? from : last - WEEKS4;
  const compared = last > from;
  const pairs = new Map();
  for (const [name, points] of Object.entries(pf.quests || {}))
    pairs.set(name, { now: pointAt(points, last), then: compared ? pointAt(points, j) : null });
  return { date: latest.date, since: compared && young ? addDays(latest.first, from) : null, compared, pairs };
}

// The page's three numbers over the selected quests: the total (app.js totalSeries; null when no selected
// quest was counted), the change over the same quests counted on both dates (likeForLike; aged null when
// a date has no aged split) and the three types with the most open.
export function summarize(pairs, sel) {
  let open = null, any = false, dOpen = 0, dAged = 0, agedKnown = true;
  const top = [];
  for (const [name, { now, then }] of pairs) {
    if (!sel.has(name) || !now) continue;
    open = (open || 0) + now[0];
    if (now[0]) top.push({ name, open: now[0] });
    if (!then) continue;
    dOpen += now[0] - then[0];
    if (now[1] == null || then[1] == null) agedKnown = false; else dAged += now[1] - then[1];
    any = true;
  }
  top.sort((a, b) => b.open - a.open);
  return { open, change: any ? { open: dOpen, aged: agedKnown ? dAged : null } : null, top: top.slice(0, 3) };
}

// "AddBenchBackrest" -> "bench backrest": the quest's name, not the app's question (app.js arrivalText).
export function questWords(name) {
  if (name === "OsmNoteQuestType") return "OSM notes";
  return name.replace(/([a-z0-9])([A-Z])/g, "$1 $2").replace(/([A-Z])([A-Z][a-z])/g, "$1 $2")
    .replace(/^Add /, "").toLowerCase();
}

// The words. Invite, never shame: a fall is said plainly, a rise that is mostly aging says so, and
// "almost done" is kept for a place that is both nearly empty and falling (a hamlet with 14 quests that
// nobody touched is small, not almost done).
export function texts({ name, where, open, change, since, top, date }) {
  const place = where ? `${name}, ${where}` : name;
  const quests = (n) => (n === 1 ? "quest" : "quests");
  let title;
  if (open === 0) title = `No open StreetComplete quests in ${place}`;
  else if (open < 50 && change && change.open < 0) title = `Almost done: ${nf.format(open)} StreetComplete ${quests(open)} left in ${place}`;
  else title = `${nf.format(open)} open StreetComplete ${quests(open)} in ${place}`;
  const out = [];
  if (change) {
    const span = since ? `since ${shortDate(since)}` : "in the last 4 weeks";
    const d = change.open;
    if (d < 0) out.push(`Down ${nf.format(-d)} ${span}.`);
    else if (d > 0) out.push(`Up ${nf.format(d)} ${span}${change.aged != null && change.aged > d / 2 ? ", mostly resurveys coming due" : ""}.`);
    else out.push(`No change ${span}.`);
  }
  if (top.length) out.push(`Most open: ${top.map((t) => `${questWords(t.name)} ${nf.format(t.open)}`).join(", ")}.`);
  out.push(`As of ${shortDate(date)}, ${date.slice(0, 4)}.`);
  return { title, description: out.join(" ") };
}

// A country as the page names it (app.js cldrCountry): CLDR's English name, Palestine by its short form.
export function countryName(cc) {
  try {
    const n = new Intl.DisplayNames(["en"], { type: "region", style: cc === "PS" ? "short" : "long" }).of(cc);
    return n && n !== cc ? n : null;
  } catch { return null; }
}

// A place's row in its name-layer file (places/<in>.json), with the rows it indexes; null when absent.
function shardRow(shard, id) {
  const rows = (shard && shard.places) || [];
  const row = rows.find((r) => r[R.id] === id);
  return row ? { row, rows } : null;
}

// A world place's name and the place it is in, from its row: the English name where the layer has one,
// as the page shows it, and its parent's.
export function namesFromRow({ row, rows }) {
  const parent = Number.isInteger(row[R.parent]) && row[R.parent] >= 0 ? rows[row[R.parent]] : null;
  return { name: row[R.en] || row[R.name], where: parent ? parent[R.en] || parent[R.name] : null };
}

// The preview of a link, or null when the link names no place the site has numbers for (the page then
// keeps its own head). load: registry() -> [{name, defaultDisabled, status}]; site(path) and world(path) -> the
// JSON at that path of the site and of the world host, null when it is not there.
export async function previewFor(ask, params, load) {
  if (!ask) return null;
  const registry = await load.registry();
  if (!registry) return null;
  const sel = selectionFrom(params, registry);
  let found = null;
  if (ask.kind === "city") found = await cityPlace(ask.city, ask.part, load);
  else {
    // A counted city or part under its place id is rewritten to ?city= by the page, so the daily count is
    // its number: the name layer's row says which ("toronto", "toronto/<part>"), and without ?in= the
    // cities' own place ids do.
    const at = shardRow(ask.placeIn ? await load.site(`places/${ask.placeIn}.json`) : null, ask.place);
    let counted = at && typeof at.row[R.counted] === "string" && COUNTED.test(at.row[R.counted]) ? at.row[R.counted] : "";
    if (!counted) {
      const cities = await load.site("data/cities.json");
      const c = cities && (cities.cities || []).find((x) => x.place === ask.place);
      if (c && CITY_ID.test(c.id)) counted = c.id;
    }
    if (counted) found = await cityPlace(counted.split("/")[0], counted.split("/")[1] || "", load);
    if (!found || !found.series) found = await worldPlace(ask, at, load);
  }
  if (!found || !found.series) return null;
  const { open, change, top } = summarize(found.series.pairs, sel);
  if (open == null) return null;
  return texts({ name: found.name, where: found.where, open, change, since: found.series.since, top, date: found.series.date });
}

// A world file's days in the shape of a city's series (app.js worldSeries), over `names`: the days from the
// file's `from` through latest.date, a quest null before latest.questsFrom's day for it. Null when the
// place was first counted after latest.date.
export function worldSeries(latest, pf, names) {
  const last = Math.round((dayTs(latest.date) - dayTs(latest.first)) / 86400);
  const from = Number.isInteger(pf.from) && pf.from > 0 ? pf.from : 0;
  if (!(last >= from)) return null;
  const days = Array.from({ length: last - from + 1 }, (_, k) => from + k);
  const quests = {};
  for (const q of new Set(names)) {
    const since = (latest.questsFrom || {})[q] || 0;
    const at = days.map((k) => (k < since ? [null, null] : pointAt((pf.quests || {})[q], k)));
    quests[q] = { open: at.map((v) => v[0]), agedOnly: at.map((v) => v[1]) };
  }
  return { dates: days.map((k) => addDays(latest.first, k)), quests };
}

// A city's file before the world's first day, the world's days from it on (app.js joinWorld); a quest only
// one of them counts is null on the other's days.
export function joinWorld(h, w) {
  const k = h.dates.findIndex((d) => d >= w.dates[0]), n = k < 0 ? h.dates.length : k;
  const none = (len) => Array(len).fill(null);
  const join = (a, b) => [...(a ? a.slice(0, n) : none(n)), ...(b || none(w.dates.length))];
  const quests = {};
  for (const q of new Set([...Object.keys(h.quests || {}), ...Object.keys(w.quests)])) {
    const a = (h.quests || {})[q] || {}, b = w.quests[q] || {};
    const s = { open: join(a.open, b.open), agedOnly: join(a.agedOnly, b.agedOnly) };
    if (!s.open.every((v) => v == null)) quests[q] = s;
  }
  return { ...h, dates: join(h.dates, w.dates), quests };
}

// The quests the site counts in a city (app.js countedIn): quests.json's status per city.
const countedIn = (registry, city) => registry.filter((q) => q.status && q.status[city] === "counted").map((q) => q.name);

async function worldLatest(load) {
  const latest = await load.world("latest.json");
  return worldLatestOk(latest) ? latest : null;
}

// A city: its history file joined with the world's days of it (app.js cityHistory); a part: the world's
// file of it (app.js worldPart), else its own history file (partHistory). Without the world host, the
// files alone.
async function cityPlace(city, part, load) {
  const [registry, latest] = await Promise.all([load.registry(), worldLatest(load).catch(() => null)]);
  if (!part) {
    const [h, wf] = await Promise.all([load.site(`data/history/${city}.json`),
      latest && latest.city ? load.world(`${latest.city}${city}.json?v=${encodeURIComponent(latest.v)}`).catch(() => null) : null]);
    if (!h || !Array.isArray(h.dates)) return null;
    const w = wf && wf.quests ? worldSeries(latest, wf, countedIn(registry, city)) : null;
    return { name: h.name, where: "", series: seriesPairs(w ? joinWorld(h, w) : h) };
  }
  const cities = await load.site("data/cities.json");
  const c = cities && (cities.cities || []).find((x) => x.id === city);
  const where = c ? c.name : "";
  if (latest && latest.cityParts) {
    const v = encodeURIComponent(latest.v);
    const [pf, kids, partNames] = await Promise.all([
      load.world(`${latest.place}${part.slice(0, 2)}/${part}.json?v=${v}`).catch(() => null),
      load.world(`${latest.cityParts}${city}.json?v=${v}`).catch(() => null),
      load.site(`data/parts/${city}.json`)]);
    const p = partNames && (partNames.parts || []).find((x) => x.id === part);
    const f = pf || (kids && (kids.noFile || []).includes(part) ? { quests: {} } : null);
    const s = p && f && c ? worldSeries(latest, f, countedIn(registry, city)) : null;
    if (s) return { name: p.en || p.name, where, series: seriesPairs(s) };
  }
  const p = await load.site(`data/history/${city}/${part}.json`);
  if (!p) return null;
  return { name: p.en || p.name, where, series: seriesPairs(p) };
}

async function worldPlace(ask, at, load) {
  const latest = await load.world("latest.json");
  if (!worldLatestOk(latest)) return null;
  const pf = await load.world(`${latest.place}${ask.place.slice(0, 2)}/${ask.place}.json?v=${encodeURIComponent(latest.v)}`);
  if (!pf || !pf.quests) return null;
  const named = at ? namesFromRow(at) : { name: pf.name, where: null };
  const country = pf.subtype === "country" ? null : countryName((pf.cc || "").toUpperCase());
  return { name: named.name, where: named.where || country || "", series: worldPairs(latest, pf) };
}
