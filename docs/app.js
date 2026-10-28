// sc-open-quests site. Reads the JSON described in DATA-FORMAT.md; no build step.
// ?data=<path> points it at another data directory (the test fixtures use this).
"use strict";

const DATA = (new URLSearchParams(location.search).get("data") || "data").replace(/\/$/, "");
const MAX_PINNED = 6;
const nf = new Intl.NumberFormat("en-CA");
const nf1 = new Intl.NumberFormat("en-CA", { maximumFractionDigits: 1, minimumFractionDigits: 1 });

const state = {
  view: "city",
  city: "toronto",
  filter: "",
  selected: new Set(),              // quest names counted in the summary chart and tiles
  pinned: [],                       // quest names charted on their own, as small multiples
  questSort: { key: "open", dir: -1 },
  compareQuest: "",                 // "" = all counted quests
  compareSort: { key: "perKm2", dir: -1 },
  releases: true,                   // StreetComplete releases on the time axis
  place: "",                        // places view: the place shown (12-hex id), "" = the list of countries
  placeIn: "",                      // its region file as "<cc>/<regionId>", the hint that finds it
  placeScope: "",                   // the country the place search looks inside ("" = names in the index)
};
let cities, quests, questByName, hist;   // loaded data
let urlSelection = null;                    // the selection as read from the URL, resolved once quests.json is in
let icons = {};                             // quest name -> {icon, title}, from icons/index.json
let releases = [];                          // [{ts, version}], stable SC releases, oldest first
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
  if (get("view")) state.view = { compare: "compare", places: "places" }[get("view")] || "city";
  if (get("city")) state.city = get("city");
  state.pinned = names(p.get("pin") ?? h.get("q")).slice(0, MAX_PINNED);
  if (get("cq") != null) state.compareQuest = get("cq");
  state.releases = get("rel") !== "0";
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
  const sel = selectionParams();
  if (sel.base !== "app") p.set("base", sel.base);
  if (sel.on.length) p.set("on", sel.on.join(","));
  if (sel.off.length) p.set("off", sel.off.join(","));
  if (state.pinned.length) p.set("pin", state.pinned.join(","));
  if (state.compareQuest) p.set("cq", state.compareQuest);
  if (!state.releases) p.set("rel", "0");
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

// Sum of the selected quests at each date. null quest values count as absent, not 0,
// but a date where every quest is null stays null.
function totalSeries(h) {
  const n = h.dates.length, open = Array(n).fill(null), aged = Array(n).fill(null);
  for (const [name, s] of Object.entries(h.quests)) {
    if (!selected(name)) continue;
    for (let i = 0; i < n; i++) {
      if (s.open[i] != null) open[i] = (open[i] || 0) + s.open[i];
      if (s.agedOnly[i] != null) aged[i] = (aged[i] || 0) + s.agedOnly[i];
    }
  }
  return { open, aged };
}

function questSeries(h, name) {
  const s = h.quests[name];
  if (!s) return null;
  return { open: s.open, aged: s.agedOnly };
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

const majorRelease = (v) => /^v\d+\.0$/.test(v);

// StreetComplete releases as faint, unlabelled vertical lines through the plot. While the pointer is
// on a date, the release current on that date (the last one at or before it, so the line to the
// pointer's left) is drawn solid and named in note, below the chart. Over long ranges only majors get
// a faint line, but a minor release still gets its solid one while it is current.
function releaseLayer(xs, long, { note = null, idle = true } = {}) {
  const rel = state.releases ? releases.filter((r) => r.ts >= xs[0] - 86400 && r.ts <= last(xs) + 86400) : [];
  let hover = null, hoverTs = null;
  const shown = (r) => !long || majorRelease(r.version);
  const day = (ts) => new Date(ts * 1e3).toISOString().slice(0, 10);
  const describe = (r, ts) => `StreetComplete <b>${r.version}</b> was the current release on ${day(ts)}` +
    (r.ts === ts ? "; it came out that day." : `, out since ${day(r.ts)}.`);
  const idleText = rel.length && idle
    ? "The faint vertical lines are StreetComplete releases" + (long ? " (major versions)" : "") +
      "; move along the chart to see which was current. Every count here uses the quests of " + `v${cities.scVersion}` + ", whatever the date."
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
      for (const r of rel) if (shown(r) && r !== hover) line(r);
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
  const rel = releaseLayer(xs, long, { note, idle: noteIdle });
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
    (h.dates.length === 1 ? "One snapshot so far; the line starts here." : `${h.dates.length} snapshots since ${h.dates[0]}.`);
  lineChart($("#chart-total"), h, tot, { height: 300, questSetBreaks: true, note: $("#release-note") });
  $("#breaks").replaceChildren(...breaks(h, { questSet: true }).map((b) => el("li", {}, `│ ${b.date}: ${b.label}. Totals on either side are not directly comparable.`)));

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

const STATUS_RANK = { counted: 0, "not-in-region": 2, unsupported: 3 };
const STATUS_TEXT = {
  counted: "no count in latest run",        // counted per quests.json, but absent from this city's snapshot
  "not-in-region": "not offered here",      // the app doesn't offer it here (enabledInCountries)
  unsupported: "not counted yet",           // custom logic this site doesn't model yet
};

function questRows(h) {
  const n = h.dates.length;
  return quests.quests.map((q) => {
    const s = h.quests[q.name];
    const status = (q.status && q.status[h.city]) || "unsupported";
    const open = s ? s.open[n - 1] : null;
    const prev = s && n > 1 ? s.open[n - 2] : null;
    const aged = s ? s.agedOnly[n - 1] : null;
    return {
      q, status, open,
      delta: open != null && prev != null ? open - prev : null,
      isNew: open != null && n > 1 && prev == null,
      agedShare: q.usesAge && open ? aged / open : null,
      counted: status === "counted" && open != null,
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
    support: (r) => ["supported", "approximated", "unsupported"].indexOf(r.q.support),
    status: (r) => STATUS_RANK[r.status] ?? 9,
  }[key];
  rows.sort((a, b) => {
    if (a.counted !== b.counted) return a.counted ? -1 : 1;   // uncounted always below
    if (!a.counted) return (STATUS_RANK[a.status] ?? 9) - (STATUS_RANK[b.status] ?? 9) || a.q.order - b.q.order;
    const va = val(a), vb = val(b);
    if (va == null && vb == null) return a.q.order - b.q.order;
    if (va == null) return 1;
    if (vb == null) return -1;
    return (va < vb ? -1 : va > vb ? 1 : 0) * dir || a.q.order - b.q.order;
  });
  for (const th of document.querySelectorAll("#quest-table th[data-sort]"))
    th.setAttribute("aria-sort", th.dataset.sort === key ? (dir > 0 ? "ascending" : "descending") : "none");

  const on = rows.filter((r) => selected(r.q.name)).length;
  const head = $("#select-shown");
  head.checked = on > 0 && on === rows.length;
  head.indeterminate = on > 0 && on < rows.length;
  head.disabled = !rows.length;

  const tbody = $("#quest-table tbody");
  tbody.replaceChildren(...rows.map((r) => {
    const sel = selected(r.q.name), pinned = state.pinned.includes(r.q.name);
    const name = questTitle(r.q.name);
    const link = r.q.wikiLink ? el("a", { href: `https://wiki.openstreetmap.org/wiki/${r.q.wikiLink}` }, name) : el("span", {}, name);
    return el("tr", { class: [r.counted ? "" : "off", sel ? "" : "unselected", pinned ? "pinned" : ""].join(" ").trim() || null },
      el("td", { class: "c-pick" }, el("input", { type: "checkbox", checked: sel, "aria-label": `Count ${name} in the totals`,
                                                  onchange: () => toggleSelect(r.q.name) })),
      el("td", { class: "c-pin" }, r.counted ? el("button", { type: "button", class: "pin-btn", "aria-pressed": pinned ? "true" : "false",
                                                              title: pinned ? "Unpin: take its chart away" : "Pin: chart this quest on its own",
                                                              "aria-label": `${pinned ? "Unpin" : "Pin"} ${name}`,
                                                              onclick: () => togglePin(r.q.name) }) : null),
      el("td", {}, el("div", { class: "quest-cell" }, questIcon(r.q.name),
        el("div", {}, link, r.q.defaultDisabled ? el("span", { class: "chip", title: "Off by default in the app" }, "off by default") : null,
          el("span", { class: "code" }, r.q.name)))),
      el("td", { class: "c-trend" }, r.counted ? sparkline(h.dates, h.quests[r.q.name].open, name) : null),
      el("td", { class: "num" }, r.open == null ? "—" : nf.format(r.open)),
      el("td", { class: "num" }, r.isNew ? "new" : r.delta == null ? "—" : signed(r.delta)),
      el("td", { class: "num" }, r.agedShare == null ? "—" : `${Math.round(100 * r.agedShare)}%`),
      el("td", {}, el("span", { class: `badge ${r.q.support}` }, r.q.support)),
      el("td", {}, r.counted ? "counted" : STATUS_TEXT[r.status] || "not counted yet"));
  }));
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

function selectShown(on) {   // the header tick: every row the search box leaves
  for (const r of shownRows(hist)) {
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
  const rows = [];
  for (const c of cities.cities) {
    // cities.json carries the app-default total, not the reader's selection
    const open = qn ? per[c.id] ?? null : c.open;
    rows.push({
      c, open,
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
  $("#compare-sub").textContent = `${state.compareQuest ? humanize(state.compareQuest) : "All counted quests the app turns on by default"}, ${cities.asOfDate}. ` +
    "Raw counts follow city size, so the table ranks by density. Click a column to rank by it; the bar shows the ranked column." +
    (state.compareQuest && cities.dates ? " Trends are shown for all counted quests only." : "");
  $("#compare-table tbody").replaceChildren(...rows.map((r, i) => {
    const v = r[barKey];
    const trend = trends && r.c.trend;
    return el("tr", { class: r.c.id === state.city ? "picked" : null },
      el("td", { class: "num" }, i + 1),
      el("td", {}, el("a", { href: "#", onclick: (e) => { e.preventDefault(); state.city = r.c.id; $("#city").value = r.c.id; setView("city"); } }, r.c.name)),
      trends ? el("td", { class: "c-trend" }, trend ? sparkline(cities.dates, trend, r.c.name) : null) : null,
      el("td", { class: "num" }, fmt(r.open, nf)),
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
const refName = (ref) => ref.kind === "country" ? ref.country.name : ref.kind === "region" ? ref.region.name : ref.shard.rows[ref.i][R.name];
const refId = (ref) => ref.kind === "country" ? ref.country.id : ref.kind === "region" ? ref.region.id : ref.shard.rows[ref.i][R.id];
const refEn = (ref) => ref.kind === "row" ? ref.shard.rows[ref.i][R.en] : null;
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
    state.city = c.id;
    $("#city").value = c.id;
    renderFooter();
    setView("city");
    window.scrollTo({ top: 0 });
  } }, text);
}

const cityById = (id) => cities.cities.find((c) => c.id === id);

// ---- search ----

function fillScope(idx) {
  const sel = $("#place-scope");
  if (!sel.options.length) {
    sel.append(el("option", { value: "" }, "Countries and regions"),
      ...idx.countries.map((c) => el("option", { value: c.cc }, c.name)));
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
    if (pending) { note.textContent = `Loading ${country.name}'s ${nf.format(n)} place names…`; box.setAttribute("aria-busy", "true"); }
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
    offer({ kind: "country", country: c }, [fold(c.name)]);
    for (const r of c.regions) if (r.id !== "_" && r.name) offer({ kind: "region", country: c, region: r }, [fold(r.name)]);
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
    const en = refEn(h.ref);
    return el("li", {}, placeLink(h.ref, refName(h.ref) + (en ? ` (${en})` : "")),
      h.counted ? el("span", { class: "chip counted" }, "counted") : null,
      el("span", { class: "place-kind" }, SUBTYPE[h.st] || ""),
      el("span", { class: "place-chain" }, chainText(h.ref)));
  }));
  const where = country ? `${country.name}'s places and every country and region` :
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
  const slot = el("div", {}, el("p", { class: "notice" }, ref.kind === "country" ? `Loading ${ref.country.name}'s places…` : "Loading…"));
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
  const en = refEn(ref);
  return el("article", { class: "card place-head" },
    el("nav", { class: "crumbs", "aria-label": "Where it is" },
      placeLink(null, "All countries"),
      ...up.slice(0, -1).flatMap((r) => [el("span", { class: "sep", "aria-hidden": "true" }, "›"), placeLink(r)])),
    el("h2", {}, refName(ref), en ? el("span", { class: "en" }, ` (${en})`) : null,
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
  listed.sort((a, b) => a.sh.rows[a.i][R.name].localeCompare(b.sh.rows[b.i][R.name]));
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
  const p = new URLSearchParams({ template: "place-request.yml", title: `Count ${name} (${ref.country.name})`,
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
    .sort((a, b) => (b.open ?? -1) - (a.open ?? -1) || a.p.name.localeCompare(b.p.name));
  return el("article", { class: "card" },
    el("h2", {}, `Parts of ${c.name}`),
    el("p", { class: "sub" }, `Open quests inside each part's OpenStreetMap boundary, counting ${selectionText()}. ` +
      "Parts overlap and leave gaps, so they do not add up to the city."),
    el("div", { class: "table-wrap" }, el("table", { class: "data" },
      el("thead", {}, el("tr", {}, el("th", { scope: "col" }, "Part"), el("th", { scope: "col" }, "Kind"), el("th", { scope: "col", class: "num" }, "Open"))),
      el("tbody", {}, rows.map(({ p, open }) => {
        const i = sh.byId.get(p.id);
        const label = p.name + (p.en ? ` (${p.en})` : "");
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
  $("#city-filters").style.display = state.view === "places" ? "none" : "";   // a place page has no city picker
  try {
    if (state.view === "city") await renderCity();
    else if (state.view === "places") await renderPlaces();
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
  const [ic, rel] = await Promise.all([
    fetch("icons/index.json").then((r) => (r.ok ? r.json() : null)).catch(() => null),
    getJSON("sc-releases.json").catch(() => null),
  ]);
  icons = (ic && ic.quests) || {};
  releases = ((rel && rel.releases) || []).map((r) => ({ ts: dayTs(r.date), version: r.version }));
  if (!cities.cities.some((c) => c.id === state.city)) state.city = cities.cities.some((c) => c.id === "toronto") ? "toronto" : cities.cities[0].id;
  state.pinned = state.pinned.filter((n) => questByName.has(n));
  state.selected = resolveSelection(urlSelection);

  const sel = $("#city");
  // cities grouped as the regions are (Ontario, Germany), in config order, when there is more than one group
  const groups = [...new Set((cities.regions || []).map((r) => r.group))];
  const groupOf = (c) => ((cities.regions || []).find((r) => r.id === c.region) || {}).group;
  const option = (c) => el("option", { value: c.id }, c.name);
  sel.replaceChildren(...(groups.length > 1
    ? groups.map((g) => el("optgroup", { label: g }, ...cities.cities.filter((c) => groupOf(c) === g).map(option)))
    : cities.cities.map(option)));
  sel.value = state.city;
  sel.addEventListener("change", () => { state.city = sel.value; writeURL(); renderFooter(); render(); });

  const showRel = $("#show-releases");
  showRel.checked = state.releases;
  showRel.closest("label").hidden = !releases.length;
  showRel.addEventListener("change", () => { state.releases = showRel.checked; writeURL(); render(); });

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
