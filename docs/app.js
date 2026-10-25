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
  if (get("view")) state.view = get("view") === "compare" ? "compare" : "city";
  if (get("city")) state.city = get("city");
  state.pinned = names(p.get("pin") ?? h.get("q")).slice(0, MAX_PINNED);
  if (get("cq") != null) state.compareQuest = get("cq");
  state.releases = get("rel") !== "0";
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

function writeURL() {
  const p = new URLSearchParams();
  const data = new URLSearchParams(location.search).get("data");
  if (data) p.set("data", data);
  if (state.view !== "city") p.set("view", state.view);
  p.set("city", state.city);
  const sel = selectionParams();
  if (sel.base !== "app") p.set("base", sel.base);
  if (sel.on.length) p.set("on", sel.on.join(","));
  if (sel.off.length) p.set("off", sel.off.join(","));
  if (state.pinned.length) p.set("pin", state.pinned.join(","));
  if (state.compareQuest) p.set("cq", state.compareQuest);
  if (!state.releases) p.set("rel", "0");
  // a relative "?query" drops the hash, which is where old links kept the state
  window.history.replaceState(null, "", "?" + p.toString().replace(/%2C/g, ",").replace(/%2F/g, "/"));
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
  renderCity();
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
  try {
    if (state.view === "city") await renderCity();
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

  sortHandler("#quest-table", () => state.questSort, () => renderQuestTable(hist));
  sortHandler("#compare-table", () => state.compareSort, renderCompare);

  renderFooter();
  writeURL();
  await render();
}

main();
