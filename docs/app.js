// sc-open-quests site. Reads the JSON described in DATA-FORMAT.md; no build step.
// ?data=<path> points it at another data directory (the test fixtures use this).
"use strict";

const DATA = (new URLSearchParams(location.search).get("data") || "data").replace(/\/$/, "");
// Every other place's numbers, from the world's daily count (DESIGN.md, "World places published: stable paths
// (schema 2)"); ?world=<url> points it at another folder, relative allowed (the test fixture uses this). With
// WORLD_HOST "" the page asks nothing of the world unless ?world= is given.
const WORLD_HOST = "https://sc-data.comentality.com/";
const WORLD = (new URLSearchParams(location.search).get("world") || WORLD_HOST).replace(/\/?$/, "/");
const MAX_PINNED = 6;
const nf = new Intl.NumberFormat("en-CA");
const nf1 = new Intl.NumberFormat("en-CA", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const nfShort = new Intl.NumberFormat("en-CA", { notation: "compact", maximumSignificantDigits: 3 });
const HOME_CITY = "guelph";                 // the first visit's city
const RECENT_KEY = "sc-open-quests-cities"; // localStorage: the reader's cities, the last first
const MAX_RECENT = 5;
const RECENT_DAYS = 90;                     // the place chart opens on this many days; "All" shows every snapshot
const WEEKS4 = 28;                          // the place's 4-week change, in days

const state = {
  view: "city",                     // "city" is the place page: a counted city, or one of its parts
  city: "",                         // from the link, else the last city seen, else HOME_CITY
  part: "",                         // the part of the city (its place id) the page shows, "" = the city itself
  range: "recent",                  // the place chart's time: "recent" (RECENT_DAYS) or "all"
  filter: "",
  selected: new Set(),              // quest names counted in the summary chart and tiles
  pinned: [],                       // quest names charted on their own, as small multiples
  questSort: { key: "open", dir: -1 },
  compareQuest: "",                 // "" = all counted quests
  compareSort: { key: "perKm2", dir: -1 },
  releases: true,                   // StreetComplete releases on the time axis
  asThen: false,                    // each quest counts only from the release that first offered it
  place: "",                        // places view: the place shown (12-hex id), "" = the list of countries
  placeIn: "",                      // its region file as "<cc>/<regionId>", the hint that finds it
  placeScope: "",                   // the country the place search looks inside ("" = names in the index)
  mapAt: "",                        // map view: "zoom/lat/lon" once the reader has moved it, "" = every city in view
};
let cities, quests, questByName;            // loaded data
let hist = null;                            // the place page's series, the city's or a part's (seriesFor)
let urlSelection = null;                    // the selection as read from the URL, resolved once quests.json is in
let icons = {};                             // quest name -> {icon, title}, from icons/index.json
let releases = [];                          // [{ts, version}], stable SC releases, oldest first
let questFirst = {};                        // quest name -> {version, date}, from quest-releases.json
const compareCache = new Map();             // quest name -> promise of compare/<quest>.json
const charts = [];                          // live uPlot instances, for resize

// ---------- small helpers ----------

const $ = (sel) => document.querySelector(sel);

function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid != null) e.append(kid instanceof Node ? kid : String(kid));
  return e;
}

async function getJSON(path) {
  const r = await fetch(`${DATA}/${path}`, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
  return r.json();
}

function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

// "AddBenchBackrest" -> "Add bench backrest"
function humanize(name) {
  if (name === "OsmNoteQuestType") return "Answer OSM notes";
  return name.replace(/([a-z0-9])([A-Z])/g, "$1 $2").replace(/([A-Z])([A-Z][a-z])/g, "$1 $2")
    .replace(/ (\w)/g, (m, c) => " " + c.toLowerCase());
}

// The quest's title as the app asks it ("Does this bench have a backrest?"), else its class name humanized.
function questTitle(name) { return (icons[name] && icons[name].title) || humanize(name); }

function questIcon(name, cls = "q-icon") {
  const i = icons[name];
  return i && i.icon ? el("img", { class: cls, src: `icons/${i.icon}`, alt: "", loading: "lazy", width: 32, height: 32 }) : null;
}

function signed(n) { return n > 0 ? "+" + nf.format(n) : n < 0 ? "−" + nf.format(-n) : "±0"; }
// Rates: one decimal from 10 up, two significant digits below (0.012, 0.35, 4.7).
const sig2 = new Intl.NumberFormat("en-CA", { minimumSignificantDigits: 2, maximumSignificantDigits: 2 });
const nf0 = new Intl.NumberFormat("en-CA", { maximumFractionDigits: 0 });
function rate(v) { return v == null || !isFinite(v) ? "—" : (v >= 100 ? nf0 : v >= 10 ? nf1 : sig2).format(v); }
function ratio(n, d) { return n != null && d ? rate(n / d) : "—"; }
const last = (arr) => arr[arr.length - 1];

const selected = (name) => state.selected.has(name);   // does this quest count towards the totals?

// ---------- URL state ----------
// The query string holds what is on screen, so a link reproduces it: city, view, pins, the compare quest,
// and the selection as a base plus a diff: base=app (the quests the app turns on by default; the default,
// left out), none or all, then on=A,B ticked on top of it and off=C,D unticked from it. Quest class names
// are the key, so a link survives an app release: names it doesn't know are dropped, new quests follow
// the base. ?data= is kept as it is. Links from before 2026-10-21 kept the state in the hash, with q= for
// the charted quests; they are read once and rewritten.

const SEL_BASES = ["app", "none", "all"];
const names = (v) => (v || "").split(",").filter(Boolean);

function readURL() {
  const p = new URLSearchParams(location.search);
  const h = new URLSearchParams(location.hash.slice(1));
  const get = (k) => p.get(k) ?? h.get(k);
  if (get("view")) state.view = { compare: "compare", places: "places", map: "map" }[get("view")] || "city";
  if (get("city")) state.city = get("city");
  if (p.get("part")) state.part = p.get("part");
  state.range = p.get("range") === "all" ? "all" : "recent";
  state.pinned = names(p.get("pin") ?? h.get("q")).slice(0, MAX_PINNED);
  if (get("cq") != null) state.compareQuest = get("cq");
  state.releases = get("rel") !== "0";
  state.asThen = get("then") === "1";
  state.mapAt = p.get("at") || "";
  if (p.get("place")) { state.view = "places"; state.place = p.get("place"); state.placeIn = p.get("in") || ""; }
  urlSelection = { base: SEL_BASES.includes(p.get("base")) ? p.get("base") : "app", on: names(p.get("on")), off: names(p.get("off")) };
}

function baseSet(base) {
  return new Set(quests.quests.filter((q) => base === "all" || (base === "app" && !q.defaultDisabled)).map((q) => q.name));
}

function resolveSelection({ base, on, off }) {
  const s = baseSet(base);
  for (const n of on) if (questByName.has(n)) s.add(n);
  for (const n of off) s.delete(n);
  return s;
}

// The selection as base, on and off: the base whose diff names the fewest quests, in registry order so
// the same selection always gives the same link. Ties go to the default base.
function selectionParams() {
  let best = null;
  for (const base of SEL_BASES) {
    const b = baseSet(base);
    const on = quests.quests.filter((q) => selected(q.name) && !b.has(q.name)).map((q) => q.name);
    const off = quests.quests.filter((q) => !selected(q.name) && b.has(q.name)).map((q) => q.name);
    if (!best || on.length + off.length < best.on.length + best.off.length) best = { base, on, off };
  }
  return best;
}

// The query string of a view; s is the state, or a copy of it with another place in it (place links).
// A counted place is ?city=, with &part= for a part of it; any other place names itself and its region
// file only (?place=&in=), so the link stays short. A ?place= link to a counted place is rewritten to
// ?city= once the page has found it.
function queryString(s = state) {
  const p = new URLSearchParams();
  const data = new URLSearchParams(location.search).get("data");
  if (data) p.set("data", data);
  const world = new URLSearchParams(location.search).get("world");
  if (world) p.set("world", world);
  if (s.view === "places" && s.place) {
    p.set("place", s.place);
    if (s.placeIn) p.set("in", s.placeIn);
  } else if (s.view !== "city") p.set("view", s.view);
  if (s.view !== "places") p.set("city", s.city);
  if (s.view === "city" && s.part) p.set("part", s.part);
  if (s.view === "map" && s.mapAt) p.set("at", s.mapAt);
  if (s.range === "all") p.set("range", "all");
  const sel = selectionParams();
  if (sel.base !== "app") p.set("base", sel.base);
  if (sel.on.length) p.set("on", sel.on.join(","));
  if (sel.off.length) p.set("off", sel.off.join(","));
  if (state.pinned.length) p.set("pin", state.pinned.join(","));
  if (state.compareQuest) p.set("cq", state.compareQuest);
  if (!state.releases) p.set("rel", "0");
  if (state.asThen) p.set("then", "1");
  return "?" + p.toString().replace(/%2C/g, ",").replace(/%2F/g, "/");
}

function writeURL() {
  // a relative "?query" drops the hash, which is where old links kept the state
  window.history.replaceState(null, "", queryString());
}

// How the totals' subtitle names the selection.
function selectionText() {
  const n = state.selected.size, all = quests.quests.length;
  const sel = selectionParams();
  const plain = !sel.on.length && !sel.off.length;
  if (plain && sel.base === "app") return `the ${n} quest types the app turns on by default`;
  if (plain && sel.base === "all") return `all ${all} quest types, including those off by default`;
  return `the ${n} of ${all} quest types ticked in the table below`;
}

// ---------- series ----------

// With "Only quests the app had then", a quest counts from the release that first offered it. The counts
// themselves are today's rules on that date's map data. A quest the file doesn't name counts all along.
function offeredOn(name, date) {
  const f = state.asThen && questFirst[name];
  return !f || f.date <= date;
}

// Sum of the selected quests at each date. null quest values count as absent, not 0,
// but a date where every quest is null stays null.
function totalSeries(h) {
  const n = h.dates.length, open = Array(n).fill(null), aged = Array(n).fill(null);
  for (const [name, s] of Object.entries(h.quests)) {
    if (!selected(name)) continue;
    for (let i = 0; i < n; i++) {
      if (!offeredOn(name, h.dates[i])) continue;
      if (s.open[i] != null) open[i] = (open[i] || 0) + s.open[i];
      if (s.agedOnly[i] != null) aged[i] = (aged[i] || 0) + s.agedOnly[i];
    }
  }
  return { open, aged };
}

function questSeries(h, name) {
  const s = h.quests[name];
  if (!s) return null;
  const shown = (v) => v.map((x, i) => (offeredOn(name, h.dates[i]) ? x : null));
  return { open: shown(s.open), aged: shown(s.agedOnly) };
}

// The steps of the switch: the dates selected quests first count at, the largest few, oldest first.
// A step is what the arriving quests hold at that date; the rest of the total moves as it would anyway.
function arrivals(h, limit = 5) {
  const at = new Map();
  for (const [name, s] of Object.entries(h.quests)) {
    const f = questFirst[name];
    if (!f || !selected(name) || f.date <= h.dates[0]) continue;
    const i = h.dates.findIndex((d) => d >= f.date);
    if (i < 0 || !s.open[i]) continue;
    if (!at.has(i)) at.set(i, []);
    at.get(i).push({ name, open: s.open[i], ...f });
  }
  return [...at].map(([i, qs]) => ({ i, date: h.dates[i], qs: qs.sort((a, b) => b.open - a.open), open: qs.reduce((t, q) => t + q.open, 0) }))
    .sort((a, b) => b.open - a.open).slice(0, limit).sort((a, b) => a.i - b.i);
}

// By the quest's name, not the app's title: "What's the surface here?" could be any of six quests.
function arrivalText({ date, qs, open }) {
  const more = qs.length - 1;
  const byDate = [...qs].sort((a, b) => a.date.localeCompare(b.date));
  const from = byDate[0].version, to = last(byDate).version;
  return `↑ ${date}: ${signed(open)} from ${humanize(qs[0].name).replace(/^Add /, "").toLowerCase()}` + (more ? ` and ${more} more` : "") +
    (from === to ? `, new in ${from}` : `, new in ${from} to ${to}`);
}

// Names of the selected quests that have a value at date index i.
function selectedQuestsAt(h, i) {
  return new Set(Object.entries(h.quests)
    .filter(([name, s]) => s.open[i] != null && selected(name)).map(([name]) => name));
}

// Change in the total from date j to i, over the selected quests counted on both dates only: the open
// count, and the part of it that aged (null where a date has no aged split). Null when no quest is on both.
function likeForLike(h, j, i) {
  let open = 0, aged = 0, any = false, agedKnown = true;
  for (const [name, s] of Object.entries(h.quests)) {
    if (!selected(name) || s.open[i] == null || s.open[j] == null) continue;
    open += s.open[i] - s.open[j];
    if (s.agedOnly[i] == null || s.agedOnly[j] == null) agedKnown = false;
    else aged += s.agedOnly[i] - s.agedOnly[j];
    any = true;
  }
  return any ? { open, aged: agedKnown ? aged : null } : null;
}
const likeForLikeDelta = (h, i) => likeForLike(h, i - 1, i)?.open ?? null;

const daysBetween = (a, b) => Math.round((dayTs(b) - dayTs(a)) / 86400);
const shortDate = (d) => new Date(dayTs(d) * 1e3).toLocaleDateString("en-CA", { month: "short", day: "numeric", timeZone: "UTC" });
const monthYear = (d) => new Date(dayTs(d) * 1e3).toLocaleDateString("en-CA", { month: "short", year: "numeric", timeZone: "UTC" });
function addDays(d, n) { return new Date((dayTs(d) + n * 86400) * 1e3).toISOString().slice(0, 10); }

// The series from date `from` on: every array cut alike, so the chart, its sparklines, legend and breaks
// agree on what is shown.
function sliceSeries(h, from) {
  const k = h.dates.findIndex((d) => d >= from);
  if (k <= 0) return h;
  const cut = (a) => (Array.isArray(a) ? a.slice(k) : a);
  return { ...h, dates: h.dates.slice(k), meta: h.meta.slice(k),
           quests: Object.fromEntries(Object.entries(h.quests).map(([q, s]) => [q, { open: cut(s.open), agedOnly: cut(s.agedOnly) }])) };
}

// Does the series reach back further than the recent window? Only then is there a choice of range.
const longerThanRecent = (h) => h.dates.length > 1 && daysBetween(h.dates[0], last(h.dates)) > RECENT_DAYS;
const shownSeries = (h) => (state.range === "all" || !longerThanRecent(h) ? h : sliceSeries(h, addDays(last(h.dates), -RECENT_DAYS)));

// A city's series, once a page: history/<city>.json.
const cityHistCache = new Map();
function cityHistory(id) {
  if (!cityHistCache.has(id)) {
    const p = getJSON(`history/${id}.json`);
    p.catch(() => cityHistCache.delete(id));
    cityHistCache.set(id, p);
  }
  return cityHistCache.get(id);
}

// A part's series (DATA-FORMAT.md, "A part's series") in the shape of its city's: the city's meta on the
// same dates, so version breaks show here too, and every quest the city has, a quest the part file leaves
// out (nothing ever open in the part) 0 wherever the city counted it and null where it did not. Null
// when the part has no published series yet.
async function partHistory(cityId, pid) {
  const [city, part] = await Promise.all([cityHistory(cityId),
    optionalJSON(`${DATA}/history/${encodeURIComponent(cityId)}/${encodeURIComponent(pid)}.json`)]);
  if (!part || !part.dates || !part.dates.length) return null;
  const at = new Map(city.dates.map((d, i) => [d, i]));
  const idx = part.dates.map((d) => at.get(d));
  const quests = {};
  for (const [q, cs] of Object.entries(city.quests)) {
    quests[q] = part.quests[q] || {
      open: idx.map((i) => (i == null || cs.open[i] == null ? null : 0)),
      agedOnly: idx.map((i) => (i == null || cs.agedOnly[i] == null ? null : 0)),
    };
  }
  for (const [q, s] of Object.entries(part.quests)) quests[q] ||= s;
  return { city: cityId, part: pid, name: part.en || part.name, subtype: part.subtype, in: part.in || null,
           cityName: city.name, dates: part.dates, meta: idx.map((i) => (i == null ? {} : city.meta[i])), quests };
}

// The page's series: the city's, or the part's.
async function seriesFor(cityId, pid) {
  if (!pid) return cityHistory(cityId);
  return partHistory(cityId, pid);
}

// Steps worth a note on the chart: one quest type moving by more than a tenth of the total (and at least
// STEP_MIN) between two counts. Imports and bulk edits do this; players solving quests rarely do. A run of
// such steps in the same quest and direction, a count apart, is one note. The largest few, oldest first.
// What a step is said to be comes from KNOWN_STEPS only; a found step states its size and quest.
const STEP_MIN = 500, STEP_SHARE = 0.1, STEP_NOTES = 4;
const KNOWN_STEPS = {
  // confirmed by the owner (HANDOFF, "Deeper history"); the 2019 rise in Toronto is not confirmed
  toronto: [{ quest: "AddHousenumber", date: "2026-06-01", text: "an address import into OpenStreetMap" }],
};
function steps(h, tot) {
  const found = [];
  for (const [name, s] of Object.entries(h.quests)) {
    if (!selected(name)) continue;
    for (let i = 1; i < h.dates.length; i++) {
      if (s.open[i] == null || s.open[i - 1] == null || !offeredOn(name, h.dates[i - 1])) continue;
      const d = s.open[i] - s.open[i - 1];
      if (Math.abs(d) < STEP_MIN || Math.abs(d) < STEP_SHARE * (tot.open[i - 1] || 0)) continue;
      const prev = found.find((f) => f.name === name && f.j === i - 1 && Math.sign(f.d) === Math.sign(d));
      if (prev) { prev.j = i; prev.d += d; } else found.push({ name, i0: i - 1, i, j: i, d });
    }
  }
  const known = h.part ? [] : KNOWN_STEPS[h.city] || [];
  return found.sort((a, b) => Math.abs(b.d) - Math.abs(a.d)).slice(0, STEP_NOTES).sort((a, b) => a.i - b.i)
    .map((f) => ({ ...f, from: h.dates[f.i0], to: h.dates[f.j],
                   known: known.find((k) => k.quest === f.name && k.date > h.dates[f.i0] && k.date <= h.dates[f.j]) }));
}
const stepShort = (f) => `${f.d > 0 ? "+" : "−"}${nfShort.format(Math.abs(f.d))}`;
function stepText(f) {
  const span = f.j - f.i0 > 1 ? `from ${monthYear(f.from)} to ${monthYear(f.to)}` : `between ${f.from} and ${f.to}`;
  return `◆ ${signed(f.d)} ${humanize(f.name).replace(/^Add /, "").toLowerCase()} quests ${span}` +
    (f.known ? `: ${f.known.text}.` : ".");
}

// Indices where the SC version, resurvey multiplier, area unit or notes modelling differs from the previous date. With
// questSet, also where the set of selected quests changes (a quest type counted for the first
// time, e.g. a newly ported custom quest), which moves a total but not a single quest's line.
function breaks(h, { questSet = false } = {}) {
  const out = [];
  for (let i = 1; i < h.dates.length; i++) {
    const a = h.meta[i - 1] || {}, b = h.meta[i] || {};
    const what = [], short = [];
    if (questSet) {
      const before = selectedQuestsAt(h, i - 1), now = selectedQuestsAt(h, i);
      const added = [...now].filter((q) => !before.has(q)).length;
      const dropped = [...before].filter((q) => !now.has(q)).length;
      if (added) { what.push(`${added} more quest type${added > 1 ? "s" : ""} counted`); short.push(`+${added} types`); }
      if (dropped) { what.push(`${dropped} quest type${dropped > 1 ? "s" : ""} no longer counted`); short.push(`−${dropped} types`); }
    }
    if (a.scVersion !== b.scVersion) {
      what.push(`StreetComplete ${a.scVersion} → ${b.scVersion}`);
      short.push(b.scVersion);
    }
    if (a.resurveyMultiplier !== b.resurveyMultiplier) {
      what.push(`resurvey ×${a.resurveyMultiplier} → ×${b.resurveyMultiplier}`);
      short.push(`×${b.resurveyMultiplier}`);
    }
    // absent on snapshots that held no area quests, so only a change between two set values counts
    if (a.areaUnit && b.areaUnit && a.areaUnit !== b.areaUnit) {
      what.push(`area quests per ${a.areaUnit} → per ${b.areaUnit}`);
      short.push(b.areaUnit);
    }
    // with notes, quests on an open note's position are hidden, as in the app
    if (!!a.notes !== !!b.notes) {
      what.push(b.notes ? "open notes now hide the quests at their position" : "open notes no longer modelled");
      short.push(b.notes ? "notes" : "no notes");
    }
    if (what.length) out.push({ i, date: h.dates[i], label: what.join(", "), short: short.join(" ") });
  }
  return out;
}

// ---------- chart ----------

function dayTs(d) { return Date.UTC(+d.slice(0, 4), +d.slice(5, 7) - 1, +d.slice(8, 10)) / 1000; }

// The first release of each major number: v5.0, but also v1.2 and v3.2 where SC skipped the .0.
const majorOf = (v) => v.match(/^v?(\d+)/)?.[1];
const isMajor = (r, i, all) => i === 0 || majorOf(all[i - 1].version) !== majorOf(r.version);

// StreetComplete major releases as faint, unlabelled vertical lines through the plot. While the pointer
// is on a date, the release current on that date (the last one at or before it, so the line to the
// pointer's left), minor or major, is drawn solid and named in note, below the chart.
function releaseLayer(xs, { note = null, idle = true } = {}) {
  const rel = state.releases ? releases.filter((r) => r.ts >= xs[0] - 86400 && r.ts <= last(xs) + 86400) : [];
  let hover = null, hoverTs = null;
  const day = (ts) => new Date(ts * 1e3).toISOString().slice(0, 10);
  const describe = (r, ts) => `StreetComplete <b>${r.version}</b> was the current release on ${day(ts)}` +
    (r.ts === ts ? "; it came out that day." : `, out since ${day(r.ts)}.`);
  const idleText = rel.length && idle
    ? "The faint vertical lines are StreetComplete major releases" +
      "; move along the chart to see which was current. " + (state.asThen
        ? `Quests join at the first date on or after their release, and every count uses the rules of v${cities.scVersion}.`
        : `Every count here uses the quests of v${cities.scVersion}, whatever the date.`)
    : "";
  if (note) note.innerHTML = idleText;
  return {
    draw(u) {
      if (!rel.length) return;
      const ctx = u.ctx, dpr = devicePixelRatio, { left, top, width, height } = u.bbox;
      const line = (r) => {
        const x = Math.round(u.valToPos(r.ts, "x", true)) + 0.5;   // on a pixel, so 1px stays crisp
        if (x < left || x > left + width) return;
        ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, top + height); ctx.stroke();
      };
      ctx.save();
      ctx.strokeStyle = css("--release");
      ctx.lineWidth = dpr;
      ctx.globalAlpha = 0.28;
      for (const r of rel) if (r.major && r !== hover) line(r);
      if (hover) { ctx.globalAlpha = 1; ctx.lineWidth = 1.5 * dpr; line(hover); }
      ctx.restore();
    },
    cursor(u) {
      if (!rel.length) return;
      const idx = u.cursor.idx;
      const ts = idx == null ? null : xs[idx];
      let cur = null;
      if (ts != null) for (const r of releases) { if (r.ts <= ts) cur = r; else break; }
      if (cur === hover && ts === hoverTs) return;
      const redraw = cur !== hover;
      hover = cur;
      hoverTs = ts;
      if (note) note.innerHTML = hover ? describe(hover, ts) : idleText;
      if (redraw) u.redraw(false);
    },
  };
}

function lineChart(target, h, series, { height = 260, showAged = true, questSetBreaks = false, note = null, noteIdle = true, marks = [] } = {}) {
  const xs = h.dates.map(dayTs);
  const mapping = series.open.map((v, i) => (v == null ? null : v - (series.aged[i] || 0)));
  const brk = breaks(h, { questSet: questSetBreaks });
  const few = xs.length <= 60;
  // Over a year or more, label months with their year and leave days out.
  const long = xs.length > 1 && xs[xs.length - 1] - xs[0] > 300 * 86400;
  const tickFmt = long ? { month: "short", year: "numeric", timeZone: "UTC" } : { month: "short", day: "numeric", timeZone: "UTC" };
  const surface = css("--surface");
  const rel = releaseLayer(xs, { note, idle: noteIdle });
  let idle = true;   // the legend reads out the latest snapshot, not the pointer
  const mk = (label, color, data) => ({
    label, stroke: color, width: 2, value: (u, v) => (v == null ? "—" : nf.format(v)),
    points: { show: few, size: 8, width: 2, stroke: color, fill: color },
    spanGaps: false, _data: data,
  });
  const ser = [{ ...mk("Needs mapping", css("--series-1"), mapping), fill: css("--wash") }];
  if (showAged) ser.push(mk("Aged, needs resurvey", css("--series-2"), series.aged));
  const axis = { stroke: css("--muted"), grid: { stroke: css("--grid"), width: 1 },
                 ticks: { stroke: css("--axis"), width: 1, size: 4 }, font: "12px Roboto, system-ui, sans-serif" };
  const opts = {
    width: Math.max(280, target.clientWidth),
    height,
    tzDate: (ts) => uPlot.tzDate(new Date(ts * 1e3), "Etc/UTC"),
    // every chart on the page follows the pointer on any one of them: same date, all charts at once
    cursor: { points: { size: 10, width: 2, fill: surface }, drag: { x: false, y: false },
              sync: { key: "city", setSeries: false } },
    scales: {
      // one snapshot: centre it in a week instead of letting the scale collapse
      x: xs.length === 1 ? { time: true, auto: false, range: [xs[0] - 3 * 86400, xs[0] + 3 * 86400] } : { time: true },
      y: { range: (u, min, max) => [0, max > 0 ? max * 1.12 : 10] },
    },
    axes: [
      { ...axis, values: (u, ticks) => ticks.map((t) => {
          const d = new Date(t * 1e3);
          return d.getUTCHours() || (long && d.getUTCDate() !== 1) ? "" : d.toLocaleDateString("en-CA", tickFmt);
        }) },
      { ...axis, size: 60, values: (u, ticks) => ticks.map((t) => nf.format(t)) },
    ],
    legend: { live: true },
    series: [{ label: "Date", value: (u, ts) => (ts == null ? "—" : new Date(ts * 1e3).toISOString().slice(0, 10)) },
             ...ser.map(({ _data, ...s }) => s)],
    hooks: {
      // With no pointer over the plot, the legend reads out the latest snapshot.
      ready: [(u) => u.setLegend({ idx: xs.length - 1 })],
      // uPlot places the hover rings only when the index changes, and the idle legend already holds the
      // last one, so a pointer arriving on the latest snapshot would get its line without rings. Clearing
      // the legend and placing the cursor again, quietly, makes it a change.
      setCursor: [(u) => {
        const i = u.cursor.idx;
        if (i == null) { u.setLegend({ idx: xs.length - 1 }); idle = true; }
        else if (idle) {
          idle = false;
          if (i === xs.length - 1) { u.setLegend({ idx: null }); u.setCursor({ left: u.cursor.left, top: u.cursor.top }, false, false); }
        }
        rel.cursor(u);
      }],
      draw: [(u) => {
        rel.draw(u);
        if (marks.length) {   // steps: a faint band over the counts they span, the size at its top
          const ctx = u.ctx, { left, top, width, height: ph } = u.bbox, dpr = devicePixelRatio;
          ctx.save();
          ctx.font = `${11 * dpr}px Roboto, system-ui, sans-serif`;
          ctx.textBaseline = "alphabetic";
          for (const f of marks) {
            const x0 = Math.round(u.valToPos(xs[f.i0], "x", true)), x1 = Math.max(x0 + 2 * dpr, Math.round(u.valToPos(xs[f.j], "x", true)));
            ctx.globalAlpha = 0.12;
            ctx.fillStyle = css("--series-2");
            ctx.fillRect(x0, top, x1 - x0, ph);
            ctx.globalAlpha = 1;
            ctx.fillStyle = css("--ink-2");
            const label = "◆ " + stepShort(f), w = ctx.measureText(label).width;
            ctx.textAlign = "left";
            ctx.fillText(label, x1 + 3 * dpr + w <= left + width ? x1 + 3 * dpr : x0 - 3 * dpr - w, top + 24 * dpr);
          }
          ctx.restore();
        }
        if (!brk.length) return;
        const ctx = u.ctx, { top, height: ph } = u.bbox, dpr = devicePixelRatio;
        const y0 = top;
        ctx.save();
        ctx.strokeStyle = css("--ink-2");
        ctx.fillStyle = css("--ink-2");
        ctx.lineWidth = dpr;
        ctx.font = `${11 * dpr}px Roboto, system-ui, sans-serif`;
        ctx.textAlign = "left";
        ctx.textBaseline = "alphabetic";
        for (const b of brk) {
          const x = Math.round(u.valToPos(xs[b.i] - 43200, "x", true));   // half a day before the new run
          ctx.beginPath(); ctx.moveTo(x, y0); ctx.lineTo(x, top + ph); ctx.stroke();
          // near the right edge, the label goes to the left of its line
          const w = ctx.measureText(" " + b.short).width;
          const right = x + 2 + w <= u.bbox.left + u.bbox.width;
          ctx.fillText(" " + b.short, right ? x + 2 : x - 4 * dpr - w, y0 + 10 * dpr);
        }
        ctx.restore();
      }],
    },
  };
  target.replaceChildren();
  const u = new uPlot(opts, [xs, ...ser.map((s) => s._data)], target);
  charts.push({ u, target });
  return u;
}

// The first and last points sit on the plot's very edges, where a pixel or two holds them (the latest
// days of daily counts crowd into the last few). Level with the plot, the white beside it, out to the
// card's edges, stands for those ends: the pointer over the y-axis or the card's left padding reads out
// the first snapshot, past the plot's right edge the last. uPlot only follows the pointer over the plot
// itself, so this moves its cursor by hand, synced to the other charts like a hover is. One listener for
// the page, since a redraw replaces the charts; it finds the chart by the card the pointer is in.
let edgeChart = null;   // the chart whose cursor this put on an end
function edgeHover(e) {
  const card = e.target.closest?.(".card");
  const c = card && charts.find(({ target }) => card.contains(target));
  if (c && c.u.over.contains(e.target)) { edgeChart = null; return; }   // uPlot's own ground
  let hit = null, left, top;
  if (c) {
    const r = c.u.over.getBoundingClientRect(), xs = c.u.data[0];
    if (e.clientY >= r.top && e.clientY < r.bottom && (e.clientX < r.left || e.clientX >= r.right)) {
      hit = c.u;
      left = hit.valToPos(e.clientX < r.left ? xs[0] : last(xs), "x");
      top = e.clientY - r.top;
    }
  }
  if (edgeChart && edgeChart !== hit && charts.some(({ u }) => u === edgeChart))
    edgeChart.setCursor({ left: -10, top: -10 }, true, true);
  edgeChart = hit;
  if (hit) hit.setCursor({ left, top }, true, true);
}
document.addEventListener("mousemove", edgeHover);
document.documentElement.addEventListener("mouseleave", () => edgeHover({ target: document.body }));

// A row's trend: an inline SVG line over time (x by date, not index, since monthly history runs into
// daily counts), scaled to its own min and max because the Open column carries the size. Nulls break
// the line. The latest value gets a dot.
const SVG = "http://www.w3.org/2000/svg";
function sparkline(dates, values, label) {
  const W = 96, H = 24, PAD = 3;
  const pts = dates.map((d, i) => [dayTs(d), values[i]]).filter(([, v]) => v != null);
  if (pts.length < 2) return null;
  const t0 = pts[0][0], t1 = last(pts)[0];
  let lo = Infinity, hi = -Infinity;
  for (const [, v] of pts) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
  const x = (t) => PAD + ((t - t0) / (t1 - t0 || 1)) * (W - 2 * PAD);
  const y = (v) => (hi === lo ? H / 2 : PAD + (1 - (v - lo) / (hi - lo)) * (H - 2 * PAD));
  let d = "", pen = false;
  for (let i = 0; i < dates.length; i++) {
    const v = values[i];
    if (v == null) { pen = false; continue; }
    d += `${pen ? "L" : "M"}${x(dayTs(dates[i])).toFixed(1)},${y(v).toFixed(1)}`;
    pen = true;
  }
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("class", "spark");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("width", W);
  svg.setAttribute("height", H);
  svg.setAttribute("role", "img");
  const first = pts[0][1], now = last(pts)[1];
  const text = `${label}: ${nf.format(first)} on ${dates[values.findIndex((v) => v != null)]}, ` +
    `${nf.format(now)} now (low ${nf.format(lo)}, high ${nf.format(hi)})`;
  svg.setAttribute("aria-label", text);
  const title = document.createElementNS(SVG, "title");
  title.textContent = text;
  const path = document.createElementNS(SVG, "path");
  path.setAttribute("d", d);
  const dot = document.createElementNS(SVG, "circle");
  dot.setAttribute("cx", x(t1).toFixed(1));
  dot.setAttribute("cy", y(now).toFixed(1));
  dot.setAttribute("r", 2.5);
  svg.append(title, path, dot);
  return svg;
}

window.addEventListener("resize", () => {
  for (const { u, target } of charts) if (target.isConnected) u.setSize({ width: Math.max(280, target.clientWidth), height: u.height });
});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => render());

// ---------- city view ----------

function tile(label, value, extra, hero = false) {
  return el("div", { class: "tile" + (hero ? " hero" : "") },
    el("div", { class: "label" }, label), el("div", { class: "value" }, value), extra);
}

// The net change in words: edits, aging and new map data together, since the site cannot count solves.
function changeWords(d, from, to) {
  const when = daysBetween(from, to) === 1 ? "the day before" : `on ${shortDate(from)}`;   // the count's day, not the reader's
  return d === 0 ? `The same as ${when}` : `${nf.format(Math.abs(d))} ${d < 0 ? "fewer" : "more"} than ${when}`;
}

function renderTiles(h, tot) {
  const n = h.dates.length, i = n - 1;
  const open = tot.open[i], aged = tot.aged[i] || 0;
  const change = n > 1 ? likeForLikeDelta(h, i) : null;
  const sameSet = n > 1 && !breaks(h, { questSet: true }).some((b) => b.i === i && /types/.test(b.short));
  const delta = change != null && open != null
    ? el("div", { class: "delta" + (change < 0 ? " down" : change > 0 ? " up" : "") }, changeWords(change, h.dates[i - 1], h.dates[i]) +
      (sameSet ? "" : ", over the same quest types"))
    : el("div", { class: "note" }, "First count, no change yet");
  // 4 weeks back, or the first count when the series is younger (a part's starts 2026-10-27)
  let j = -1;
  for (let k = 0; k < i; k++) if (h.dates[k] <= addDays(h.dates[i], -WEEKS4)) j = k;
  const young = j < 0;
  if (young) j = 0;
  const w = n > 1 ? likeForLike(h, j, i) : null;
  const across = breaks(h).some((b) => b.i > j && b.i <= i);   // a new app version inside the span
  const key = (v) => el("span", { class: "key", style: `background:${css(v)}` });
  const weeks = w
    ? tile(young ? `Since ${shortDate(h.dates[j])}` : "Last 4 weeks", signed(w.open),
        el("div", { class: "note" }, w.aged == null ? "net change, aged split not counted then"
          : [key("--series-1"), `mapping ${signed(w.open - w.aged)} `, key("--series-2"), `resurvey ${signed(w.aged)}`],
          across ? el("div", {}, "across an app release, see below the chart") : null))
    : tile("Last 4 weeks", "—", el("div", { class: "note" }, "one count so far"));
  let top = null;
  for (const [name, s] of Object.entries(h.quests))
    if (selected(name) && offeredOn(name, h.dates[i]) && s.open[i] && (!top || s.open[i] > top.open)) top = { name, open: s.open[i] };
  $("#tiles").replaceChildren(
    tile("Open quests", open == null ? "—" : nf.format(open), delta, true),
    tile("Need mapping", open == null ? "—" : nf.format(open - aged),
      el("div", { class: "note" }, key("--series-1"), "tags still missing")),
    tile("Aged, need resurvey", nf.format(aged),
      el("div", { class: "note" }, key("--series-2"), open ? `${Math.round((100 * aged) / open)}% of open` : "")),
    weeks,
    top ? tile("Most open", nf.format(top.open), el("div", { class: "note top-quest" }, questIcon(top.name, "q-icon sm"), questTitle(top.name)))
        : tile("Most open", "—", el("div", { class: "note" }, "nothing open")),
  );
}

function renderCityCharts(full) {
  for (const { u } of charts) u.destroy();
  charts.length = 0;
  renderTiles(full, totalSeries(full));
  const h = shownSeries(full);
  const tot = totalSeries(h);
  const marks = steps(h, tot);
  const long = longerThanRecent(full);
  $("#chart-title").textContent = `Open quests over time in ${full.name}`;
  $("#range").hidden = !long;
  for (const b of document.querySelectorAll("#range button")) {
    b.setAttribute("aria-pressed", String(b.dataset.range === state.range));
    if (b.dataset.range === "all") b.textContent = `All since ${full.dates[0].slice(0, 4)}`;
  }
  $("#chart-sub").textContent = `Counting ${selectionText()}. ` +
    (h.dates.length === 1 ? "One count so far; the line starts here." :
      h !== full ? `The last ${RECENT_DAYS} days, ${h.dates.length} counts.` :
      `${h.dates.length} counts since ${h.dates[0]}` + (full.part && !long ? "; neighbourhoods are counted daily from 2026-10-27." : ".")) +
    (state.asThen ? " Each quest counts from the release that first offered it, by today's rules. Quests since removed from the app are not in these counts." : "");
  lineChart($("#chart-total"), h, tot, { height: 300, questSetBreaks: true, note: $("#release-note"), marks });
  $("#breaks").replaceChildren(...breaks(h, { questSet: true }).map((b) => el("li", {}, `│ ${b.date}: ${b.label}. Totals on either side are not directly comparable.`)),
    ...marks.map((f) => el("li", {}, stepText(f))),
    ...(marks.some((f) => !f.known) ? [el("li", {}, "◆ marks one quest type moving by a tenth of the total or more between two counts.")] : []));
  $("#arrivals").replaceChildren(...(state.asThen ? arrivals(h) : []).map((a) => el("li", {}, arrivalText(a))));

  const box = $("#multiples");
  box.replaceChildren();
  for (const qn of state.pinned) {
    const q = questByName.get(qn), s = questSeries(h, qn);
    const target = el("div", { class: "chart" });
    const note = el("p", { class: "hover-note", "aria-live": "polite" });
    const card = el("article", { class: "card" },
      el("h3", {}, questIcon(qn, "q-icon lg"), el("span", { class: "q-title" }, questTitle(qn)),
        el("button", { type: "button", title: "Unpin", "aria-label": `Unpin ${questTitle(qn)}`,
                       onclick: () => togglePin(qn) }, "×")),
      el("p", { class: "sub" }, s ? (q && q.usesAge ? "Mapping and aged series." : "This quest has no resurvey age, so nothing ages into it.")
                                  : "Not counted here."),
      target, s ? note : null);
    box.append(card);
    if (s) lineChart(target, h, s, { height: 190, showAged: !!(q && q.usesAge), note, noteIdle: false });
  }
}

// Uncounted rows sink below the counted ones, one group per reason, each under its own heading.
const GROUPS = {
  missing: { rank: 1, head: () => "No count in the latest run" },          // counted per quests.json, but absent from this city's snapshot
  "not-in-region": { rank: 2, head: (h) => `Not offered in ${h.name}` },   // enabledInCountries leaves this city out
  unsupported: { rank: 3, head: () => "Not counted yet" },                 // custom logic this site doesn't model yet
};

const regionNames = new Intl.DisplayNames(["en"], { type: "region" });
function countryName(code) {   // "US-OR" -> "United States (OR)"
  const [c, sub] = code.split("-");
  let n;
  try { n = regionNames.of(c) || c; } catch { n = c; }
  return sub ? `${n} (${sub})` : n;
}

// Where the app offers a quest, for the city it is missing from: short for a chip, in full for its
// tooltip. Null when it is everywhere. cities.json's countryCodes (["CA", "CA-ON"]) name the city's
// country: the code on an except-list that leaves it out, or the country (or province) a long only-list lacks.
function offeredWhere(e, cityId) {
  if (!e || !e.codes || !e.codes.length) return null;
  const names = e.codes.map(countryName).sort((a, b) => a.localeCompare(b));
  const only = e.type === "NoCountriesExcept";
  // a world place passes its country's code itself: [cc]
  const c = !Array.isArray(cityId) && cityById(cityId), codes = Array.isArray(cityId) ? cityId : (c && c.countryCodes) || [];
  const country = codes.find((x) => !x.includes("-"));
  // an only-list naming some of the country's provinces lacks the city's province, not its country
  const lacks = country && e.codes.some((x) => x.startsWith(country + "-")) ? codes.find((x) => x.includes("-")) : country;
  const hit = !only && e.codes.find((x) => codes.includes(x));
  const countries = new Set(e.codes.map((x) => x.split("-")[0])).size;
  const short = names.length <= 3 ? names.join(", ")
    : `${countries} countries${only && lacks ? `, not ${countryName(lacks)}` : ""}`;
  return {
    text: hit ? `not offered in ${countryName(hit)}` : `${only ? "only in" : "not in"} ${short}`,
    title: `The app offers this quest ${only ? "only in" : "everywhere except"} ${names.join(", ")}`,
  };
}

function questRows(h) {
  const n = h.dates.length;
  return quests.quests.map((q) => {
    const s = h.quests[q.name];
    const status = h.world ? worldStatus(q, h) : (q.status && q.status[h.city]) || "unsupported";
    const open = s ? s.open[n - 1] : null;
    const prev = s && n > 1 ? s.open[n - 2] : null;
    const aged = s ? s.agedOnly[n - 1] : null;
    const counted = status === "counted" && open != null;
    return {
      q, status, open, counted,
      group: counted ? null : status === "counted" ? "missing" : GROUPS[status] ? status : "unsupported",
      delta: open != null && prev != null ? open - prev : null,
      isNew: open != null && n > 1 && prev == null,
      agedShare: q.usesAge && open ? aged / open : null,
    };
  });
}

// The rows the search box leaves; the header tick acts on these.
function shownRows(h) {
  const f = state.filter.trim().toLowerCase();
  return questRows(h).filter((r) => !f || r.q.name.toLowerCase().includes(f) ||
    humanize(r.q.name).toLowerCase().includes(f) || questTitle(r.q.name).toLowerCase().includes(f));
}

function renderQuestTable(h) {
  $("#table-city").textContent = h.name;
  const rows = shownRows(h);
  const { key, dir } = state.questSort;
  const val = {
    name: (r) => questTitle(r.q.name).toLowerCase(),
    open: (r) => r.open, delta: (r) => r.delta, aged: (r) => r.agedShare,
  }[key];
  rows.sort((a, b) => {
    if (a.counted !== b.counted) return a.counted ? -1 : 1;   // uncounted always below
    if (!a.counted) return GROUPS[a.group].rank - GROUPS[b.group].rank || a.q.order - b.q.order;
    const va = val(a), vb = val(b);
    if (va == null && vb == null) return a.q.order - b.q.order;
    if (va == null) return 1;
    if (vb == null) return -1;
    return (va < vb ? -1 : va > vb ? 1 : 0) * dir || a.q.order - b.q.order;
  });
  for (const th of document.querySelectorAll("#quest-table th[data-sort]"))
    th.setAttribute("aria-sort", th.dataset.sort === key ? (dir > 0 ? "ascending" : "descending") : "none");

  const tickable = rows.filter((r) => r.counted);
  const on = tickable.filter((r) => selected(r.q.name)).length;
  const head = $("#select-shown");
  head.checked = on > 0 && on === tickable.length;
  head.indeterminate = on > 0 && on < tickable.length;
  head.disabled = !tickable.length;

  // Counted quests with nothing open fold into one line under the open ones: the place's good news.
  const done = rows.filter((r) => r.counted && r.open === 0);
  const rest = rows.filter((r) => !(r.counted && r.open === 0));
  const at = rest.findIndex((r) => !r.counted);
  const out = [];
  for (const [i, r] of rest.entries()) {
    if (i === at && done.length) out.push(...doneRows(h, done));   // above the uncounted groups
    if (r.group && r.group !== (rest[i - 1] && rest[i - 1].group)) {
      const n = rest.filter((x) => x.group === r.group).length;
      out.push(el("tr", { class: "group-head" }, el("th", { colspan: 7, scope: "rowgroup" }, `${GROUPS[r.group].head(h)} · ${n}`)));
    }
    out.push(questRow(h, r));
  }
  if (at < 0 && done.length) out.push(...doneRows(h, done));
  $("#quest-table tbody").replaceChildren(...out);
}

let showDone = false;   // the "done here" line opened
function doneRows(h, done) {
  const n = done.length;
  const head = el("tr", { class: "done-head" }, el("td", { colspan: 7 },
    el("button", { type: "button", class: "done-toggle", "aria-expanded": String(showDone),
                   onclick: () => { showDone = !showDone; renderQuestTable(shownSeries(hist)); } },
      el("span", { class: "done-mark", "aria-hidden": "true" }, "✓"),
      `${nf.format(n)} quest type${n > 1 ? "s" : ""} done here`,
      el("span", { class: "done-more" }, showDone ? "hide" : "show"))));
  return [head, ...(showDone ? done.map((r) => questRow(h, r)) : [])];
}

function questRow(h, r) {
  const sel = selected(r.q.name), pinned = state.pinned.includes(r.q.name);
  const name = questTitle(r.q.name);
  const link = r.q.wikiLink ? el("a", { href: `https://wiki.openstreetmap.org/wiki/${r.q.wikiLink}` }, name) : el("span", {}, name);
  const where = r.group === "not-in-region" ? offeredWhere(r.q.enabledInCountries, h.world ? [h.cc] : h.city) : null;
  // An uncounted quest's tick does nothing here, so it is shown but locked; it still counts where the quest is.
  return el("tr", { class: [r.counted ? "" : "off", sel ? "" : "unselected", pinned ? "pinned" : ""].join(" ").trim() || null },
      el("td", { class: "c-pick" }, el("input", { type: "checkbox", checked: sel, disabled: !r.counted,
                                                  "aria-label": `Count ${name} in the totals`,
                                                  title: r.counted ? null : `Not counted in ${h.name}, so the tick does nothing here`,
                                                  onchange: () => toggleSelect(r.q.name) })),
      el("td", { class: "c-pin" }, r.counted ? el("button", { type: "button", class: "pin-btn", "aria-pressed": pinned ? "true" : "false",
                                                              title: pinned ? "Unpin: take its chart away" : "Pin: chart this quest on its own",
                                                              "aria-label": `${pinned ? "Unpin" : "Pin"} ${name}`,
                                                              onclick: () => togglePin(r.q.name) }) : null),
      el("td", {}, el("div", { class: "quest-cell" }, questIcon(r.q.name),
        el("div", {}, link, r.q.defaultDisabled ? el("span", { class: "chip", title: "Off by default in the app" }, "off by default") : null,
          where ? el("span", { class: "chip", title: where.title }, where.text) : null,
          el("span", { class: "code" }, r.q.name)))),
      el("td", { class: "c-trend" }, r.counted ? sparkline(h.dates, h.quests[r.q.name].open, name) : null),
      el("td", { class: "num" }, r.open == null ? "—" : nf.format(r.open)),
      el("td", { class: "num" }, r.isNew ? "new" : r.delta == null ? "—" : signed(r.delta)),
      el("td", { class: "num c-aged" }, r.agedShare == null ? "—" : `${Math.round(100 * r.agedShare)}%`));
}

function togglePin(name) {
  const i = state.pinned.indexOf(name);
  if (i >= 0) state.pinned.splice(i, 1);
  else if (state.pinned.length < MAX_PINNED) state.pinned.push(name);
  else { setStatus(`Up to ${MAX_PINNED} quests can be pinned at once.`); return; }
  setStatus("");
  writeURL();
  renderCity();
}

function toggleSelect(name) {
  if (selected(name)) state.selected.delete(name);
  else state.selected.add(name);
  selectionChanged();
}

function selectShown(on) {   // the header tick: every counted row the search box leaves
  for (const r of shownRows(hist)) {
    if (!r.counted) continue;
    if (on) state.selected.add(r.q.name);
    else state.selected.delete(r.q.name);
  }
  selectionChanged();
}

function selectionChanged() {
  writeURL();
  if (state.view === "places") renderPlaces();
  else renderCity();
}

// ---------- the place page ----------
// One page for a counted city and for each of its parts (DESIGN.md, "A neighbourhood is a place"): the
// chain above it, the number and its change, the chart, the quest table, then the places inside it. It
// paints from the series alone; the chain and the name layer's children follow when their region file is in.

let pageSeq = 0;   // the newest renderCity call; older ones stop where they are
async function renderCity() {
  if (state.view === "places") return renderPlaces();   // a world place's page (pins, range) is drawn from there
  const seq = ++pageSeq;
  if (!hist || hist.city !== state.city || (hist.part || "") !== state.part) {
    placeHeadText();
    const h = await seriesFor(state.city, state.part);
    if (seq !== pageSeq) return;
    if (!h) {   // a part without a published series: its city instead, saying so
      const was = state.part;
      state.part = "";
      writeURL();
      await renderCity();
      setStatus(`No counts for that part of ${cityById(state.city).name} yet (${was}); here is the whole city.`);
      return;
    }
    hist = h;
    showDone = false;
  }
  placeHeadText(hist);
  renderCityCharts(hist);
  renderQuestTable(shownSeries(hist));
  await placeAround(seq);
}

// The head's name, kind and date; before the series is in, the city's name from cities.json.
function placeHeadText(h = null) {
  const c = cityById(state.city);
  $("#place-name").textContent = h ? h.name : state.part ? "" : c.name;
  $("#place-kind").textContent = !h ? "" : h.part ? partKind(h.subtype) : "city";
  $("#place-asof").textContent = !h ? "" : `Newest count ${shortDate(last(h.dates))}, ${last(h.dates).slice(0, 4)}` +
    (h.part ? `, from ${h.cityName}'s daily run.` : ".");
  if (!h || !h.part) $("#place-crumbs").replaceChildren(placeLink(null, "All countries"), crumbSep(),
    el("span", {}, cityWhere(c)));   // until the name layer gives the chain
  else $("#place-crumbs").replaceChildren(placeLink(null, "All countries"), crumbSep(), cityLink(c, c.name));
}
const crumbSep = () => el("span", { class: "sep", "aria-hidden": "true" }, "›");

// The chain in the head, from the name layer's region file (15-80 KB). Below the table, the city's parts
// and the name layer's places inside this one, once the reader nears them: the parts come from the city's
// newest snapshot, which for Ontario is 250 KB gzipped.
let childWatch = null;
async function placeAround(seq) {
  const c = cityById(state.city);
  const box = $("#place-children");
  box.replaceChildren();
  const id = state.part || c.place, file = state.part ? hist.in : c.in;
  const ref = id && file ? await resolvePlace(id, file).catch(() => null) : null;
  if (seq !== pageSeq) return;
  if (ref) {
    const up = chain(ref).reverse();
    $("#place-crumbs").replaceChildren(placeLink(null, "All countries"),
      ...up.slice(0, -1).flatMap((r) => [crumbSep(), placeLink(r)]));
  }
  childWatch?.disconnect();
  childWatch = new IntersectionObserver(async (seen) => {
    if (!seen.some((e) => e.isIntersecting)) return;
    childWatch.disconnect();
    const parts = await partsCard(c.id, state.part).catch(() => null);
    if (seq !== pageSeq) return;
    const kids = ref && childrenCard(ref, childRows(ref).map((i) => ({ ref: rowRef(ref.shard, i) })));
    box.replaceChildren(...[parts, kids].filter(Boolean));
  }, { rootMargin: "800px 0px" });
  childWatch.observe(box);
}

// ---------- compare view ----------

// one quest's open count per city, each in its newest snapshot: data/compare/<quest>.json. A quest
// counted nowhere has no file, which reads as no count anywhere.
async function compareFile(quest) {
  if (!compareCache.has(quest)) {
    compareCache.set(quest, fetch(`${DATA}/compare/${encodeURIComponent(quest)}.json`, { cache: "no-cache" })
      .then((r) => {
        if (r.status === 404) return { open: {} };
        if (!r.ok) throw new Error(`compare/${quest}.json: HTTP ${r.status}`);
        return r.json();
      }));
  }
  return compareCache.get(quest);
}

async function compareRows() {
  const qn = state.compareQuest;
  const per = qn ? (await compareFile(qn)).open : null;
  const q = qn && questByName.get(qn);
  const rows = [];
  for (const c of cities.cities) {
    // cities.json carries the app-default total, not the reader's selection
    const open = qn ? per[c.id] ?? null : c.open;
    rows.push({
      c, open,
      notOffered: !!(q && q.status && q.status[c.id] === "not-in-region"),
      perKm2: open != null && c.landAreaKm2 ? open / c.landAreaKm2 : null,
      perRoadKm: open != null && c.highwayKm ? open / c.highwayKm : null,
      per1k: open != null && c.population ? (1000 * open) / c.population : null,
    });
  }
  return rows;
}

// Each city's default total on every snapshot date, for the trend column: data/trends.json, asked for
// when Compare first opens so a first visit doesn't carry it. Data written before 2026-11-10 has the
// arrays in cities.json; a file that fails to load leaves the column out.
let trendsFile = null;
function cityTrends() {
  if (!trendsFile) {
    const old = cities.cities.some((c) => c.trend);
    trendsFile = old
      ? Promise.resolve({ dates: cities.dates, trend: Object.fromEntries(cities.cities.map((c) => [c.id, c.trend])) })
      : getJSON("trends.json").catch(() => null);
  }
  return trendsFile;
}

async function renderCompare() {
  const sel = $("#compare-quest");
  if (!sel.options.length) {
    sel.append(el("option", { value: "" }, "All counted quests (app defaults)"));
    const counted = quests.quests.filter((q) => Object.values(q.status || {}).includes("counted"))
      .sort((a, b) => humanize(a.name).localeCompare(humanize(b.name)));
    for (const q of counted) sel.append(el("option", { value: q.name }, humanize(q.name) + (q.defaultDisabled ? " (off by default)" : "")));
  }
  sel.value = state.compareQuest;

  // cities.json and trends.json carry totals over time, not each quest's, so the trend column is for
  // all quests only
  const [rows, trends] = await Promise.all([compareRows(), state.compareQuest ? null : cityTrends()]);
  const { key, dir } = state.compareSort;
  const val = { name: (r) => r.c.name.toLowerCase(), open: (r) => r.open, perKm2: (r) => r.perKm2,
                perRoadKm: (r) => r.perRoadKm, per1k: (r) => r.per1k }[key];
  rows.sort((a, b) => {
    const va = val(a), vb = val(b);
    if (va == null) return 1;
    if (vb == null) return -1;
    return (va < vb ? -1 : va > vb ? 1 : 0) * dir;
  });
  for (const th of document.querySelectorAll("#compare-table th[data-sort]"))
    th.setAttribute("aria-sort", th.dataset.sort === key ? (dir > 0 ? "ascending" : "descending") : "none");
  const barKey = key === "name" ? "perKm2" : key;
  const max = Math.max(0, ...rows.map((r) => r[barKey === "open" ? "open" : barKey] || 0));
  const fmt = (v, f) => (v == null ? "—" : f.format(v));
  for (const th of document.querySelectorAll("#compare-table th.c-trend")) th.hidden = !trends;
  // The app offers some quests only in some countries, so totals cover different sets of quests.
  const kinds = cities.cities.map((c) => c.questsCounted).filter((n) => n != null);
  const lo = Math.min(...kinds), hi = Math.max(...kinds);
  const off = rows.filter((r) => r.notOffered).length;
  $("#compare-sub").textContent = `${state.compareQuest ? humanize(state.compareQuest) : "All counted quests the app turns on by default"}, ${cities.asOfDate}. ` +
    "Raw counts follow city size, so the table ranks by density. Click a column to rank by it; the bar shows the ranked column." +
    (state.compareQuest && cities.dates ? " Trends are shown for all counted quests only." : "") +
    (state.compareQuest && off ? ` The app doesn't offer this quest in ${off} of these cities; they are listed last.` : "") +
    (!state.compareQuest && lo < hi ? ` The app offers some quests only in some countries, so a city's total covers ${lo}–${hi} quest types depending on where it is.` : "");
  $("#compare-table tbody").replaceChildren(...rows.map((r, i) => {
    const v = r[barKey];
    const trend = trends && trends.trend[r.c.id];
    const where = r.notOffered && offeredWhere(questByName.get(state.compareQuest).enabledInCountries, r.c.id);
    return el("tr", { class: [r.c.id === state.city ? "picked" : "", r.notOffered ? "off" : ""].join(" ").trim() || null },
      el("td", { class: "num" }, r.notOffered ? null : i + 1),
      el("td", {}, el("a", { href: "#", onclick: (e) => { e.preventDefault(); setCity(r.c.id); setView("city"); } }, r.c.name)),
      trends ? el("td", { class: "c-trend" }, trend ? sparkline(trends.dates, trend, r.c.name) : null) : null,
      el("td", { class: "num" }, r.notOffered ? el("span", { title: where ? where.title : null }, where ? where.text : "not offered") : fmt(r.open, nf)),
      el("td", { class: "num" }, rate(r.perKm2)),
      el("td", { class: "num" }, rate(r.perRoadKm)),
      el("td", { class: "num" }, rate(r.per1k)),
      el("td", { class: "bar-col" }, v != null && max ? el("div", { class: "hbar", style: `width:${(100 * v) / max}%`,
                                                                    title: `${r.c.name}: ${rate(v)}` }) : null));
  }));
}

// ---------- places view ----------
// The name layer (DATA-FORMAT.md, "Places and parts"): places/index.json names every country and its
// regions; places/<cc>/<region>.json holds a region's places as rows [id, name, st, parent, xmin, ymin,
// xmax, ymax, en, counted], parents first. A region file is fetched when the reader opens a place in it,
// and all of a country's when they search inside it or open the country; never the world's.
// A place link is ?place=<id>&in=<cc>/<regionId>: countries and regions are found in the index, any
// other place in the region file `in` names. Region ids and file names are the index's, used as given.

const PLACES = "places";
const ASK_URL = "https://github.com/skfd/sc-open-quests/issues";
const SUBTYPE = ["country", "dependency", "region", "county", "local admin area", "locality", "borough",
                 "macrohood", "neighbourhood", "microhood"];
const SHOW_CHILDREN = 120;            // per subtype, before "Show all"
const MAX_RESULTS = 50;
const R = { id: 0, name: 1, st: 2, parent: 3, en: 8, counted: 9 };

let placeIndex = null;                 // promise of places/index.json
const shardCache = new Map();          // region file -> promise of its shard
const optionalCache = new Map();       // path -> promise of JSON, or null when absent
let placeSeq = 0;                      // the newest renderPlaces call; older ones stop where they are
let searchSeq = 0;

// JSON that may not be there (a 404 is null, not an error): parts names, a snapshot.
function optionalJSON(url) {
  if (!optionalCache.has(url)) {
    optionalCache.set(url, fetch(url, { cache: "no-cache" }).then((r) => {
      if (r.status === 404) return null;
      if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
      return r.json();
    }));
  }
  return optionalCache.get(url);
}

// A country is named as StreetComplete names it: the platform's locale data (CLDR), here the browser's,
// in English like the rest of the site; Palestine by CLDR's short form (DESIGN.md, "Countries in the place
// index"). The index's own name (the local one, or the code where no division stands for the country)
// stays searchable.
const shortRegionNames = new Intl.DisplayNames(["en"], { type: "region", style: "short" });
function cldrCountry(cc) {
  try {
    const n = (cc === "PS" ? shortRegionNames : regionNames).of(cc);
    return n && n !== cc ? n : null;
  } catch { return null; }
}

function placesIndex() {
  if (!placeIndex) {
    placeIndex = optionalJSON(`${PLACES}/index.json`).then((idx) => {
      if (!idx) return idx;
      for (const c of idx.countries) c.en = cldrCountry(c.cc) || c.en || null;
      idx.countries.sort((a, b) => enName(a).localeCompare(enName(b), "en"));
      return idx;
    });
    placeIndex.catch(() => { placeIndex = null; });   // a failed fetch is tried again next time
  }
  return placeIndex;
}

// Accent- and case-blind, punctuation as spaces: "Saint-Jérôme" and "saint jerome" are one key.
function fold(s) {
  return (s || "").normalize("NFD").replace(/\p{M}/gu, "").toLowerCase()
    .replace(/ß/g, "ss").replace(/æ/g, "ae").replace(/œ/g, "oe").replace(/ø/g, "o").replace(/ł/g, "l")
    .replace(/đ/g, "d").replace(/ı/g, "i").replace(/[^\p{L}\p{N}]+/gu, " ").trim();
}

// A region file with what browsing needs: rows by id, each row's children, the top rows (parent -1)
// and the region's own row among them when it has one (a "_" file, places outside every region, has
// none, so its top rows hang off the country).
function loadShard(country, region) {
  if (!shardCache.has(region.file)) {
    const p = fetch(`${PLACES}/${region.file}`, { cache: "no-cache" }).then((r) => {
      if (!r.ok) throw new Error(`${PLACES}/${region.file}: HTTP ${r.status}`);
      return r.json();
    }).then((f) => {
      const rows = f.places || [];
      const kids = rows.map(() => []), top = [], byId = new Map();
      let self = -1;
      rows.forEach((row, i) => {
        byId.set(row[R.id], i);
        if (row[R.parent] >= 0) kids[row[R.parent]].push(i);
        else if (self < 0 && region.id !== "_" && (row[R.id] === region.id || row[R.st] === 2)) self = i;
        else top.push(i);
      });
      return { country, region, rows, kids, top, self, byId,
               keys: rows.map((row) => [fold(row[R.name]), row[R.en] ? fold(row[R.en]) : null]) };
    });
    p.catch(() => shardCache.delete(region.file));
    shardCache.set(region.file, p);
  }
  return shardCache.get(region.file);
}

// Every region file of a country, for a search inside it or its roll-up. Files that fail are skipped.
async function loadCountry(country) {
  const got = await Promise.allSettled(country.regions.map((r) => loadShard(country, r)));
  return got.filter((g) => g.status === "fulfilled").map((g) => g.value);
}

// A place is a ref: { kind: "country" | "region" | "row", country, region, shard, i }.
// The English name where the name layer has one, else the local name, which still finds the place.
const enName = (p) => p.en || p.name;
const rowName = (row) => row[R.en] || row[R.name];
const refName = (ref) => ref.kind === "country" ? enName(ref.country) : ref.kind === "region" ? enName(ref.region) : rowName(ref.shard.rows[ref.i]);
// A country no Overture division heads (Palestine, Western Sahara, the Canaries) is addressed by its code,
// lower case: two letters never clash with a 12-hex place id.
const countryId = (c) => c.id || c.cc.toLowerCase();
const refId = (ref) => ref.kind === "country" ? countryId(ref.country) : ref.kind === "region" ? ref.region.id : ref.shard.rows[ref.i][R.id];
const refSt = (ref) => ref.kind === "country" ? 0 : ref.kind === "region" ? 2 : ref.shard.rows[ref.i][R.st];
const refIn = (ref) => ref.kind === "row" ? `${ref.country.cc.toLowerCase()}/${ref.region.id}` : "";
function refCounted(ref) {
  if (ref.kind === "row") return ref.shard.rows[ref.i][R.counted];
  if (ref.kind === "region" && ref.shard && ref.shard.self >= 0) return ref.shard.rows[ref.shard.self][R.counted];
  return null;
}
function rowRef(shard, i) {
  return i === shard.self ? { kind: "region", country: shard.country, region: shard.region, shard }
                          : { kind: "row", country: shard.country, region: shard.region, shard, i };
}

// From the place up to its country: [ref, parent, ..., country].
function chain(ref) {
  const out = [ref];
  if (ref.kind === "row") {
    let i = ref.shard.rows[ref.i][R.parent];
    while (i >= 0) { out.push(rowRef(ref.shard, i)); i = ref.shard.rows[i][R.parent]; }
    if (ref.region.id !== "_" && last(out).kind !== "region") out.push({ kind: "region", country: ref.country, region: ref.region, shard: ref.shard });
  }
  if (ref.kind !== "country") out.push({ kind: "country", country: ref.country });
  return out;
}

// "Annex · Toronto · Ontario · Canada": a name repeated by its parent (Toronto the county, Toronto the
// city) is said once.
// With upTo, the chain stops below that place (a roll-up's list need not repeat where it is).
function chainText(ref, from = 1, upTo = null) {
  let up = chain(ref).slice(from);
  const stop = upTo ? up.findIndex((r) => r.kind === upTo.kind && refId(r) === refId(upTo)) : -1;
  if (stop >= 0) up = up.slice(0, stop);
  return up.map(refName).filter((n, i, a) => n && n !== a[i - 1]).join(" · ");
}

async function resolvePlace(id, hint) {
  const idx = await placesIndex();
  if (!idx) return null;
  for (const country of idx.countries) {
    if (countryId(country) === id) return { kind: "country", country };
    const region = country.regions.find((r) => r.id === id && r.id !== "_");
    if (region) return { kind: "region", country, region, shard: await loadShard(country, region) };
  }
  const [cc, rid] = (hint || "").toLowerCase().split("/");   // the index has "CA", links and files "ca"
  const country = idx.countries.find((c) => c.cc.toLowerCase() === cc);
  const region = country && country.regions.find((r) => r.id === rid);
  if (!region) return null;
  const shard = await loadShard(country, region);
  const i = shard.byId.get(id);
  return i == null ? null : rowRef(shard, i);
}

// A counted place's page is the place page: [city id, part id or ""], or null when the place is not
// counted, or its city is not published yet.
function countedAs(ref) {
  const c = ref && refCounted(ref);
  if (!c) return null;
  const [city, part = ""] = c.split("/");
  return cityById(city) ? [city, part] : null;
}

function placeHref(ref) {
  const k = countedAs(ref);
  if (k) return queryString({ ...state, view: "city", city: k[0], part: k[1] });
  return queryString({ ...state, view: "places", place: ref ? refId(ref) : "", placeIn: ref ? refIn(ref) : "" });
}

function goPlace(ref) {
  const k = countedAs(ref);
  if (k) { openCounted(...k); return; }
  state.view = "places";
  state.place = ref ? refId(ref) : "";
  state.placeIn = ref ? refIn(ref) : "";
  writeURL();
  render();
  window.scrollTo({ top: 0 });
}

// The place page of a counted city, or of a part of it.
function openCounted(city, part = "") {
  setCity(city, part);
  state.view = "city";
  writeURL();
  renderFooter();
  render();
  window.scrollTo({ top: 0 });
}

// A link that opens a place here, and in a new tab with a modifier.
function placeLink(ref, text = refName(ref)) {
  return el("a", { href: placeHref(ref), onclick: (e) => {
    if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    goPlace(ref);
  } }, text);
}

// A link to a counted city's page, or to a part's with part.
function cityLink(c, text, part = "") {
  return el("a", { href: queryString({ ...state, view: "city", city: c.id, part }), onclick: (e) => {
    if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    openCounted(c.id, part);
  } }, text);
}

const cityById = (id) => cities.cities.find((c) => c.id === id);

// ---- the city picker ----
// A button naming the city, opening a sheet to find another. Every counted city is in cities.json, so
// the sheet filters them as the reader types, on their names and `aka` and on where they are; a country
// lists its cities. Towns the site does not count belong to the Places search, a country at a time.

let cityKeys = new Map();              // city id -> { own, where }, folded for the sheet's search
let sheetCountry = null;               // the country the sheet lists, { name, cc }; null = the sheet's start

function recentCities() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY)) || []; } catch { return []; }
}

// A city's own group is its country; a region's is its country or a province of it (DATA-FORMAT.md).
const groupOf = (c) => c.group || ((cities.regions || []).find((r) => r.id === c.region) || {}).group;
const cityCC = (c) => ((c.countryCodes || [])[0] || "").split("-")[0];
const cityCountry = (c) => c.group || countryName(cityCC(c)) || groupOf(c) || "";

function cityWhere(c) {
  const g = groupOf(c), n = cityCountry(c);
  return g && g !== n ? `${g}, ${n}` : n;
}

function showCity() {
  const c = cityById(state.city);
  $("#city-name").textContent = c.name;
  $("#city-where").textContent = cityWhere(c);
}

// The city (and part of it) in the state, the button and the reader's recent cities; the caller renders.
function setCity(id, part = "") {
  state.city = id;
  state.part = part;
  showCity();
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify([id, ...recentCities().filter((x) => x !== id)].slice(0, MAX_RECENT + 1)));
  } catch { /* no storage, no recent cities */ }
}

function chooseCity(id) {
  $("#city-sheet").close();
  setCity(id);
  if (state.view === "places") state.view = "city";   // from a world place's page ("Change place")
  writeURL();
  renderFooter();
  render();
}

// The query carried to the Places search, inside a country: that search has no towns without one.
function searchPlaces(text, cc) {
  $("#city-sheet").close();
  state.place = "";
  state.placeIn = "";
  state.placeScope = cc;
  $("#place-search").value = text;
  setView("places");
  runSearch();
  window.scrollTo({ top: 0 });
}

function sheetSection(head, note, rows) {
  return [el("h3", { class: "sheet-head" }, el("span", {}, head), note ? el("span", {}, note) : null),
          el("ul", { class: "sheet-list" }, rows.map((r) => el("li", {}, r)))];
}

function sheetCity(c, where = true) {
  return el("button", { type: "button", class: "sheet-row", onclick: () => chooseCity(c.id) },
    el("span", {},
      el("span", { class: "sheet-name" }, c.name),
      where ? el("span", { class: "sheet-where" }, cityWhere(c)) : null),
    el("span", { class: "sheet-value" }, nfShort.format(c.open)));
}

function browseCountry(country) {
  sheetCountry = country;
  renderSheet();
  $("#city-results .sheet-row").focus();
}

function sheetStart() {
  const recent = recentCities().filter((id) => id !== state.city).map(cityById).filter(Boolean).slice(0, MAX_RECENT);
  const byCountry = new Map();
  for (const c of cities.cities) {
    const name = cityCountry(c);
    if (!byCountry.has(name)) byCountry.set(name, { name, cc: cityCC(c), n: 0 });
    byCountry.get(name).n++;
  }
  const countries = [...byCountry.values()].sort((a, b) => b.n - a.n || a.name.localeCompare(b.name));
  return [
    ...(recent.length ? sheetSection("Recent", "open quests", recent.map((c) => sheetCity(c))) : []),
    ...sheetSection("Counted cities by country", null, countries.map((k) =>
      el("button", { type: "button", class: "sheet-row", onclick: () => browseCountry(k) },
        el("span", { class: "sheet-name" }, k.name),
        el("span", { class: "sheet-value" }, `${nf.format(k.n)} ${k.n > 1 ? "cities" : "city"} ›`)))),
    el("ul", { class: "sheet-list sheet-more" }, el("li", {},
      el("button", { type: "button", class: "sheet-row", onclick: () => { $("#city-sheet").close(); goPlace(null); } },
        "Every place, by country ›"))),
  ];
}

// A country's cities by name, under their provinces when it has several.
function sheetOfCountry() {
  const list = cities.cities.filter((c) => cityCountry(c) === sheetCountry.name);
  const areas = [...new Set(list.map(groupOf))].sort((a, b) => a.localeCompare(b));
  return [
    el("button", { type: "button", class: "sheet-row sheet-back", onclick: () => browseCountry(null) }, "‹ All countries"),
    ...(areas.length > 1
      ? areas.flatMap((a, i) => sheetSection(a, i ? null : "open quests", list.filter((c) => groupOf(c) === a).map((c) => sheetCity(c, false))))
      : sheetSection(sheetCountry.name, "open quests", list.map((c) => sheetCity(c, false)))),
  ];
}

// A name beats a place, and a place must match from a word's start: "ber" finds Berlin first, and not
// every city in Alberta.
function cityRank(c, q) {
  const { own, where } = cityKeys.get(c.id);
  const ranks = [...own.map((k) => matchRank(k, q)),
                 ...where.map((k) => { const r = matchRank(k, q); return r != null && r < 3 ? r + 4 : null; })];
  const found = ranks.filter((r) => r != null);
  return found.length ? Math.min(...found) : null;
}

function sheetHits(text, q) {
  const hits = cities.cities.map((c) => ({ c, rank: cityRank(c, q) })).filter((h) => h.rank != null)
    .sort((a, b) => a.rank - b.rank || b.c.open - a.c.open);
  const cc = sheetCountry ? sheetCountry.cc : cityCC(cityById(state.city));
  const head = !hits.length ? "No counted city matches" :
    hits.length > MAX_RESULTS ? `The first ${MAX_RESULTS} of ${nf.format(hits.length)} counted cities` :
    `Counted cities · ${hits.length}`;
  return [
    ...sheetSection(head, hits.length ? "open quests" : null, hits.slice(0, MAX_RESULTS).map((h) => sheetCity(h.c))),
    el("ul", { class: "sheet-list sheet-more" }, el("li", {},
      el("button", { type: "button", class: "sheet-row", onclick: () => searchPlaces(text, cc) },
        `Search ${countryName(cc) ? `${countryName(cc)}'s` : "a country's"} towns for “${text}” ›`))),
  ];
}

function renderSheet() {
  const text = $("#city-search").value.trim(), q = fold(text), box = $("#city-results");
  box.replaceChildren(...(q ? sheetHits(text, q) : sheetCountry ? sheetOfCountry() : sheetStart()));
  box.scrollTop = 0;
}

function initCitySheet() {
  cityKeys = new Map(cities.cities.map((c) => [c.id, {
    own: [c.name, ...(c.aka || [])].map(fold),
    where: [groupOf(c), cityCountry(c), countryName(cityCC(c))].map(fold),
  }]));
  const sheet = $("#city-sheet"), search = $("#city-search");
  $("#city-button").addEventListener("click", () => {
    sheetCountry = null;
    search.value = "";
    renderSheet();
    sheet.showModal();
  });
  $("#city-close").addEventListener("click", () => sheet.close());
  sheet.addEventListener("click", (e) => { if (e.target === sheet) sheet.close(); });   // the backdrop
  search.addEventListener("input", renderSheet);
  sheet.addEventListener("keydown", (e) => {
    // preventDefault: the sheet closes, focus returns to the button that opened it, and Enter would press it again
    if (e.key === "Enter" && e.target === search && fold(search.value)) { e.preventDefault(); $("#city-results .sheet-row").click(); return; }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const rows = [search, ...sheet.querySelectorAll(".sheet-row")];
    const next = rows[rows.indexOf(document.activeElement) + (e.key === "ArrowDown" ? 1 : -1)];
    if (next) next.focus();
  });
}

// ---- search ----

function fillScope(idx) {
  const sel = $("#place-scope");
  if (!sel.options.length) {
    sel.append(el("option", { value: "" }, "Countries and regions"),
      ...idx.countries.map((c) => el("option", { value: c.cc }, enName(c))));
  }
  sel.value = state.placeScope;
}

// 0 the whole name, 1 its start, 2 a word's start, 3 anywhere; null no match.
function matchRank(key, q) {
  if (!key) return null;
  if (key === q) return 0;
  if (key.startsWith(q)) return 1;
  if ((" " + key).includes(" " + q)) return 2;
  return key.includes(q) ? 3 : null;
}

async function runSearch() {
  const seq = ++searchSeq;
  const q = fold($("#place-search").value);
  const box = $("#place-results"), note = $("#place-search-note");
  if (!q) { box.replaceChildren(); note.textContent = ""; return; }
  const idx = await placesIndex();
  if (!idx || seq !== searchSeq) return;
  const country = idx.countries.find((c) => c.cc === state.placeScope);
  if (country) {
    const n = country.regions.reduce((s, r) => s + (r.n || 0), 0);
    const pending = country.regions.some((r) => !shardCache.has(r.file));
    if (pending) { note.textContent = `Loading ${enName(country)}'s ${nf.format(n)} place names…`; box.setAttribute("aria-busy", "true"); }
    await loadCountry(country);
    box.removeAttribute("aria-busy");
    if (seq !== searchSeq) return;
  }
  const hits = [];
  const offer = (ref, keys, counted) => {
    let rank = null;
    for (const k of keys) { const r = matchRank(k, q); if (r != null && (rank == null || r < rank)) rank = r; }
    if (rank != null) hits.push({ ref, rank, counted: !!counted, st: refSt(ref), name: refName(ref) });
  };
  for (const c of idx.countries) {
    offer({ kind: "country", country: c }, [fold(c.name), fold(c.en)]);
    for (const r of c.regions) if (r.id !== "_" && r.name) offer({ kind: "region", country: c, region: r }, [fold(r.name), fold(r.en)]);
  }
  // every region file loaded so far: the chosen country's, and any the reader browsed
  const shards = await Promise.all([...shardCache.values()].map((p) => p.catch(() => null)));
  if (seq !== searchSeq) return;
  for (const sh of shards) {
    if (!sh) continue;
    for (let i = 0; i < sh.rows.length; i++) if (i !== sh.self) offer(rowRef(sh, i), sh.keys[i], sh.rows[i][R.counted]);
  }
  hits.sort((a, b) => a.rank - b.rank || b.counted - a.counted || a.st - b.st ||
    a.name.length - b.name.length || a.name.localeCompare(b.name));
  box.replaceChildren(...hits.slice(0, MAX_RESULTS).map((h) => {
    return el("li", {}, placeLink(h.ref),
      h.counted ? el("span", { class: "chip counted" }, "counted") : null,
      el("span", { class: "place-kind" }, SUBTYPE[h.st] || ""),
      el("span", { class: "place-chain" }, chainText(h.ref)));
  }));
  const where = country ? `${enName(country)}'s places and every country and region` :
    "country and region names (choose a country to search its towns and neighbourhoods)";
  note.textContent = !hits.length ? `Nothing found among ${where}.` :
    hits.length > MAX_RESULTS ? `The first ${MAX_RESULTS} of ${nf.format(hits.length)} matches among ${where}; type more to narrow.` :
    `${hits.length} match${hits.length > 1 ? "es" : ""} among ${where}.`;
}

// ---- the page ----

async function renderPlaces() {
  const seq = ++placeSeq;
  if (worldShown()) { await renderWorld(seq); return; }   // the same world place again: a tick, a pin, the range
  const page = $("#place-page");
  const idx = await placesIndex();
  if (seq !== placeSeq) return;
  if (!idx) {
    page.replaceChildren(el("p", { class: "notice" }, "Place names are not published yet."));
    return;
  }
  fillScope(idx);
  if (!state.place) { page.replaceChildren(countriesCard(idx)); return; }
  page.replaceChildren(el("p", { class: "notice" }, "Loading…"));
  const ref = await resolvePlace(state.place, state.placeIn);
  if (seq !== placeSeq) return;
  if (!ref) {
    page.replaceChildren(el("p", { class: "notice" }, `This link names a place the site cannot find (${state.place}). ` +
      "Try the search above."));
    return;
  }
  const k = countedAs(ref);
  if (k) {   // a counted place has the place page; the ?place= link becomes its ?city= one
    state.place = "";
    state.placeIn = "";
    setCity(...k);
    state.view = "city";
    writeURL();
    renderFooter();
    await render();
    return;
  }
  if (state.placeScope !== ref.country.cc) { state.placeScope = ref.country.cc; $("#place-scope").value = ref.country.cc; }
  const wh = await worldPlace(ref).catch(() => null);   // counted by the world: numbers; else as before
  if (seq !== placeSeq) return;
  if (wh) {
    hist = wh;
    showDone = false;
    await renderWorld(seq);
    return;
  }
  const head = placeHead(ref);
  const slot = el("div", {}, el("p", { class: "notice" }, ref.kind === "country" ? `Loading ${enName(ref.country)}'s places…` : "Loading…"));
  page.replaceChildren(head, slot);
  if (ref.kind === "country") page.append(countryChildren(ref, []) || "");
  const sections = await placeSections(ref);
  if (seq !== placeSeq) return;
  slot.replaceChildren(...sections.filter(Boolean));
}

function countriesCard(idx) {
  return el("article", { class: "card" },
    el("h2", {}, "Countries"),
    el("p", { class: "sub" }, "Every named place, from Overture Maps' divisions. Choose a country, then a region, " +
      "and on down; places this site counts link to their numbers, and any other can be asked for."),
    el("p", { class: "sub" }, "Places are filed where StreetComplete applies that country's rules, so a few " +
      "appear under two countries. This site describes the app; it takes no position on borders."),
    el("ul", { class: "place-grid" }, idx.countries.map((c) => el("li", {},
      placeLink({ kind: "country", country: c }),
      el("span", { class: "place-n" }, nf.format(c.regions.reduce((s, r) => s + (r.n || 0), 0)))))));
}

function placeHead(ref) {
  const up = chain(ref).reverse();
  return el("article", { class: "card place-head" },
    el("nav", { class: "crumbs", "aria-label": "Where it is" },
      placeLink(null, "All countries"),
      ...up.slice(0, -1).flatMap((r) => [el("span", { class: "sep", "aria-hidden": "true" }, "›"), placeLink(r)])),
    el("h2", {}, refName(ref),
      el("span", { class: "place-kind" }, SUBTYPE[refSt(ref)] || "")));
}

// Everything inside a place, below it: its descendants' row indices, per shard.
function descendants(ref, shards) {
  if (ref.kind === "country") return shards.map((sh) => ({ sh, idx: sh.rows.map((_, i) => i) }));
  const out = [], stack = ref.kind === "region" ? [...childRows(ref)] : [...ref.shard.kids[ref.i]];
  while (stack.length) { const i = stack.pop(); out.push(i); stack.push(...ref.shard.kids[i]); }
  return [{ sh: ref.shard, idx: out }];
}

function childRows(ref) {
  const sh = ref.shard;
  if (ref.kind === "region") return [...(sh.self >= 0 ? sh.kids[sh.self] : []), ...sh.top];
  return sh.kids[ref.i];
}

async function placeSections(ref) {
  const counted = refCounted(ref);
  const out = [];
  if (ref.kind === "country") {
    const shards = await loadCountry(ref.country);
    const card = countryChildren(ref, shards);
    const old = $("#place-page > .card.children");
    if (old && card) old.replaceWith(card);
    else if (card) out.push(card);
    out.unshift(rollupCard(ref, shards));
    return out;
  }
  // a counted place whose city is not in cities.json yet (counted ones open the place page)
  if (counted) out.push(el("article", { class: "card" }, el("h2", {}, "Counted"),
    el("p", { class: "sub" }, `${refName(ref)} is counted; its numbers arrive with the next published count.`)));
  else if (ref.kind === "region") out.push(rollupCard(ref, [ref.shard]));
  else {
    out.push(askCard(ref));
    const inside = descendants(ref, null);
    if (inside[0].idx.some((i) => ref.shard.rows[i][R.counted])) out.push(rollupCard(ref, [ref.shard]));
  }
  out.push(childrenCard(ref, childRows(ref).map((i) => ({ ref: rowRef(ref.shard, i) }))));
  return out;
}

// A country's regions from the index (with their files once loaded, so a counted region shows it), and
// the places of its "_" file, outside every region.
function countryChildren(ref, shards) {
  const shardOf = (r) => shards.find((sh) => sh.region === r);
  return childrenCard(ref, [
    ...ref.country.regions.filter((r) => r.id !== "_").map((r) => ({ ref: { kind: "region", country: ref.country, region: r, shard: shardOf(r) }, n: r.n })),
    ...shards.filter((sh) => sh.region.id === "_").flatMap((sh) => sh.top.map((i) => ({ ref: rowRef(sh, i) }))),
  ]);
}

// A region or country is the sum of nothing: it says how many of its places are counted and lists them.
function rollupCard(ref, shards) {
  const inside = descendants(ref, shards);
  let m = 0;
  const found = [];
  for (const { sh, idx } of inside) {
    m += idx.length;
    for (const i of idx) if (sh.rows[i][R.counted]) found.push({ sh, i, c: sh.rows[i][R.counted] });
  }
  const cityIds = new Set(found.filter((f) => !f.c.includes("/")).map((f) => f.c));
  const partsOf = new Map();
  for (const f of found) {
    const city = f.c.includes("/") ? f.c.split("/")[0] : null;
    if (city && cityIds.has(city)) partsOf.set(city, (partsOf.get(city) || 0) + 1);
  }
  // a city's parts are on its own page; parts whose city is outside this place are listed here
  const listed = found.filter((f) => !f.c.includes("/") || !cityIds.has(f.c.split("/")[0]));
  listed.sort((a, b) => rowName(a.sh.rows[a.i]).localeCompare(rowName(b.sh.rows[b.i])));
  const name = refName(ref);
  return el("article", { class: "card" },
    el("h2", {}, `${nf.format(found.length)} of ${nf.format(m)} places counted`),
    el("p", { class: "sub" }, found.length
      ? `${name} itself is not counted: the numbers are each counted place's own, and they do not add up to ${name}.`
      : `Nothing in ${name} is counted yet. Open a place to ask for it.`),
    listed.length ? el("ul", { class: "counted-list" }, listed.map((f) => {
      const r = rowRef(f.sh, f.i), city = !f.c.includes("/") && cityById(f.c), parts = partsOf.get(f.c);
      return el("li", {}, placeLink(r),
        el("span", { class: "place-kind" }, SUBTYPE[refSt(r)] || ""),
        city ? el("span", { class: "num" }, `${nf.format(city.open)} open`) : null,
        parts ? el("span", { class: "place-chain" }, `${parts} part${parts > 1 ? "s" : ""} counted`) : null,
        el("span", { class: "place-chain" }, chainText(r, 1, ref)));
    })) : null,
    cityIds.size ? el("p", { class: "sub" }, `Open quests as of each city's newest count, with the quests the app turns on by default.`) : null);
}

function childrenCard(ref, items) {
  if (!items.length) return null;
  const groups = new Map();
  for (const it of items) {
    const st = refSt(it.ref);
    if (!groups.has(st)) groups.set(st, []);
    groups.get(st).push(it);
  }
  const body = el("div", {});
  for (const st of [...groups.keys()].sort((a, b) => a - b)) {
    const list = groups.get(st).sort((a, b) => refName(a.ref).localeCompare(refName(b.ref)));
    const ul = el("ul", { class: "place-grid" });
    const fill = (n) => ul.replaceChildren(...list.slice(0, n).map((it) => {
      const c = refCounted(it.ref);
      const kids = it.ref.kind === "row" ? it.ref.shard.kids[it.ref.i].length : 0;
      return el("li", {}, placeLink(it.ref), c ? el("span", { class: "chip counted" }, "counted") : null,
        it.n != null ? el("span", { class: "place-n" }, nf.format(it.n)) : kids ? el("span", { class: "place-n" }, nf.format(kids)) : null);
    }));
    fill(SHOW_CHILDREN);
    const more = list.length > SHOW_CHILDREN
      ? el("button", { type: "button", class: "btn", onclick: (e) => { fill(list.length); e.target.remove(); } }, `Show all ${nf.format(list.length)}`)
      : null;
    body.append(el("h3", {}, `${SUBTYPE[st] || "other"} (${nf.format(list.length)})`), ul);
    if (more) body.append(more);   // append(null) would write "null"
  }
  return el("article", { class: "card children" }, el("h2", {}, `Inside ${refName(ref)}`),
    el("p", { class: "sub" }, "The number beside a place is how many places it holds."), body);
}

function askCard(ref) {
  const name = refName(ref), id = refId(ref);
  const path = chain(ref).reverse().map(refName).filter(Boolean).join(" / ");
  const p = new URLSearchParams({ template: "place-request.yml", title: `Count ${name} (${enName(ref.country)})`,
                                  "place-id": id, "place-name": name, "place-path": path });
  const search = new URLSearchParams({ q: `is:issue label:"place request" ${id}` });
  return el("article", { class: "card ask" },
    el("h2", {}, "Not counted yet"),
    el("p", {}, `This site does not count the quests in ${name} yet. Places are added when someone asks.`),
    el("p", {}, el("a", { class: "btn primary", href: `${ASK_URL}/new?${p}` }, "Ask for this place"),
      " ", el("span", { class: "sub" }, "opens a short GitHub form with the place filled in.")),
    el("p", { class: "sub" }, "Someone may have asked already: ",
      el("a", { href: `${ASK_URL}?${search}` }, "look for a request"), ", and a 👍 on it is a vote."));
}

// The newest snapshot of a city: the parts are in it (cities.<id>.parts).
function snapshotOf(c) { return optionalJSON(`${DATA}/${c.region}/snapshots/${c.asOfDate}.json`); }
function partNames(cityId) { return optionalJSON(`${DATA}/parts/${encodeURIComponent(cityId)}.json`); }

const partTotal = (counts) => Object.entries(counts || {}).reduce((s, [q, n]) => s + (selected(q) ? n : 0), 0);
const partKind = (st) => (st === "neighborhood" ? "neighbourhood" : st || "part");

// The city's parts with their totals over the ticked quests, from its newest snapshot, each linking to its
// page; current (a part id) is the one shown. Null when the city has none published.
async function partsCard(cityId, current) {
  const c = cityById(cityId);
  if (!c) return null;
  // the snapshot first: a city without parts has no names file to ask for
  const snap = await snapshotOf(c).catch(() => null);
  const counts = snap && snap.cities && snap.cities[cityId] && snap.cities[cityId].parts;
  const names = counts && Object.keys(counts).length ? await partNames(cityId).catch(() => null) : null;
  if (!names || !names.parts || !names.parts.length) return null;
  const rows = names.parts.map((p) => ({ p, open: counts[p.id] ? partTotal(counts[p.id]) : null }))
    .sort((a, b) => (b.open ?? -1) - (a.open ?? -1) || enName(a.p).localeCompare(enName(b.p)));
  return el("article", { class: "card" },
    el("h2", {}, current ? `Every part of ${c.name}` : `Neighbourhoods and other parts of ${c.name}`),
    el("p", { class: "sub" }, `Open quests inside each part's OpenStreetMap boundary on ${shortDate(c.asOfDate)}, counting ` +
      `${selectionText()}. Parts overlap and leave gaps, so they do not add up to the city.`),
    el("div", { class: "table-wrap" }, el("table", { class: "data parts" },
      el("thead", {}, el("tr", {}, el("th", { scope: "col" }, "Part"), el("th", { scope: "col" }, "Kind"), el("th", { scope: "col", class: "num" }, "Open"))),
      el("tbody", {}, rows.map(({ p, open }) => el("tr", { class: p.id === current ? "picked" : null },
        el("td", {}, p.id === current ? el("b", {}, enName(p)) : cityLink(c, enName(p), p.id)),
        el("td", {}, partKind(p.subtype)),
        el("td", { class: "num" }, open == null ? "—" : nf.format(open))))))));
}

// ---- world places ----
// Any place of the name layer the world counts, beyond the counted cities (DESIGN.md, "World places
// published: stable paths (schema 2)"): latest.json and the place's own file, its whole series, turned into a series the
// shape of a city's, so the place page draws it as it draws a city. Its children's numbers come from
// children/<self>. The paths are stable: every file but latest.json is asked with ?v=<latest.v>, the token
// of the publish, so it takes the browser's cache until the next one; latest.json is asked afresh. A file
// that is missing, or a host that does not answer, is null: the place then shows as it did before,
// "Not counted yet".

const worldCache = new Map();   // path (with its ?v) -> promise of JSON or null
// v is the publish token of the latest.json in hand; without it the file is latest.json itself, asked afresh.
function worldJSON(path, v = null) {
  if (WORLD === "/") return Promise.resolve(null);  // no world host yet (WORLD_HOST), and no ?world=
  const fresh = v == null;
  if (!fresh) path += `?v=${encodeURIComponent(v)}`;
  if (!worldCache.has(path)) {
    const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 8000);
    const p = fetch(WORLD + path, { cache: fresh ? "no-cache" : "default", signal: ctl.signal })
      .then((r) => (r.status === 404 ? null : r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      // a 404 is kept; a failure is tried again next time, latest.json's after 5 minutes (each try logs an error)
      .catch(() => { setTimeout(() => worldCache.delete(path), fresh ? 300000 : 0); return null; })
      .finally(() => clearTimeout(timer));
    worldCache.set(path, p);
  }
  return worldCache.get(path);
}
const worldShard = (id) => `${id.slice(0, 2)}/${id}.json`;

// Change points [[day, open, aged], ...]: the values hold from day number `day` until the next point, 0 before
// the first. Day 0 is latest.first. A point past k is not read, so a file newer than the latest.json in hand
// gives the same numbers.
function pointAt(points, k) {
  let v = [0, 0];
  for (const [i, open, aged] of points || []) { if (i > k) break; v = [open, aged]; }
  return v;
}

// Does the app offer a quest in country cc? null when its rule names only some of the country's provinces or
// states: the world gates by position, so a quest can be on in one place of the country and off in another.
function offeredIn(e, cc) {
  const only = e && e.type === "NoCountriesExcept";
  const codes = (e && e.codes) || [];
  if (codes.includes(cc)) return only;
  if (codes.some((c) => c.startsWith(cc + "-"))) return null;
  return !only;
}

// A quest for a world place: counted where the world counts it and the app offers it in the place's country
// (or the place's files hold it), not offered where the app leaves the country out, else not counted.
function worldStatus(q, h) {
  if (!h.worldQuests.has(q.name)) return "unsupported";
  if (h.quests[q.name]) return "counted";   // worldSeries holds every quest counted here
  // on in some of the country's provinces only: "No count", not "Not offered", since it may be offered here
  return offeredIn(q.enabledInCountries, h.cc) === null ? "counted" : "not-in-region";
}

// The series: every day from the place's first counted day (`from`, 0 when absent) through latest.date, read
// from the place file's change points. A quest the file leaves out is 0 if the world counts it in this place
// (it is in latest.json's quests and the app offers it in the country); else the quest stays out. Null when
// the place was first counted after latest.date.
function worldSeries(latest, pf, cc) {
  const last = Math.round((dayTs(latest.date) - dayTs(latest.first)) / 86400);
  const from = Number.isInteger(pf.from) && pf.from > 0 ? pf.from : 0;
  if (!(last >= from)) return null;
  const days = Array.from({ length: last - from + 1 }, (_, k) => from + k);
  const counted = new Set(latest.quests);
  const names = new Set([...latest.quests.filter((q) => offeredIn(questByName.get(q)?.enabledInCountries, cc) === true),
                         ...Object.keys(pf.quests)]);
  const quests = {};
  for (const q of names) {
    const at = days.map((k) => pointAt(pf.quests[q], k));
    quests[q] = { open: at.map((v) => v[0]), agedOnly: at.map((v) => v[1]) };
  }
  const meta = { scVersion: latest.scVersion, resurveyMultiplier: latest.resurveyMultiplier ?? 1, notes: true };
  return { world: true, dates: days.map((k) => addDays(latest.first, k)), meta: days.map(() => meta), quests, worldQuests: counted };
}

const DAY = /^\d{4}-\d\d-\d\d$/;
// A place's world series, or null when the world does not count it (or its files cannot be had).
async function worldPlace(ref) {
  const id = refId(ref);
  if (!/^[0-9a-f]{12}$/.test(id)) return null;   // a country addressed by its code has no world file
  const latest = await worldJSON("latest.json");
  // a latest.json of another schema (the host mid-switch) is as good as none
  if (!latest || latest.schema !== 2 || latest.v == null || !latest.place || !latest.children || !Array.isArray(latest.quests) ||
      ![latest.date, latest.first, latest.back].every((d) => DAY.test(d))) return null;
  const pf = await worldJSON(latest.place + worldShard(id), latest.v);
  if (!pf || !pf.quests) return null;
  const cc = (pf.cc || ref.country.cc).toUpperCase();
  const s = worldSeries(latest, pf, cc);
  if (!s) return null;
  return { ...s, id, placeIn: state.placeIn, ref, cc, latest, name: refName(ref) };
}

// Is the page showing the world place the state names?
const worldShown = () => state.view === "places" && !!state.place && !!hist && !!hist.world &&
  hist.id === state.place && hist.placeIn === state.placeIn;

// The place page for a world place: the head, tiles, chart and table from its series, then its children.
async function renderWorld(seq) {
  const h = hist;
  const page = ++pageSeq;    // a city page still loading stops where it is, and this one if a city follows
  childWatch?.disconnect();
  $("#view-places").hidden = true;
  $("#view-city").hidden = false;
  const up = chain(h.ref).reverse();
  $("#place-crumbs").replaceChildren(placeLink(null, "All countries"), ...up.slice(0, -1).flatMap((r) => [crumbSep(), placeLink(r)]));
  $("#place-name").textContent = h.name;
  $("#place-kind").textContent = SUBTYPE[refSt(h.ref)] || "";
  $("#place-asof").textContent = `As of ${shortDate(h.latest.date)}, ${h.latest.date.slice(0, 4)}, from the daily count of the whole world.`;
  renderCityCharts(h);
  renderQuestTable(shownSeries(h));
  const box = $("#place-children");
  box.replaceChildren();
  const items = await worldChildItems(h.ref).catch(() => []);
  const cf = items.length ? await worldJSON(h.latest.children + worldShard(h.id), h.latest.v) : null;
  if (seq !== placeSeq || page !== pageSeq) return;
  box.replaceChildren(...[cf && cf.places && worldKidsCard(h, items, cf), childrenCard(h.ref, items)].filter(Boolean));
}

// The name layer's places inside a place; a country's are its regions, and the places of its "_" file.
async function worldChildItems(ref) {
  if (ref.kind !== "country") return childRows(ref).map((i) => ({ ref: rowRef(ref.shard, i) }));
  const out = ref.country.regions.filter((r) => r.id !== "_").map((r) => ({ ref: { kind: "region", country: ref.country, region: r }, n: r.n }));
  const loose = ref.country.regions.find((r) => r.id === "_");
  const sh = loose && await loadShard(ref.country, loose).catch(() => null);
  if (sh) out.push(...sh.top.map((i) => ({ ref: rowRef(sh, i) })));
  return out;
}

// The children the world counts, with their open quests (the ticked ones) on the newest day and the change
// from latest.back: 4 weeks before, or the first published day when that is younger. In the children file a
// child's keys index the file's own quests list; a value is [open, aged, open on back, aged on back].
function worldKidsCard(h, items, cf) {
  const { date, back } = h.latest;
  const ticked = (cf.quests || []).map((q) => selected(q));
  const total = (qs, n) => Object.entries(qs).reduce((s, [k, v]) => s + (ticked[k] ? v[n] || 0 : 0), 0);
  const rows = items.filter((it) => cf.places[refId(it.ref)]).map((it) => {
    const qs = cf.places[refId(it.ref)];
    const open = total(qs, 0);
    return { ref: it.ref, open, change: back === date ? null : open - total(qs, 2) };
  }).sort((a, b) => b.open - a.open || refName(a.ref).localeCompare(refName(b.ref)));
  if (!rows.length) return null;
  const since = back === addDays(date, -WEEKS4) ? "Last 4 weeks" : `Since ${shortDate(back)}`;
  return el("article", { class: "card" },
    el("h2", {}, `Counted places inside ${h.name}`),
    el("p", { class: "sub" }, `Open quests in each on ${shortDate(date)}, counting ${selectionText()}. ` +
      "Places overlap and leave gaps, so they need not add up to the place they are in."),
    el("div", { class: "table-wrap" }, el("table", { class: "data parts" },
      el("thead", {}, el("tr", {}, el("th", { scope: "col" }, "Place"), el("th", { scope: "col" }, "Kind"),
        el("th", { scope: "col", class: "num" }, "Open"), el("th", { scope: "col", class: "num" }, since))),
      el("tbody", {}, rows.map((r) => el("tr", {},
        el("td", {}, placeLink(r.ref)),
        el("td", {}, SUBTYPE[refSt(r.ref)] || ""),
        el("td", { class: "num" }, nf.format(r.open)),
        el("td", { class: "num" }, r.change == null ? "—" : signed(r.change))))))));
}

// ---------- map view ----------
// What is counted, on a map: each city's boundary from coverage.json (DATA-FORMAT.md), joined by id to
// cities.json for its name and count. Everything not coloured is not counted. A city is a few pixels at
// the zoom that shows both continents, so it also has a dot, and each dot goes the moment its own city
// covers more of the screen than the dot does — small cities keep theirs longer than big ones.
// Leaflet is the one page's library, so it loads with the tab. It and uPlot are served from vendor/, the
// npm packages' own dist files (docs/vendor/README.md), so the page needs no CDN.

const LEAFLET = "vendor/leaflet-1.9.4/leaflet";
const DOT_RADIUS = 5;                   // px, plus the 1 px white ring
const DOT_AREA = Math.PI * (DOT_RADIUS + 1) ** 2;
let coverageMap = null;                 // promise of the Leaflet map, built the first time the tab opens

// A GeoJSON (Multi)Polygon's area in Web Mercator pixels at zoom 0; at zoom z it is this times 4^z, which
// is what the reader sees, unlike km² (a northern city looks bigger than its land).
function pixelAreaAtZoom0(geometry) {
  const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
  const ring = (coords) => {
    let twice = 0, prev = null;
    for (const [lon, lat] of coords) {
      const p = L.CRS.EPSG3857.latLngToPoint(L.latLng(lat, lon), 0);
      if (prev) twice += prev.x * p.y - p.x * prev.y;
      prev = p;
    }
    return Math.abs(twice) / 2;
  };
  return polygons.reduce((sum, [outer, ...holes]) =>
    sum + ring(outer) - holes.reduce((h, r) => h + ring(r), 0), 0);
}

function loadLeaflet() {
  const load = (tag, attrs) => new Promise((done, fail) => {
    const e = el(tag, attrs);
    e.onload = done;
    e.onerror = () => fail(new Error("the map library did not load"));
    document.head.append(e);
  });
  return Promise.all([
    load("link", { rel: "stylesheet", href: `${LEAFLET}.css` }),
    load("script", { src: `${LEAFLET}.js` }),
  ]);
}

function mapPopup(c) {
  return el("div", {}, el("b", {}, c.name), el("div", { class: "map-where" }, cityWhere(c)),
    el("div", {}, `${nf.format(c.open)} open quests`), cityLink(c, "See this city"));
}

async function buildMap() {
  const [coverage] = await Promise.all([getJSON("coverage.json"), loadLeaflet()]);
  const map = L.map("coverage-map", { minZoom: 1, zoomSnap: 0.5 });
  map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');   // the credit, without the flag
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);
  const colour = css("--series-1");
  map.createPane("dots").style.zIndex = 450;   // above the shapes, so a hovered shape brought forward stays under
  const shapes = L.featureGroup().addTo(map);
  const cityDots = [];                          // [dot, area at zoom 0]
  for (const f of coverage.features) {
    const c = cityById(f.id);
    if (!c) continue;
    const shape = L.geoJSON(f, { style: { color: colour, weight: 1.5, fillOpacity: 0.35, className: "city-shape" } }).addTo(shapes);
    const dot = L.circleMarker(shape.getBounds().getCenter(),
      { pane: "dots", radius: DOT_RADIUS, color: "#fff", weight: 1, fillColor: colour, fillOpacity: 1, className: "city-dot" });
    cityDots.push([dot, pixelAreaAtZoom0(f.geometry)]);
    // hovering either the shape or its dot lights up both: the dot says where, the shape says how much
    const hot = (on) => {
      shape.eachLayer((l) => l.getElement()?.classList.toggle("hot", on));
      dot.getElement()?.classList.toggle("hot", on);
      if (on) shape.bringToFront();
    };
    for (const layer of [shape, dot]) {
      layer.bindPopup(() => mapPopup(c));
      layer.on({ mouseover: () => hot(true), mouseout: () => hot(false) });
      if (!L.Browser.mobile) layer.bindTooltip(c.name, { sticky: true }).on("click", () => layer.closeTooltip());
    }
  }
  const showDots = () => {
    const scale = 4 ** map.getZoom();
    for (const [dot, area0] of cityDots) {
      if (area0 * scale < DOT_AREA) dot.addTo(map);
      else { dot.getElement()?.classList.remove("hot"); dot.remove(); }   // no mouseout comes once it is gone
    }
  };
  map.on("zoomend", showDots);
  const at = state.mapAt.split("/").map(Number);
  if (at.length === 3 && at.every(Number.isFinite)) map.setView(at.slice(1), at[0]);
  else map.fitBounds(shapes.getBounds(), { animate: false });
  showDots();
  map.on("moveend", () => {
    const { lat, lng } = map.getCenter();
    state.mapAt = `${map.getZoom()}/${lat.toFixed(4)}/${lng.toFixed(4)}`;
    writeURL();
  });
  return map;
}

async function renderMap() {
  const countries = new Set(cities.cities.map(cityCountry)).size;
  const land = cities.cities.reduce((sum, c) => sum + (c.landAreaKm2 || 0), 0);
  $("#map-sub").replaceChildren(
    `The coloured areas are counted: ${nf.format(cities.cities.length)} cities in ${nf.format(countries)} countries, ` +
    `${nf.format(Math.round(land))} km² of land. The rest of the world is not counted yet; `,
    el("a", { href: queryString({ ...state, view: "places" }), onclick: (e) => {
      if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      setView("places");
    } }, "find a place"), " to ask for it.");
  coverageMap ||= buildMap().catch((e) => { coverageMap = null; throw e; });
  (await coverageMap).invalidateSize();
}

// ---------- wiring ----------

function setStatus(msg) { const s = $("#status"); s.textContent = msg; s.hidden = !msg; }

function setView(v) {
  state.view = v;
  writeURL();
  render();
}

async function render() {
  for (const t of document.querySelectorAll(".tab")) {
    if (t.dataset.view === (state.view === "places" ? "city" : state.view)) t.setAttribute("aria-current", "page");
    else t.removeAttribute("aria-current");
  }
  const world = worldShown();   // a world place's numbers use the place page's layout
  $("#view-city").hidden = state.view !== "city" && !world;
  $("#view-compare").hidden = state.view !== "compare";
  $("#view-places").hidden = state.view !== "places" || world;
  $("#view-map").hidden = state.view !== "map";
  $("#city-filters").style.display = state.view === "compare" ? "" : "none";   // the place page has its own in its head
  setStatus("");
  try {
    if (state.view === "city") await renderCity();
    else if (state.view === "places") await renderPlaces();
    else if (state.view === "map") await renderMap();
    else await renderCompare();
  } catch (e) {
    setStatus(`Could not load data: ${e.message}`);
    console.error(e);
  }
}

function renderFooter() {
  const city = cities.cities.find((c) => c.id === state.city);
  const region = city && (cities.regions || []).find((r) => r.id === city.region);
  $("#foot-data").textContent =
    `Data as of ${cities.asOfDate} (${region ? region.source : "Geofabrik"} extract) · StreetComplete ${cities.scVersion} quest definitions · ` +
    `resurvey multiplier ×${cities.resurveyMultiplier ?? 1} · ${cities.cities.length} cities` +
    (city && city.asOfDate !== cities.asOfDate ? ` · ${city.name} last counted ${city.asOfDate}` : "");
}

function sortHandler(table, sortState, rerender) {
  $(table + " thead").addEventListener("click", (e) => {
    const th = e.target.closest("th[data-sort]");
    if (!th) return;
    const key = th.dataset.sort;
    const s = sortState();
    if (s.key === key) s.dir = -s.dir;
    else { s.key = key; s.dir = key === "name" ? 1 : -1; }
    rerender();
  });
}

async function main() {
  readURL();
  try {
    [cities, quests] = await Promise.all([getJSON("cities.json"), getJSON("quests.json")]);
  } catch (e) {
    setStatus(`No data yet (${e.message}). The first daily run publishes it.`);
    return;
  }
  questByName = new Map(quests.quests.map((q) => [q.name, q]));
  // Icons and release dates only decorate; the site works without them.
  const [ic, rel, first] = await Promise.all([
    fetch("icons/index.json").then((r) => (r.ok ? r.json() : null)).catch(() => null),
    getJSON("sc-releases.json").catch(() => null),
    getJSON("quest-releases.json").catch(() => null),
  ]);
  icons = (ic && ic.quests) || {};
  questFirst = (first && first.quests) || {};
  state.asThen = state.asThen && !!first;
  releases = ((rel && rel.releases) || []).map((r) => ({ ts: dayTs(r.date), version: r.version }))
    .map((r, i, all) => ({ ...r, major: isMajor(r, i, all) }));
  if (cityById(state.city)) setCity(state.city, state.part);   // a link's city counts as seen
  else {
    state.city = [...recentCities(), HOME_CITY].find(cityById) || cities.cities[0].id;
    state.part = "";
    showCity();
  }
  state.pinned = state.pinned.filter((n) => questByName.has(n));
  state.selected = resolveSelection(urlSelection);

  initCitySheet();

  const showRel = $("#show-releases");
  showRel.checked = state.releases;
  showRel.closest("label").hidden = !releases.length;
  showRel.addEventListener("change", () => { state.releases = showRel.checked; writeURL(); render(); });

  const asThen = $("#as-then");
  asThen.checked = state.asThen;
  asThen.closest("label").hidden = !first;
  asThen.addEventListener("change", () => { state.asThen = asThen.checked; writeURL(); render(); });

  $("#quest-filter").addEventListener("input", (e) => { state.filter = e.target.value; if (hist) renderQuestTable(shownSeries(hist)); });
  $("#range").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-range]");
    if (!b || b.dataset.range === state.range) return;
    state.range = b.dataset.range;
    writeURL();
    renderCity();
  });
  $("#place-change").addEventListener("click", () => $("#city-button").click());
  $("#select-shown").addEventListener("change", (e) => { if (hist) selectShown(e.target.checked); });
  $("#select-defaults").addEventListener("click", () => { state.selected = baseSet("app"); selectionChanged(); });
  $("#compare-quest").addEventListener("change", (e) => { state.compareQuest = e.target.value; writeURL(); renderCompare(); });
  for (const t of document.querySelectorAll(".tab"))
    t.addEventListener("click", (e) => { e.preventDefault(); setView(t.dataset.view); });

  let searchTimer = 0;
  $("#place-search").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(runSearch, 120); });
  $("#place-scope").addEventListener("change", (e) => { state.placeScope = e.target.value; runSearch(); });
  $("#place-results").addEventListener("click", (e) => {   // a result picked: the search has done its job
    if (e.target.closest("a") && e.defaultPrevented) { $("#place-search").value = ""; runSearch(); }
  });

  sortHandler("#quest-table", () => state.questSort, () => renderQuestTable(shownSeries(hist)));
  sortHandler("#compare-table", () => state.compareSort, renderCompare);

  renderFooter();
  writeURL();
  await render();
}

main();
