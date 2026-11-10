// sc-open-quests site. Reads the JSON described in DATA-FORMAT.md; no build step.
// ?data=<path> points it at another data directory (the test fixtures use this).
"use strict";

const DATA = (new URLSearchParams(location.search).get("data") || "data").replace(/\/$/, "");
const MAX_PINNED = 6;
const nf = new Intl.NumberFormat("en-CA");
const nf1 = new Intl.NumberFormat("en-CA", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const nfShort = new Intl.NumberFormat("en-CA", { notation: "compact", maximumSignificantDigits: 3 });
const HOME_CITY = "guelph";                 // the first visit's city
const RECENT_KEY = "sc-open-quests-cities"; // localStorage: the reader's cities, the last first
const MAX_RECENT = 5;

const state = {
  view: "city",
  city: "",                         // from the link, else the last city seen, else HOME_CITY
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
let cities, quests, questByName, hist;   // loaded data
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
// A place link names the place and its region file only; the city is left out, so the link stays short.
function queryString(s = state) {
  const p = new URLSearchParams();
  const data = new URLSearchParams(location.search).get("data");
  if (data) p.set("data", data);
  if (s.view === "places" && s.place) {
    p.set("place", s.place);
    if (s.placeIn) p.set("in", s.placeIn);
  } else if (s.view !== "city") p.set("view", s.view);
  if (s.view !== "places") p.set("city", s.city);
  if (s.view === "map" && s.mapAt) p.set("at", s.mapAt);
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

// Change in the total from date i-1 to i, over the quests counted on both dates only.
function likeForLikeDelta(h, i) {
  let d = 0, any = false;
  for (const [name, s] of Object.entries(h.quests)) {
    if (!selected(name) || s.open[i] == null || s.open[i - 1] == null) continue;
    d += s.open[i] - s.open[i - 1];
    any = true;
  }
  return any ? d : null;
}

// Indices where the SC version, resurvey multiplier, area unit or notes modelling differs from the previous date. With
// questSet, also where the set of selected quests changes (a quest type counted for the first
// time, e.g. a newly ported custom quest), which moves a total but not a single quest's line.
function breaks(h, { questSet = false } = {}) {
  const out = [];
  for (let i = 1; i < h.meta.length; i++) {
    const a = h.meta[i - 1], b = h.meta[i];
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

function lineChart(target, h, series, { height = 260, showAged = true, questSetBreaks = false, note = null, noteIdle = true } = {}) {
  const xs = h.dates.map(dayTs);
  const mapping = series.open.map((v, i) => (v == null ? null : v - (series.aged[i] || 0)));
  const brk = breaks(h, { questSet: questSetBreaks });
  const few = xs.length <= 60;
  // Over a year or more, label months with their year and leave days out.
  const long = xs.length > 1 && xs[xs.length - 1] - xs[0] > 300 * 86400;
  const tickFmt = long ? { month: "short", year: "numeric", timeZone: "UTC" } : { month: "short", day: "numeric", timeZone: "UTC" };
  const surface = css("--surface");
  const rel = releaseLayer(xs, { note, idle: noteIdle });
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
    cursor: { points: { size: 10, width: 2, fill: surface }, drag: { x: false, y: false } },
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
      setCursor: [(u) => { if (u.cursor.idx == null) u.setLegend({ idx: xs.length - 1 }); rel.cursor(u); }],
      draw: [(u) => {
        rel.draw(u);
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

function renderTiles(h, tot) {
  const n = h.dates.length, i = n - 1;
  const open = tot.open[i], aged = tot.aged[i] || 0;
  const change = n > 1 ? likeForLikeDelta(h, i) : null;
  const sameSet = n > 1 && !breaks(h, { questSet: true }).some((b) => b.i === i && /types/.test(b.short));
  const km = last(h.denominators.highwayKm);
  const area = h.denominators.landAreaKm2;
  const delta = change != null && open != null
    ? el("div", { class: "delta" }, `${signed(change)} since ${h.dates[i - 1]}${sameSet ? "" : ", same quest types"}`)
    : el("div", { class: "note" }, "First snapshot, no change yet");
  $("#tiles").replaceChildren(
    tile("Open quests", open == null ? "—" : nf.format(open), delta, true),
    tile("Need mapping", open == null ? "—" : nf.format(open - aged),
      el("div", { class: "note" }, el("span", { class: "key", style: `background:${css("--series-1")}` }), "tags still missing")),
    tile("Aged, need resurvey", nf.format(aged),
      el("div", { class: "note" }, el("span", { class: "key", style: `background:${css("--series-2")}` }),
        open ? `${Math.round((100 * aged) / open)}% of open` : "")),
    tile("Per km² of land", ratio(open, area), el("div", { class: "note" }, area ? `${nf1.format(area)} km²` : "area unknown")),
    tile("Per km of road", ratio(open, km), el("div", { class: "note" }, km ? `${nf.format(Math.round(km))} km of highway` : "road length not yet counted")),
  );
}

function renderCityCharts(h) {
  for (const { u } of charts) u.destroy();
  charts.length = 0;
  const tot = totalSeries(h);
  renderTiles(h, tot);
  const name = h.name;
  $("#chart-title").textContent = `Open quests over time in ${name}`;
  $("#chart-sub").textContent = `Counting ${selectionText()}. ` +
    (h.dates.length === 1 ? "One snapshot so far; the line starts here." : `${h.dates.length} snapshots since ${h.dates[0]}.`) +
    (state.asThen ? " Each quest counts from the release that first offered it, by today's rules. Quests since removed from the app are not in these counts." : "");
  lineChart($("#chart-total"), h, tot, { height: 300, questSetBreaks: true, note: $("#release-note") });
  $("#breaks").replaceChildren(...breaks(h, { questSet: true }).map((b) => el("li", {}, `│ ${b.date}: ${b.label}. Totals on either side are not directly comparable.`)));
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
                                  : "Not counted in this city."),
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
  const c = cityById(cityId), codes = (c && c.countryCodes) || [];
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
    const status = (q.status && q.status[h.city]) || "unsupported";
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

  const out = [];
  for (const [i, r] of rows.entries()) {
    if (r.group && r.group !== (rows[i - 1] && rows[i - 1].group)) {
      const n = rows.filter((x) => x.group === r.group).length;
      out.push(el("tr", { class: "group-head" }, el("th", { colspan: 7, scope: "rowgroup" }, `${GROUPS[r.group].head(h)} · ${n}`)));
    }
    out.push(questRow(h, r));
  }
  $("#quest-table tbody").replaceChildren(...out);
}

function questRow(h, r) {
  const sel = selected(r.q.name), pinned = state.pinned.includes(r.q.name);
  const name = questTitle(r.q.name);
  const link = r.q.wikiLink ? el("a", { href: `https://wiki.openstreetmap.org/wiki/${r.q.wikiLink}` }, name) : el("span", {}, name);
  const where = r.group === "not-in-region" ? offeredWhere(r.q.enabledInCountries, h.city) : null;
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
      el("td", { class: "num" }, r.agedShare == null ? "—" : `${Math.round(100 * r.agedShare)}%`));
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

async function renderCity() {
  if (!hist || hist.city !== state.city) hist = await getJSON(`history/${state.city}.json`);
  renderCityCharts(hist);
  renderQuestTable(hist);
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

async function renderCompare() {
  const sel = $("#compare-quest");
  if (!sel.options.length) {
    sel.append(el("option", { value: "" }, "All counted quests (app defaults)"));
    const counted = quests.quests.filter((q) => Object.values(q.status || {}).includes("counted"))
      .sort((a, b) => humanize(a.name).localeCompare(humanize(b.name)));
    for (const q of counted) sel.append(el("option", { value: q.name }, humanize(q.name) + (q.defaultDisabled ? " (off by default)" : "")));
  }
  sel.value = state.compareQuest;

  const rows = await compareRows();
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
  // cities.json carries totals over time, not each quest's, so the trend column is for all quests only
  const trends = !state.compareQuest && cities.dates;
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
    const trend = trends && r.c.trend;
    const where = r.notOffered && offeredWhere(questByName.get(state.compareQuest).enabledInCountries, r.c.id);
    return el("tr", { class: [r.c.id === state.city ? "picked" : "", r.notOffered ? "off" : ""].join(" ").trim() || null },
      el("td", { class: "num" }, r.notOffered ? null : i + 1),
      el("td", {}, el("a", { href: "#", onclick: (e) => { e.preventDefault(); setCity(r.c.id); setView("city"); } }, r.c.name)),
      trends ? el("td", { class: "c-trend" }, trend ? sparkline(cities.dates, trend, r.c.name) : null) : null,
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

function placesIndex() {
  if (!placeIndex) {
    placeIndex = optionalJSON(`${PLACES}/index.json`);
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
const refId = (ref) => ref.kind === "country" ? ref.country.id : ref.kind === "region" ? ref.region.id : ref.shard.rows[ref.i][R.id];
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
    if (country.id === id) return { kind: "country", country };
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

function placeHref(ref) {
  return queryString({ ...state, view: "places", place: ref ? refId(ref) : "", placeIn: ref ? refIn(ref) : "" });
}

function goPlace(ref) {
  state.view = "places";
  state.place = ref ? refId(ref) : "";
  state.placeIn = ref ? refIn(ref) : "";
  writeURL();
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

function cityLink(c, text) {
  return el("a", { href: queryString({ ...state, view: "city", city: c.id }), onclick: (e) => {
    if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    setCity(c.id);
    renderFooter();
    setView("city");
    window.scrollTo({ top: 0 });
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

// The city in the state, the button and the reader's recent cities; the caller renders.
function setCity(id) {
  state.city = id;
  showCity();
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify([id, ...recentCities().filter((x) => x !== id)].slice(0, MAX_RECENT + 1)));
  } catch { /* no storage, no recent cities */ }
}

function chooseCity(id) {
  $("#city-sheet").close();
  setCity(id);
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
    if (e.key === "Enter" && e.target === search && fold(search.value)) { $("#city-results .sheet-row").click(); return; }
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
  if (state.placeScope !== ref.country.cc) { state.placeScope = ref.country.cc; $("#place-scope").value = ref.country.cc; }
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
  if (counted && !counted.includes("/")) out.push(cityCard(ref, counted), await partsCard(counted, ref, null));
  else if (counted) out.push(...await partCards(ref, counted));
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

function cityCard(ref, cityId) {
  const c = cityById(cityId);
  if (!c) return el("article", { class: "card" }, el("h2", {}, "Counted"),
    el("p", { class: "sub" }, `${refName(ref)} is counted; its numbers arrive with the next published count.`));
  return el("article", { class: "card" },
    el("div", { class: "tiles" },
      tile("Open quests", nf.format(c.open), el("div", { class: "note" }, `as of ${c.asOfDate}, the app's default quests`), true),
      tile("Aged, need resurvey", nf.format(c.agedOnly), el("div", { class: "note" }, c.open ? `${Math.round((100 * c.agedOnly) / c.open)}% of open` : "")),
      tile("Per km² of land", ratio(c.open, c.landAreaKm2), el("div", { class: "note" }, c.landAreaKm2 ? `${nf1.format(c.landAreaKm2)} km²` : "area unknown"))),
    el("p", {}, cityLink(c, `Open ${c.name}: every quest, ticks, pins and the chart over time →`)));
}

// The newest snapshot of a city: the parts are in it (cities.<id>.parts).
function snapshotOf(c) { return optionalJSON(`${DATA}/${c.region}/snapshots/${c.asOfDate}.json`); }
function partNames(cityId) { return optionalJSON(`${DATA}/parts/${encodeURIComponent(cityId)}.json`); }

const partTotal = (counts) => Object.entries(counts || {}).reduce((s, [q, n]) => s + (selected(q) ? n : 0), 0);

// The city's parts with their totals over the ticked quests; null when it has none published.
async function partsCard(cityId, ref, current) {
  const c = cityById(cityId);
  if (!c) return null;
  // the snapshot first: a city without parts has no names file to ask for
  const snap = await snapshotOf(c).catch(() => null);
  const counts = snap && snap.cities && snap.cities[cityId] && snap.cities[cityId].parts;
  const names = counts && Object.keys(counts).length ? await partNames(cityId).catch(() => null) : null;
  if (!names || !names.parts || !names.parts.length) return null;
  const sh = ref.shard;
  const rows = names.parts.map((p) => ({ p, open: counts[p.id] ? partTotal(counts[p.id]) : null }))
    .sort((a, b) => (b.open ?? -1) - (a.open ?? -1) || enName(a.p).localeCompare(enName(b.p)));
  return el("article", { class: "card" },
    el("h2", {}, `Parts of ${c.name}`),
    el("p", { class: "sub" }, `Open quests inside each part's OpenStreetMap boundary, counting ${selectionText()}. ` +
      "Parts overlap and leave gaps, so they do not add up to the city."),
    el("div", { class: "table-wrap" }, el("table", { class: "data" },
      el("thead", {}, el("tr", {}, el("th", { scope: "col" }, "Part"), el("th", { scope: "col" }, "Kind"), el("th", { scope: "col", class: "num" }, "Open"))),
      el("tbody", {}, rows.map(({ p, open }) => {
        const i = sh.byId.get(p.id);
        const label = enName(p);
        return el("tr", { class: p.id === current ? "picked" : null },
          el("td", {}, i != null ? placeLink(rowRef(sh, i), label) : label),
          el("td", {}, p.subtype === "neighborhood" ? "neighbourhood" : p.subtype),
          el("td", { class: "num" }, open == null ? "—" : nf.format(open)));
      })))));
}

// A counted part: its open quests per type from the city's newest snapshot, the ticked ones summed.
async function partCards(ref, counted) {
  const [cityId, pid] = [counted.slice(0, counted.indexOf("/")), counted.slice(counted.indexOf("/") + 1)];
  const c = cityById(cityId);
  const snap = c ? await snapshotOf(c).catch(() => null) : null;
  const sc = snap && snap.cities && snap.cities[cityId];
  const counts = sc && sc.parts && sc.parts[pid];
  const cityName = c ? c.name : cityId;
  if (!counts) {
    return [el("article", { class: "card" }, el("h2", {}, `Counted as part of ${cityName}`),
      el("p", { class: "sub" }, `${refName(ref)}'s numbers arrive with ${cityName}'s next count.`),
      c ? el("p", {}, cityLink(c, `Open ${c.name} →`)) : null)];
  }
  const total = partTotal(counts);
  const cityTotal = Object.entries(sc.quests).reduce((s, [q, v]) => s + (selected(q) ? v.open : 0), 0);
  const rows = quests.quests.filter((q) => counts[q.name])
    .sort((a, b) => selected(b.name) - selected(a.name) || counts[b.name] - counts[a.name] || a.order - b.order);
  const none = quests.quests.filter((q) => q.status && q.status[cityId] === "counted" && !counts[q.name]).length;
  const card = el("article", { class: "card" },
    el("div", { class: "tiles" },
      tile("Open quests", nf.format(total), el("div", { class: "note" }, `as of ${snap.asOfDate}`), true),
      tile(`Share of ${cityName}'s`, cityTotal ? `${rate((100 * total) / cityTotal)}%` : "—",
        el("div", { class: "note" }, `${nf.format(cityTotal)} open in ${cityName}`)),
      tile("Quest types open here", nf.format(rows.length), el("div", { class: "note" }, `${none} counted types have none`))),
    el("p", { class: "sub" }, `Counted in ${cityName}'s own run: the quests whose position is inside ${refName(ref)}'s ` +
      `OpenStreetMap boundary, counting ${selectionText()}. Parts have no aged split or history yet, only the newest count ` +
      "with the app's default resurvey setting."),
    el("div", { class: "card-head" }, el("h2", {}, `Quests in ${refName(ref)}`),
      el("button", { type: "button", class: "btn", title: "Tick the quests the app turns on by default, untick the rest",
                     onclick: () => { state.selected = baseSet("app"); selectionChanged(); } }, "App defaults")),
    el("div", { class: "table-wrap" }, el("table", { class: "data" },
      el("thead", {}, el("tr", {},
        el("th", { scope: "col", class: "c-pick" }, el("span", { class: "visually-hidden" }, "Counted")),
        el("th", { scope: "col" }, "Quest"), el("th", { scope: "col", class: "num" }, "Open"),
        el("th", { scope: "col", class: "num" }, `In ${cityName}`))),
      el("tbody", {}, rows.map((q) => {
        const sel = selected(q.name), name = questTitle(q.name);
        return el("tr", { class: sel ? null : "unselected" },
          el("td", { class: "c-pick" }, el("input", { type: "checkbox", checked: sel, "aria-label": `Count ${name} in the totals`,
                                                      onchange: () => toggleSelect(q.name) })),
          el("td", {}, el("div", { class: "quest-cell" }, questIcon(q.name),
            el("div", {}, q.wikiLink ? el("a", { href: `https://wiki.openstreetmap.org/wiki/${q.wikiLink}` }, name) : el("span", {}, name),
              q.defaultDisabled ? el("span", { class: "chip", title: "Off by default in the app" }, "off by default") : null,
              el("span", { class: "code" }, q.name)))),
          el("td", { class: "num" }, nf.format(counts[q.name])),
          el("td", { class: "num" }, sc.quests[q.name] ? nf.format(sc.quests[q.name].open) : "—"));
      })))),
    el("p", {}, cityLink(c, `Open ${cityName}: the whole city, over time →`)));
  return [card, await partsCard(cityId, ref, pid)];
}

// ---------- map view ----------
// What is counted, on a map: each city's boundary from coverage.json (DATA-FORMAT.md), joined by id to
// cities.json for its name and count. Everything not coloured is not counted. A city is a few pixels at
// the zoom that shows both continents, so it also has a dot, and each dot goes the moment its own city
// covers more of the screen than the dot does — small cities keep theirs longer than big ones.
// Leaflet is the one page's library, so it loads with the tab.

const LEAFLET = "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet";
const LEAFLET_JS_SRI = "sha384-cxOPjt7s7Iz04uaHJceBmS+qpjv2JkIHNVcuOrM+YHwZOmJGBXI00mdUXEq65HTH";
const LEAFLET_CSS_SRI = "sha384-sHL9NAb7lN7rfvG5lfHpm643Xkcjzp4jFvuavGOndn6pjVqS6ny56CAt3nsEVT4H";
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
    const e = el(tag, { ...attrs, crossorigin: "anonymous" });
    e.onload = done;
    e.onerror = () => fail(new Error("the map library did not load"));
    document.head.append(e);
  });
  return Promise.all([
    load("link", { rel: "stylesheet", href: `${LEAFLET}.css`, integrity: LEAFLET_CSS_SRI }),
    load("script", { src: `${LEAFLET}.js`, integrity: LEAFLET_JS_SRI }),
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
    if (t.dataset.view === state.view) t.setAttribute("aria-current", "page");
    else t.removeAttribute("aria-current");
  }
  $("#view-city").hidden = state.view !== "city";
  $("#view-compare").hidden = state.view !== "compare";
  $("#view-places").hidden = state.view !== "places";
  $("#view-map").hidden = state.view !== "map";
  $("#city-filters").style.display = ["places", "map"].includes(state.view) ? "none" : "";   // neither has a city picker
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
  if (cityById(state.city)) setCity(state.city);   // a link's city counts as seen
  else {
    state.city = [...recentCities(), HOME_CITY].find(cityById) || cities.cities[0].id;
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

  $("#quest-filter").addEventListener("input", (e) => { state.filter = e.target.value; if (hist) renderQuestTable(hist); });
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

  sortHandler("#quest-table", () => state.questSort, () => renderQuestTable(hist));
  sortHandler("#compare-table", () => state.compareSort, renderCompare);

  renderFooter();
  writeURL();
  await render();
}

main();
