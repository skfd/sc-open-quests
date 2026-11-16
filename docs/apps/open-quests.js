// Variables used by Scriptable.
// These must be at the very top of the file. Do not edit.
// icon-color: deep-blue; icon-glyph: map-marked-alt;

// Open Quests for StreetComplete — an iPhone home-screen widget for the Scriptable app.
//
// How many StreetComplete quests are open in a city or one of its neighbourhoods, or for one quest type
// there, how that moved over four weeks, and which quests moved this week. Data:
// https://street-complete-statistics.comentality.com (a day or more old: the widget always says "as of").
//
// Install: get Scriptable from the App Store, put this file in Scriptable (iCloud Drive › Scriptable,
// or paste it into a new script), add a Scriptable widget to the home screen, long-press it › Edit
// Widget, pick this script and type a city as the Parameter: "Berlin", "Toronto/Parkdale" for a
// neighbourhood, and "; Bus stop shelter" after either for one quest type. No parameter shows Toronto.
// Small, medium and large work, and the lock screen's rectangular and inline slots.
//
// A port of the Android widget's model (Summary.kt, Movers.kt), pinned on the same fixtures by
// ios/test/model.test.js. GPL-3.0. Quest names are StreetComplete's (Tobias Zwick and contributors).

const BASE = "https://street-complete-statistics.comentality.com";
const DEFAULT_CITY = "Toronto";
const VERSION = "0.1.0";

// ---------------------------------------------------------------------------------------------------
// Model: plain JavaScript, no Scriptable API, so Node can test it.

/** Days since 1970-01-01 for an ISO yyyy-mm-dd date. */
function epochDay(iso) {
  return Math.round(Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) / 86400000);
}

/**
 * One city's series from data/history/<cityId>.json, or one part's from data/history/<cityId>/<partId>.json
 * (the same shape, plus the part's id and the name-layer file the site finds it by). A missing count
 * stays null, never 0.
 */
function parseHistory(json) {
  const root = typeof json === "string" ? JSON.parse(json) : json;
  const n = root.dates.length;
  const quests = {};
  for (const name of Object.keys(root.quests)) {
    const q = root.quests[name];
    const fill = (a) => Array.from({ length: n }, (_, i) => (a && i < a.length && a[i] != null ? a[i] : null));
    quests[name] = { open: fill(q.open), agedOnly: fill(q.agedOnly) };
  }
  const part = root.part ? { id: root.part, in: root.in || null } : null;
  return { cityId: root.city || "", name: root.en || root.name || "", part, dates: root.dates, quests };
}

/** The names of the quests on by default, from the site's data/quests.json. */
function parseDefaultOn(json) {
  const root = typeof json === "string" ? JSON.parse(json) : json;
  return new Set(root.quests.filter((q) => !q.defaultDisabled).map((q) => q.name));
}

const WINDOW_DAYS = 28;
const SLACK_DAYS = 2;

/**
 * The headline, the change over four weeks and its split, and the sparkline's points. [quest]: one
 * quest type, counted whether or not it is on by default; null counts every quest on by default, as
 * the site's headline does. Null when the city or quest has no data.
 */
function summarize(h, defaultOn, quest = null, windowDays = WINDOW_DAYS) {
  if (h.dates.length === 0) return null;
  const b = h.dates.length - 1;
  const last = epochDay(h.dates[b]);
  const first = last - windowDays;
  const on = Object.keys(h.quests)
    .filter((k) => (quest == null ? defaultOn.has(k) : k === quest))
    .map((k) => h.quests[k]);
  if (quest != null && on.every((s) => s.open[b] == null)) return null;
  // One quest type new in the window starts where it was first counted, not at a zero.
  let a = 0;
  while (a < b && !(epochDay(h.dates[a]) >= first && (quest == null || on[0].open[a] != null))) a++;
  const sum = (list, f) => list.reduce((t, s) => t + (f(s) || 0), 0);
  const open = sum(on, (s) => s.open[b]);
  const aged = sum(on, (s) => s.agedOnly[b]);

  // Like for like: a quest new since the window began must not show up as a rise.
  const both = on.filter((s) => s.open[a] != null && s.open[b] != null);
  const total = (i) => sum(both, (s) => s.open[i]);
  const agedTotal = (i) => sum(both, (s) => s.agedOnly[i]);
  const change = total(b) - total(a);
  const resurvey = agedTotal(b) - agedTotal(a);

  const points = [];
  for (let i = a; i <= b; i++) {
    // A day on which a counted quest is missing is left out rather than drawn as a dip.
    if (both.every((s) => s.open[i] != null)) points.push({ day: epochDay(h.dates[i]) - first, value: total(i) });
  }
  return {
    cityId: h.cityId,
    name: h.name,
    part: h.part || null,
    quest,
    asOf: h.dates[b],
    open,
    agedOnly: aged,
    since: h.dates[a],
    fullWindow: epochDay(h.dates[a]) - first <= SLACK_DAYS,
    change,
    mapChange: change - resurvey,
    resurveyChange: resurvey,
    windowDays,
    points,
  };
}

// "Moving this week" (README, Movers.kt): the newest date against 7 days before (6, else 8), quests on
// by default counted at both ends; a rise shows at max(20, 5% of max(start, 200)), a drop at
// max(50, 5% of max(start, 500)); quests that moved together (same sign, within 25% of the lead's
// change, day-to-day steps correlated at r >= 0.9) are one group.
const RISE = { floor: 20, share: 0.05, minBase: 200 };
const DROP = { floor: 50, share: 0.05, minBase: 500 };
const LOOKBACK_DAYS = [7, 6, 8];

function threshold(rule, start) {
  return Math.max(rule.floor, rule.share * Math.max(start, rule.minBase));
}

function movers(h, defaultOn, asOf = null) {
  const b = asOf == null ? h.dates.length - 1 : h.dates.indexOf(asOf);
  if (b < 0) throw new Error(`${asOf} is not a date in history ${h.cityId}`);
  const days = h.dates.map(epochDay);
  const t = days[b];
  let a = null;
  for (const back of LOOKBACK_DAYS) {
    for (let i = 0; i < b; i++) {
      if (t - days[i] === back) { a = i; break; }
    }
    if (a != null) break;
  }

  // Name order (as the site writes them) settles ties the same way as the mockup.
  const names = Object.keys(h.quests).filter((n) => defaultOn.has(n)).sort();
  const top = names
    .filter((n) => h.quests[n].open[b] != null)
    .map((n) => [n, h.quests[n].open[b]])
    .sort((x, y) => y[1] - x[1]) // stable: ties stay in name order
    .slice(0, 3);
  if (a == null) return { asOf: h.dates[b], since: null, groups: [], top };

  const candidates = [];
  for (const n of names) {
    const s = h.quests[n];
    const start = s.open[a];
    const end = s.open[b];
    if (start == null || end == null) continue;
    const dv = end - start;
    if (dv === 0) continue;
    if (Math.abs(dv) < threshold(dv > 0 ? RISE : DROP, start)) continue;
    // A missing day inside the week counts as 0 here, as in the mockup.
    const steps = [];
    for (let i = a; i < b; i++) steps.push((s.open[i + 1] || 0) - (s.open[i] || 0));
    const agedDv = (s.agedOnly[b] || 0) - (s.agedOnly[a] || 0);
    candidates.push({ quest: n, change: dv, aging: dv > 0 && agedDv >= 0.6 * dv, steps });
  }

  const groups = [];
  const bySize = candidates.slice().sort((x, y) => Math.abs(y.change) - Math.abs(x.change));
  for (const m of bySize) {
    const home = groups.find((g) => {
      const lead = g[0];
      return m.change * lead.change > 0 &&
        Math.abs(Math.abs(m.change) - Math.abs(lead.change)) <= 0.25 * Math.abs(lead.change) &&
        correlation(m.steps, lead.steps) >= 0.9;
    });
    if (home) home.push(m); else groups.push([m]);
  }
  // Rises first (they are the news), each side by severity.
  groups.sort((x, y) => (x[0].change < 0) - (y[0].change < 0) || Math.abs(y[0].change) - Math.abs(x[0].change));
  return {
    asOf: h.dates[b],
    since: h.dates[a],
    groups: groups.map((g) => g.map(({ quest, change, aging }) => ({ quest, change, aging }))),
    top,
  };
}

/** Pearson's r; where Python's statistics.correlation raises, 1.0 if the lists are equal, else 0.0. */
function correlation(x, y) {
  const n = x.length;
  let sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0;
  for (let i = 0; i < n; i++) {
    sx += x[i]; sy += y[i]; sxx += x[i] * x[i]; syy += y[i] * y[i]; sxy += x[i] * y[i];
  }
  const cxx = n * sxx - sx * sx;
  const cyy = n * syy - sy * sy;
  const cxy = n * sxy - sx * sy;
  if (n < 2 || cxx === 0 || cyy === 0) return x.length === y.length && x.every((v, i) => v === y[i]) ? 1 : 0;
  return cxy / (Math.sqrt(cxx) * Math.sqrt(cyy));
}

/** 1 chevron below 100, 2 below 300, 3 from 300, from the lead's |change|. */
function chevrons(group) {
  const c = Math.abs(group[0].change);
  return c < 100 ? 1 : c < 300 ? 2 : 3;
}

/** "AddBusStopShelter" -> "Bus stop shelter"; "OsmNoteQuestType" -> "Notes". */
function questLabel(name) {
  if (name === "OsmNoteQuestType") return "Notes";
  const isUpper = (c) => c !== c.toLowerCase() && c === c.toUpperCase();
  const isLower = (c) => c !== c.toUpperCase() && c === c.toLowerCase();
  let out = "";
  for (let i = 0; i < name.length; i++) {
    const ch = name[i];
    if (isUpper(ch) && i > 0 && (isLower(name[i - 1]) || (i + 1 < name.length && isLower(name[i + 1])))) out += " ";
    out += ch;
  }
  let words = out.split(" ").filter((w) => w);
  if (words[0] === "Add" && words.length > 1) words = words.slice(1);
  if (words.length === 0) return name;
  return [words[0], ...words.slice(1).map((w) => w.toLowerCase())].join(" ");
}

/** The words all members' labels share (bar "on" and "status"), else the lead's label. */
function groupLabel(group) {
  if (group.length === 1) return questLabel(group[0].quest);
  const sets = group.map((m) => questLabel(m.quest).toLowerCase().split(" ").filter((w) => w));
  const words = sets[0].filter((w) => sets.slice(1).every((s) => s.includes(w)) && w !== "on" && w !== "status");
  if (words.length === 0) return questLabel(group[0].quest);
  const s = words.join(" ");
  return s[0].toUpperCase() + s.slice(1);
}

function formatCount(n, locale) {
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(n).replace("-", "−");
}

/** "+234", "−923", "0". A typographic minus, as on the site. */
function formatSigned(n, locale) {
  return (n > 0 ? "+" : "") + formatCount(n, locale);
}

/** Python's round(): half to even. */
function roundHalfEven(x) {
  const r = Math.round(x);
  return Math.abs(x % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r;
}

/** Two significant figures, signed: 125 -> "+120", as the mockup's about(). */
function about(n, locale) {
  const m = Math.abs(n);
  const digits = String(Math.trunc(m)).length;
  const k = Math.pow(10, Math.max(digits - 2, 0));
  return (n > 0 ? "+" : "−") + formatCount(roundHalfEven(m / k) * k, locale);
}

function median(values) {
  const s = values.slice().sort((x, y) => x - y);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 === 1 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

/** The lead's signed change for one quest; for several, about(median), and the caller adds "each". */
function groupChangeText(group, locale) {
  return group.length === 1 ? formatSigned(group[0].change, locale) : about(median(group.map((m) => m.change)), locale);
}

/** True once the newest date is more than 3 days old: a site or phone that stopped is not current. */
function isStale(asOf, now = new Date()) {
  const today = epochDay(now.toISOString().slice(0, 10));
  return today - epochDay(asOf) > 3;
}

/** "2026-11-10" -> "11-10". */
function shortDate(iso) {
  return iso.slice(5);
}

/** "−689 in 4 wk", or "+40 since 10-27" when the data does not reach back four weeks. */
function chipText(s, locale) {
  return formatSigned(s.change, locale) + (s.fullWindow ? " in 4 wk" : ` since ${shortDate(s.since)}`);
}

function splitText(s, locale) {
  return `map ${formatSigned(s.mapChange, locale)} · resurvey ${formatSigned(s.resurveyChange, locale)}`;
}

/** "Montréal" -> "montreal". */
function fold(s) {
  return s.normalize("NFD").replace(/\p{Mn}+/gu, "").toLowerCase();
}

/** The cities in data/cities.json: id, name, group, aka. */
function parseCities(json) {
  const root = typeof json === "string" ? JSON.parse(json) : json;
  const regionGroup = {};
  for (const r of root.regions || []) regionGroup[r.id] = r.group || r.name;
  return root.cities.map((c) => ({
    id: c.id,
    name: c.name,
    group: c.group || regionGroup[c.region] || "",
    aka: c.aka || [],
  }));
}

/**
 * The city a widget parameter names: an exact name, aka or id first (ignoring case and accents), then
 * the first city a word of whose name or aka starts with it. Null when none does.
 */
function findCity(cities, query) {
  const q = fold(query.trim());
  if (!q) return null;
  const exact = cities.find((c) => [c.name, c.id, ...c.aka].some((x) => fold(x) === q));
  if (exact) return exact;
  return cities.find((c) => [c.name, ...c.aka].some((x) => {
    const f = fold(x);
    return f.startsWith(q) || f.split(/[ \-(/]/).some((w) => w.startsWith(q));
  })) || null;
}

/** The quest type a parameter names, by class name or label ("AddBusStopShelter", "bus stop shelter"). */
function findQuest(h, query) {
  const q = fold(query.trim()).replace(/\s+/g, " ");
  if (!q) return null;
  const names = Object.keys(h.quests).sort();
  return names.find((n) => n.toLowerCase() === q) ||
    names.find((n) => fold(questLabel(n)) === q) ||
    names.find((n) => fold(questLabel(n)).startsWith(q)) ||
    null;
}

/** The parts (neighbourhoods) in data/parts/<cityId>.json: id, name, en. */
function parseParts(json) {
  const root = typeof json === "string" ? JSON.parse(json) : json;
  return root.parts.map((p) => ({ id: p.id, name: p.name, en: p.en || null }));
}

/**
 * The part a parameter names, as findCity does: an exact name, English name or id first, then the first
 * whose name starts with it, then one with a word that does. "Parkdale" is Parkdale, not South Parkdale.
 */
function findPart(parts, query) {
  const q = fold(query.trim()).replace(/\s+/g, " ");
  if (!q) return null;
  const names = (p) => [p.name, p.en].filter(Boolean).map(fold);
  return parts.find((p) => p.id === q || names(p).some((x) => x === q)) ||
    parts.find((p) => names(p).some((x) => x.startsWith(q))) ||
    parts.find((p) => names(p).some((x) => [...x].some((ch, i) => /[ \-(/—–]/.test(ch) && x.startsWith(q, i + 1)))) ||
    null;
}

/**
 * "Toronto/Parkdale; Bus stop shelter" -> { city: "Toronto", part: "Parkdale", quest: "Bus stop shelter" }.
 * ";" or "|" starts the quest type; the first "/", "›" or ">" the part (part names may hold a "/").
 */
function parseParameter(p) {
  const [place, quest] = String(p || "").split(/[;|]/, 2).map((s) => s.trim());
  const cut = (place || "").search(/[/›>]/);
  const city = (cut < 0 ? place : place.slice(0, cut)).trim();
  const part = cut < 0 ? "" : place.slice(cut + 1).trim();
  return { city: city || DEFAULT_CITY, part: part || null, quest: quest || null };
}

/** The site's page for the city, or for the part when [part] ({ id, in }) is given. */
function placeUrl(cityId, quest, part = null) {
  if (part && part.in) return `${BASE}/?place=${encodeURIComponent(part.id)}&in=${encodeURIComponent(part.in)}`;
  return `${BASE}/?city=${encodeURIComponent(cityId)}` + (quest ? `&pin=${encodeURIComponent(quest)}` : "");
}

// ---------------------------------------------------------------------------------------------------
// Data: fetched with conditional requests, kept on the phone, used stale when the network fails.

const HOUR = 3600 * 1000;

async function cached(fm, dir, key, url, maxAgeMs, derive) {
  const body = fm.joinPath(dir, key + ".json");
  const meta = fm.joinPath(dir, key + ".meta.json");
  const have = fm.fileExists(body) && fm.fileExists(meta);
  const info = have ? JSON.parse(fm.readString(meta)) : null;
  if (info && Date.now() - info.fetched < maxAgeMs) return JSON.parse(fm.readString(body));
  try {
    const req = new Request(url);
    req.timeoutInterval = 20;
    if (info && info.etag) req.headers = { "If-None-Match": info.etag };
    const text = await req.loadString();
    const status = req.response.statusCode;
    if (status === 304 && have) {
      fm.writeString(meta, JSON.stringify({ ...info, fetched: Date.now() }));
      return JSON.parse(fm.readString(body));
    }
    if (status !== 200) throw new Error(`HTTP ${status}`);
    const value = derive(text);
    const headers = req.response.headers || {};
    const etag = headers.ETag || headers.Etag || headers.etag || null;
    fm.writeString(body, JSON.stringify(value));
    fm.writeString(meta, JSON.stringify({ fetched: Date.now(), etag }));
    return value;
  } catch (e) {
    if (have) return JSON.parse(fm.readString(body));
    throw e;
  }
}

async function load(param) {
  const fm = FileManager.local();
  const dir = fm.joinPath(fm.documentsDirectory(), "open-quests");
  if (!fm.fileExists(dir)) fm.createDirectory(dir, true);
  const p = parseParameter(param);

  const cities = await cached(fm, dir, "cities", `${BASE}/data/cities.json`, 24 * HOUR, (t) => parseCities(t));
  const city = findCity(cities, p.city);
  if (!city) return { error: `No city called “${p.city}”.`, hint: "Long-press › Edit Widget › Parameter" };
  // Only the set is kept: quests.json is 742 KB, mostly per-city status the widget does not need.
  const defaultOn = new Set(await cached(fm, dir, "default-on", `${BASE}/data/quests.json`, 24 * HOUR,
    (t) => [...parseDefaultOn(t)]));
  let place = city.name;
  let key = city.id;
  let url = `${BASE}/data/history/${encodeURIComponent(city.id)}.json`;
  if (p.part) {
    let parts;
    try {
      parts = await cached(fm, dir, "parts-" + city.id, `${BASE}/data/parts/${encodeURIComponent(city.id)}.json`,
        24 * HOUR, (t) => parseParts(t));
    } catch (e) {
      if (/HTTP 404/.test(String(e.message))) return { error: `${city.name} has no neighbourhoods counted.` };
      throw e;
    }
    const part = findPart(parts, p.part);
    if (!part) return { error: `No neighbourhood “${p.part}” in ${city.name}.`, hint: "Its name as on the city’s page" };
    place = part.en || part.name;
    key = `${city.id}-${part.id}`;
    url = `${BASE}/data/history/${encodeURIComponent(city.id)}/${encodeURIComponent(part.id)}.json`;
  }
  let raw;
  try {
    raw = await cached(fm, dir, "history-" + key, url, 2 * HOUR, (t) => JSON.parse(t));
  } catch (e) {
    if (p.part && /HTTP 404/.test(String(e.message))) return { error: `No data for ${place} yet.` };
    throw e;
  }
  const h = parseHistory(raw);
  if (!h.name) h.name = place;
  if (!h.cityId) h.cityId = city.id;

  let quest = null;
  if (p.quest) {
    quest = findQuest(h, p.quest);
    if (!quest) return { error: `No quest “${p.quest}” in ${place}.`, hint: "Try its name as on the site" };
  }
  const summary = summarize(h, defaultOn, quest);
  if (!summary && quest) return { error: `${questLabel(quest)} is not counted in ${place} now.`, hint: "Long-press › Edit Widget to pick another" };
  if (!summary) return { error: `No data for ${place} yet.` };
  const week = quest ? null : movers(h, defaultOn);
  const wanted = quest ? [quest]
    : [...week.groups.slice(0, 6).map((g) => g[0].quest), ...week.top.map((t) => t[0])];
  return { summary, week, icons: await loadIcons(fm, dir, wanted) };
}

/**
 * StreetComplete's quest symbols, as the PNGs the site draws from its SVGs (Scriptable shows no
 * SVG): fetched once each and kept. An icon that can't be had is left out, and names stand in.
 */
async function loadIcons(fm, dir, quests) {
  const out = {};
  let index;
  try {
    index = await cached(fm, dir, "icon-index", `${BASE}/icons/index.json`, 7 * 24 * HOUR, (t) => {
      const q = JSON.parse(t).quests;
      const stems = {};
      for (const k of Object.keys(q)) if (q[k].icon) stems[k] = q[k].icon.replace(/\.svg$/, "");
      return stems;
    });
  } catch (e) {
    return out;
  }
  const idir = fm.joinPath(dir, "icons");
  if (!fm.fileExists(idir)) fm.createDirectory(idir, true);
  await Promise.all([...new Set(quests)].map(async (quest) => {
    const stem = index[quest];
    if (!stem) return;
    const file = fm.joinPath(idir, stem + ".png");
    try {
      if (!fm.fileExists(file)) {
        const req = new Request(`${BASE}/icons/png/${encodeURIComponent(stem)}.png`);
        req.timeoutInterval = 15;
        const img = await req.loadImage();
        if (req.response.statusCode !== 200) return;
        fm.writeImage(file, img);
      }
      out[quest] = fm.readImage(file);
    } catch (e) { /* no icon: the name stands in */ }
  }));
  return out;
}

// ---------------------------------------------------------------------------------------------------
// Widget.

const C = typeof Color === "undefined" ? null : {
  bg: Color.dynamic(new Color("#EEF0FF"), new Color("#262A3B")),
  text: Color.dynamic(new Color("#1B1B21"), new Color("#E4E1EC")),
  muted: Color.dynamic(new Color("#5B5D72"), new Color("#A9ABC2")),
  chipBg: Color.dynamic(new Color("#DDE1F9"), new Color("#3A3F57")),
  chipFg: Color.dynamic(new Color("#1B1B21"), new Color("#E4E1EC")),
  fallingBg: Color.dynamic(new Color("#C8E6C9"), new Color("#2E7D32")),
  fallingFg: Color.dynamic(new Color("#1B5E20"), new Color("#FFFFFF")),
  rise: Color.dynamic(new Color("#B07A00"), new Color("#FFD75E")),
  aging: Color.dynamic(new Color("#D84315"), new Color("#FF8A50")),
  drop: Color.dynamic(new Color("#2E7D32"), new Color("#7BD88F")),
  stale: Color.dynamic(new Color("#BA1A1A"), new Color("#FFB4AB")),
  // The sparkline is a picture, drawn before iOS knows day from night: one tone that reads on both.
  line: new Color("#7C80C8"),
};

function text(stack, s, font, color, lines = 1) {
  const t = stack.addText(s);
  t.font = font;
  t.textColor = color;
  t.lineLimit = lines;
  return t;
}

/** The icons load() fetched, by quest name; set by makeWidget. */
let ICONS = {};

function title(s) {
  return s.quest ? `${questLabel(s.quest)} · ${s.name}` : s.name;
}

/** A quest's symbol at [size] pt, if there is one; true when it was added. */
function icon(stack, quest, size, gap) {
  const img = ICONS[quest];
  if (!img) return false;
  const i = stack.addImage(img);
  i.imageSize = new Size(size, size);
  if (gap) stack.addSpacer(gap);
  return true;
}

/** "Bus stop shelter · Berlin", with the quest's symbol first when it is one quest. */
function titleRow(stack, s, size) {
  const row = stack.addStack();
  row.centerAlignContent();
  if (s.quest) icon(row, s.quest, size + 2, 5);
  text(row, title(s), Font.mediumSystemFont(size), C.muted).minimumScaleFactor = 0.8;
  return row;
}

function chip(stack, s, locale, size) {
  const c = stack.addStack();
  c.setPadding(3, 7, 3, 7);
  c.cornerRadius = 9;
  const falling = s.change < 0;
  c.backgroundColor = falling ? C.fallingBg : C.chipBg;
  const t = text(c, chipText(s, locale), Font.semiboldSystemFont(size), falling ? C.fallingFg : C.chipFg);
  t.minimumScaleFactor = 0.7;
}

function sparkline(s, width, height) {
  const ctx = new DrawContext();
  ctx.size = new Size(width, height);
  ctx.opaque = false;
  ctx.respectScreenScale = true;
  const pts = s.points;
  if (pts.length === 0) return ctx.getImage();
  let lo = Math.min(...pts.map((p) => p.value));
  let hi = Math.max(...pts.map((p) => p.value));
  // Never zoom closer than 0.5% of the total (at least 20 quests), so a wobble is not a cliff.
  const floor = Math.max(20, 0.005 * s.open);
  if (hi - lo < floor) { const mid = (hi + lo) / 2; lo = mid - floor / 2; hi = mid + floor / 2; }
  const pad = 4;
  const x = (d) => pad + (width - 2 * pad) * d / s.windowDays;
  const y = (v) => pad + (height - 2 * pad) * (1 - (v - lo) / (hi - lo));
  ctx.setStrokeColor(C.line);
  for (let i = 1; i < pts.length; i++) {
    const gap = pts[i].day - pts[i - 1].day;
    if (gap > 2) continue; // a longer gap stays open
    const path = new Path();
    path.move(new Point(x(pts[i - 1].day), y(pts[i - 1].value)));
    path.addLine(new Point(x(pts[i].day), y(pts[i].value)));
    ctx.addPath(path);
    ctx.setLineWidth(gap === 1 ? 2 : 1); // one missing day: a faint bridge, never a value
    ctx.strokePath();
  }
  ctx.setFillColor(C.line);
  for (const p of pts) ctx.fillEllipse(new Rect(x(p.day) - 2, y(p.value) - 2, 4, 4));
  return ctx.getImage();
}

/**
 * The sparkline, drawn wide and scaled down by iOS to the width the widget has: a medium widget is
 * 292pt wide on an iPhone SE and 364pt on a Pro Max, so no one fixed width fits.
 */
function addSparkline(w, s, height) {
  const img = w.addImage(sparkline(s, 340, height));
  img.resizable = true;
  img.centerAlignImage();
}

function arrows(group) {
  return (group[0].change > 0 ? "▲" : "▼").repeat(chevrons(group));
}

function arrowColor(group) {
  return group[0].change < 0 ? C.drop : group[0].aging ? C.aging : C.rise;
}

/** One line of this week's movers: "▲▲ Cycleway part surface +313 · 3 more". */
function moverLine(stack, week, locale, size) {
  const g = week.groups[0];
  const row = stack.addStack();
  row.centerAlignContent();
  text(row, arrows(g) + " ", Font.boldSystemFont(size - 2), arrowColor(g));
  const more = week.groups.length - 1;
  text(row, `${groupLabel(g)} ${groupChangeText(g, locale)}${g.length > 1 ? " each" : ""}` +
    (more > 0 ? ` · ${more} more` : ""), Font.systemFont(size), C.muted).minimumScaleFactor = 0.8;
}

/**
 * This week's movers as symbols, chevrons beside each, as many as [max], then "+N": the Android 4x2's
 * cells. False, drawing nothing, when a shown group's symbol is missing.
 */
function moverIcons(stack, week, max) {
  const shown = week.groups.slice(0, max);
  if (shown.some((g) => !ICONS[g[0].quest])) return false;
  const row = stack.addStack();
  row.centerAlignContent();
  shown.forEach((g, i) => {
    if (i > 0) row.addSpacer(7);
    text(row, arrows(g), Font.boldSystemFont(9), arrowColor(g));
    row.addSpacer(2);
    icon(row, g[0].quest, 20);
  });
  const more = week.groups.length - shown.length;
  if (more > 0) { row.addSpacer(5); text(row, `+${more}`, Font.mediumSystemFont(12), C.muted); }
  return true;
}

/** "as of 11-10", in the error colour once it is stale. */
function asOf(stack, s, size) {
  text(stack, `as of ${shortDate(s.asOf)}`, Font.systemFont(size), isStale(s.asOf) ? C.stale : C.muted);
}

function header(w, s, locale, chipSize) {
  const row = w.addStack();
  row.centerAlignContent();
  titleRow(row, s, 15);
  row.addSpacer();
  chip(row, s, locale, chipSize);
}

function bigNumber(w, s, locale, size) {
  const t = text(w, formatCount(s.open, locale), Font.boldRoundedSystemFont(size), C.text);
  t.minimumScaleFactor = 0.5;
}

function footer(w, s, week, locale) {
  const row = w.addStack();
  row.centerAlignContent();
  asOf(row, s, 12);
  row.addSpacer();
  if (week && week.groups.length > 0) { if (!moverIcons(row, week, 4)) moverLine(row, week, locale, 12); }
  else text(row, splitText(s, locale), Font.systemFont(12), C.muted).minimumScaleFactor = 0.8;
}

function buildSmall(w, s, week, locale) {
  titleRow(w, s, 14);
  bigNumber(w, s, locale, 34);
  w.addSpacer(4);
  const row = w.addStack();
  chip(row, s, locale, 13);
  row.addSpacer();
  w.addSpacer();
  asOf(w, s, 11);
}

function buildMedium(w, s, week, locale) {
  header(w, s, locale, 13);
  bigNumber(w, s, locale, 34);
  w.addSpacer();
  addSparkline(w, s, 44);
  w.addSpacer();
  footer(w, s, week, locale);
}

function buildLarge(w, s, week, locale) {
  header(w, s, locale, 14);
  bigNumber(w, s, locale, 40);
  w.addSpacer(6);
  // One quest type has no "this week" section: the line takes its room.
  addSparkline(w, s, week ? 96 : 200);
  w.addSpacer(6);
  const foot = w.addStack();
  asOf(foot, s, 12);
  foot.addSpacer();
  text(foot, splitText(s, locale), Font.systemFont(12), C.muted).minimumScaleFactor = 0.8;
  w.addSpacer(8);
  w.addSpacer();
  if (!week) return;
  const rows = 3; // as the Android 4x3
  const heading = w.addStack();
  if (week.groups.length > 0) {
    text(heading, "This week", Font.semiboldSystemFont(14), C.text);
    const more = week.groups.length - rows;
    if (more > 0) text(heading, ` · ${more} more`, Font.systemFont(14), C.muted);
    for (const g of week.groups.slice(0, rows)) {
      w.addSpacer(4);
      const row = w.addStack();
      row.centerAlignContent();
      icon(row, g[0].quest, 20, 7);
      text(row, groupLabel(g) + (g.length > 1 ? ` · ${g.length}` : ""), Font.systemFont(14), C.text)
        .minimumScaleFactor = 0.8;
      row.addSpacer();
      text(row, arrows(g) + " ", Font.boldSystemFont(11), arrowColor(g));
      text(row, groupChangeText(g, locale) + (g.length > 1 ? " each" : ""), Font.semiboldSystemFont(14), arrowColor(g));
    }
  } else {
    text(heading, "Most open", Font.semiboldSystemFont(14), C.text);
    text(heading, " · a quiet week", Font.systemFont(14), C.muted);
    for (const [quest, open] of week.top) {
      w.addSpacer(4);
      const row = w.addStack();
      row.centerAlignContent();
      icon(row, quest, 20, 7);
      text(row, questLabel(quest), Font.systemFont(14), C.text).minimumScaleFactor = 0.8;
      row.addSpacer();
      text(row, formatCount(open, locale), Font.semiboldSystemFont(14), C.muted);
    }
  }
}

function buildAccessory(w, s, locale, family) {
  if (family === "accessoryInline") {
    w.addText(`${s.name} ${formatCount(s.open, locale)} ${formatSigned(s.change, locale)}`);
    return;
  }
  if (family === "accessoryCircular") {
    const t = w.addText(s.open >= 10000 ? Math.round(s.open / 1000) + "k" : formatCount(s.open, locale));
    t.font = Font.boldRoundedSystemFont(16);
    t.minimumScaleFactor = 0.5;
    return;
  }
  text(w, title(s), Font.mediumSystemFont(12), Color.white()).minimumScaleFactor = 0.8;
  text(w, formatCount(s.open, locale), Font.boldRoundedSystemFont(22), Color.white()).minimumScaleFactor = 0.6;
  text(w, chipText(s, locale), Font.systemFont(12), Color.white()).minimumScaleFactor = 0.8;
}

function buildError(w, result) {
  text(w, "Open Quests", Font.mediumSystemFont(14), C.muted);
  w.addSpacer(6);
  text(w, result.error, Font.semiboldSystemFont(15), C.text, 3);
  if (result.hint) { w.addSpacer(4); text(w, result.hint, Font.systemFont(12), C.muted, 2); }
}

async function makeWidget(param, family) {
  const w = new ListWidget();
  const accessory = family && family.startsWith("accessory");
  if (!accessory) { w.backgroundColor = C.bg; w.setPadding(14, 16, 14, 16); }
  let locale = "en-US";
  try {
    const tag = Device.locale().replace(/_/g, "-");
    new Intl.NumberFormat(tag);
    locale = tag;
  } catch (e) { /* a tag Intl rejects: keep en-US */ }
  let result;
  try {
    result = await load(param);
  } catch (e) {
    result = { error: "Couldn’t reach the site, and nothing is saved yet.", hint: String(e.message || e) };
  }
  if (result.error) {
    if (!accessory) buildError(w, result); else w.addText(result.error);
    w.refreshAfterDate = new Date(Date.now() + HOUR);
    return w;
  }
  const s = result.summary;
  ICONS = result.icons || {};
  w.url = placeUrl(s.cityId, s.quest, s.part);
  if (accessory) buildAccessory(w, s, locale, family);
  else if (family === "small") buildSmall(w, s, result.week, locale);
  else if (family === "large" || family === "extraLarge") buildLarge(w, s, result.week, locale);
  else buildMedium(w, s, result.week, locale);
  // The site publishes once a day (about 13:00 Toronto); iOS decides when this really runs.
  w.refreshAfterDate = new Date(Date.now() + 3 * HOUR);
  return w;
}

async function runInApp() {
  const ask = new Alert();
  ask.title = "Open Quests";
  ask.message = "Preview a widget. A city, “city/neighbourhood”, and “; quest type” after either.";
  ask.addTextField("Toronto", DEFAULT_CITY);
  for (const size of ["Small", "Medium", "Large"]) ask.addAction(size);
  ask.addCancelAction("Cancel");
  const choice = await ask.present();
  if (choice < 0) return;
  const family = ["small", "medium", "large"][choice];
  const w = await makeWidget(ask.textFieldValue(0), family);
  if (family === "small") await w.presentSmall();
  else if (family === "large") await w.presentLarge();
  else await w.presentMedium();
}

// ---------------------------------------------------------------------------------------------------
// Entry. The tests and the preview cut the file here (ios/test/load.js) and run everything above.

if (config.runsInWidget) {
  Script.setWidget(await makeWidget(args.widgetParameter, config.widgetFamily));
} else {
  await runInApp();
}
Script.complete();
