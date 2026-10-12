// sc-open-quests site. Reads the JSON described in DATA-FORMAT.md; no build step.
// ?data=<path> points it at another data directory (the test fixtures use this).
"use strict";

const DATA = (new URLSearchParams(location.search).get("data") || "data").replace(/\/$/, "");
const MAX_PICKED = 6;
const nf = new Intl.NumberFormat("en-CA");
const nf1 = new Intl.NumberFormat("en-CA", { maximumFractionDigits: 1, minimumFractionDigits: 1 });

const state = {
  view: "city",
  city: "toronto",
  includeDisabled: false,
  filter: "",
  picked: [],                       // quest names charted as small multiples
  questSort: { key: "open", dir: -1 },
  compareQuest: "",                 // "" = all counted quests
  compareSort: { key: "perKm2", dir: -1 },
};
let cities, quests, questByName, hist;   // loaded data
const snapshotCache = new Map();
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

function signed(n) { return n > 0 ? "+" + nf.format(n) : n < 0 ? "−" + nf.format(-n) : "±0"; }
// Rates: one decimal from 10 up, two significant digits below (0.012, 0.35, 4.7).
const sig2 = new Intl.NumberFormat("en-CA", { minimumSignificantDigits: 2, maximumSignificantDigits: 2 });
const nf0 = new Intl.NumberFormat("en-CA", { maximumFractionDigits: 0 });
function rate(v) { return v == null || !isFinite(v) ? "—" : (v >= 100 ? nf0 : v >= 10 ? nf1 : sig2).format(v); }
function ratio(n, d) { return n != null && d ? rate(n / d) : "—"; }
const last = (arr) => arr[arr.length - 1];

function headlineQuest(q) {   // does this quest count towards the headline total?
  return q && (state.includeDisabled || !q.defaultDisabled);
}

// ---------- URL state ----------

function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  if (p.get("view")) state.view = p.get("view") === "compare" ? "compare" : "city";
  if (p.get("city")) state.city = p.get("city");
  if (p.has("q")) state.picked = p.get("q").split(",").filter(Boolean).slice(0, MAX_PICKED);
  if (p.has("cq")) state.compareQuest = p.get("cq");
  state.includeDisabled = p.get("off") === "1";
}

function writeHash() {
  const p = new URLSearchParams();
  if (state.view !== "city") p.set("view", state.view);
  p.set("city", state.city);
  if (state.picked.length) p.set("q", state.picked.join(","));
  if (state.compareQuest) p.set("cq", state.compareQuest);
  if (state.includeDisabled) p.set("off", "1");
  window.history.replaceState(null, "", "#" + p.toString().replace(/%2C/g, ","));
}

// ---------- series ----------

// Sum of the headline quests at each date. null quest values count as absent, not 0,
// but a date where every quest is null stays null.
function totalSeries(h) {
  const n = h.dates.length, open = Array(n).fill(null), aged = Array(n).fill(null);
  for (const [name, s] of Object.entries(h.quests)) {
    if (!headlineQuest(questByName.get(name))) continue;
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

// Names of the headline quests that have a value at date index i.
function headlineQuestsAt(h, i) {
  return new Set(Object.entries(h.quests)
    .filter(([name, s]) => s.open[i] != null && headlineQuest(questByName.get(name))).map(([name]) => name));
}

// Change in the headline total from date i-1 to i, over the quests counted on both dates only.
function likeForLikeDelta(h, i) {
  let d = 0, any = false;
  for (const [name, s] of Object.entries(h.quests)) {
    if (!headlineQuest(questByName.get(name)) || s.open[i] == null || s.open[i - 1] == null) continue;
    d += s.open[i] - s.open[i - 1];
    any = true;
  }
  return any ? d : null;
}

// Indices where the SC version, resurvey multiplier or area unit differs from the previous date. With
// questSet, also where the set of headline quests changes (a quest type counted for the first
// time, e.g. a newly ported custom quest), which moves a total but not a single quest's line.
function breaks(h, { questSet = false } = {}) {
  const out = [];
  for (let i = 1; i < h.meta.length; i++) {
    const a = h.meta[i - 1], b = h.meta[i];
    const what = [], short = [];
    if (questSet) {
      const before = headlineQuestsAt(h, i - 1), now = headlineQuestsAt(h, i);
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
    if (what.length) out.push({ i, date: h.dates[i], label: what.join(", "), short: short.join(" ") });
  }
  return out;
}

// ---------- chart ----------

function dayTs(d) { return Date.UTC(+d.slice(0, 4), +d.slice(5, 7) - 1, +d.slice(8, 10)) / 1000; }

function lineChart(target, h, series, { height = 260, showAged = true, questSetBreaks = false } = {}) {
  const xs = h.dates.map(dayTs);
  const mapping = series.open.map((v, i) => (v == null ? null : v - (series.aged[i] || 0)));
  const brk = breaks(h, { questSet: questSetBreaks });
  const few = xs.length <= 60;
  // Over a year or more, label months with their year and leave days out.
  const long = xs.length > 1 && xs[xs.length - 1] - xs[0] > 300 * 86400;
  const tickFmt = long ? { month: "short", year: "numeric", timeZone: "UTC" } : { month: "short", day: "numeric", timeZone: "UTC" };
  const surface = css("--surface");
  const mk = (label, color, data) => ({
    label, stroke: color, width: 2, value: (u, v) => (v == null ? "—" : nf.format(v)),
    points: { show: few, size: 8, width: 2, stroke: color, fill: color },
    spanGaps: false, _data: data,
  });
  const ser = [mk("Needs mapping", css("--series-1"), mapping)];
  if (showAged) ser.push(mk("Aged, needs resurvey", css("--series-2"), series.aged));
  const axis = { stroke: css("--muted"), grid: { stroke: css("--grid"), width: 1 },
                 ticks: { stroke: css("--axis"), width: 1, size: 4 }, font: "12px system-ui, sans-serif" };
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
      setCursor: [(u) => { if (u.cursor.idx == null) u.setLegend({ idx: xs.length - 1 }); }],
      draw: [(u) => {
        if (!brk.length) return;
        const ctx = u.ctx, { top, height: ph } = u.bbox;
        ctx.save();
        ctx.strokeStyle = css("--ink-2");
        ctx.fillStyle = css("--ink-2");
        ctx.lineWidth = devicePixelRatio;
        ctx.font = `${11 * devicePixelRatio}px system-ui, sans-serif`;
        for (const b of brk) {
          const x = Math.round(u.valToPos(xs[b.i] - 43200, "x", true));   // half a day before the new run
          ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, top + ph); ctx.stroke();
          ctx.fillText(" " + b.short, x + 2, top + 12 * devicePixelRatio);
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
  $("#chart-sub").textContent =
    (state.includeDisabled ? "All counted quests, including those off by default. " : "All counted quests that are on by default. ") +
    (h.dates.length === 1 ? "One snapshot so far; the line starts here." : `${h.dates.length} snapshots since ${h.dates[0]}.`);
  lineChart($("#chart-total"), h, tot, { height: 280, questSetBreaks: true });
  $("#breaks").replaceChildren(...breaks(h, { questSet: true }).map((b) => el("li", {}, `│ ${b.date}: ${b.label}. Totals on either side are not directly comparable.`)));

  const box = $("#multiples");
  box.replaceChildren();
  for (const qn of state.picked) {
    const q = questByName.get(qn), s = questSeries(h, qn);
    const target = el("div", { class: "chart" });
    const card = el("article", { class: "card" },
      el("h3", {}, el("span", {}, humanize(qn)),
        el("button", { type: "button", title: "Remove from charts", "aria-label": `Remove ${humanize(qn)} from charts`,
                       onclick: () => togglePick(qn) }, "×")),
      el("p", { class: "sub" }, s ? (q && q.usesAge ? "Mapping and aged series." : "This quest has no resurvey age, so nothing ages into it.")
                                  : "Not counted in this city."),
      target);
    box.append(card);
    if (s) lineChart(target, h, s, { height: 180, showAged: !!(q && q.usesAge) });
  }
}

const STATUS_RANK = { counted: 0, "not-in-region": 2, unsupported: 3 };
const STATUS_TEXT = {
  counted: "no count in latest run",        // counted per quests.json, but absent from this city's snapshot
  "not-in-region": "not in Ontario",        // the app doesn't offer it here (enabledInCountries)
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

function renderQuestTable(h) {
  $("#table-city").textContent = h.name;
  const f = state.filter.trim().toLowerCase();
  let rows = questRows(h).filter((r) => (state.includeDisabled || !r.q.defaultDisabled) &&
    (!f || r.q.name.toLowerCase().includes(f) || humanize(r.q.name).toLowerCase().includes(f)));
  const { key, dir } = state.questSort;
  const val = {
    name: (r) => humanize(r.q.name).toLowerCase(),
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

  const tbody = $("#quest-table tbody");
  tbody.replaceChildren(...rows.map((r) => {
    const picked = state.picked.includes(r.q.name);
    const name = humanize(r.q.name);
    const link = r.q.wikiLink ? el("a", { href: `https://wiki.openstreetmap.org/wiki/${r.q.wikiLink}` }, name) : name;
    return el("tr", { class: [r.counted ? "" : "off", picked ? "picked" : ""].join(" ").trim() || null },
      el("td", {}, r.counted ? el("input", { type: "checkbox", checked: picked, "aria-label": `Chart ${name}`,
                                             onchange: () => togglePick(r.q.name) }) : null),
      el("td", {}, link, r.q.defaultDisabled ? el("span", { class: "chip", title: "Off by default in the app" }, "off by default") : null,
        el("span", { class: "code" }, r.q.name)),
      el("td", { class: "num" }, r.open == null ? "—" : nf.format(r.open)),
      el("td", { class: "num" }, r.isNew ? "new" : r.delta == null ? "—" : signed(r.delta)),
      el("td", { class: "num" }, r.agedShare == null ? "—" : `${Math.round(100 * r.agedShare)}%`),
      el("td", {}, el("span", { class: `badge ${r.q.support}` }, r.q.support)),
      el("td", {}, r.counted ? "counted" : STATUS_TEXT[r.status] || "not counted yet"));
  }));
}

function togglePick(name) {
  const i = state.picked.indexOf(name);
  if (i >= 0) state.picked.splice(i, 1);
  else if (state.picked.length < MAX_PICKED) state.picked.push(name);
  else { setStatus(`Up to ${MAX_PICKED} quests can be charted at once.`); return; }
  setStatus("");
  writeHash();
  renderCity();
}

async function renderCity() {
  if (!hist || hist.city !== state.city) hist = await getJSON(`history/${state.city}.json`);
  renderCityCharts(hist);
  renderQuestTable(hist);
}

// ---------- compare view ----------

async function snapshot(date) {
  if (!snapshotCache.has(date)) snapshotCache.set(date, getJSON(`snapshots/${date}.json`));
  return snapshotCache.get(date);
}

async function compareRows() {
  const qn = state.compareQuest;
  const rows = [];
  for (const c of cities.cities) {
    let open;
    if (!qn) open = state.includeDisabled ? c.openAll : c.open;
    else {
      const snap = await snapshot(c.asOfDate);
      const sq = snap.cities[c.id] && snap.cities[c.id].quests[qn];
      open = sq ? sq.open : null;
    }
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
    sel.append(el("option", { value: "" }, "All counted quests"));
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
  $("#compare-sub").textContent = `${state.compareQuest ? humanize(state.compareQuest) : "All counted quests" +
    (state.includeDisabled ? ", including those off by default" : "")}, ${cities.asOfDate}. ` +
    "Raw counts follow city size, so the table ranks by density. Click a column to rank by it; the bar shows the ranked column.";
  $("#compare-table tbody").replaceChildren(...rows.map((r, i) => {
    const v = r[barKey];
    return el("tr", { class: r.c.id === state.city ? "picked" : null },
      el("td", { class: "num" }, i + 1),
      el("td", {}, el("a", { href: "#", onclick: (e) => { e.preventDefault(); state.city = r.c.id; $("#city").value = r.c.id; setView("city"); } }, r.c.name)),
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
  writeHash();
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
  $("#foot-data").textContent =
    `Data as of ${cities.asOfDate} (Geofabrik Ontario extract) · StreetComplete ${cities.scVersion} quest definitions · ` +
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
  readHash();
  try {
    [cities, quests] = await Promise.all([getJSON("cities.json"), getJSON("quests.json")]);
  } catch (e) {
    setStatus(`No data yet (${e.message}). The first daily run publishes it.`);
    return;
  }
  questByName = new Map(quests.quests.map((q) => [q.name, q]));
  if (!cities.cities.some((c) => c.id === state.city)) state.city = cities.cities.some((c) => c.id === "toronto") ? "toronto" : cities.cities[0].id;
  state.picked = state.picked.filter((n) => questByName.has(n));

  const sel = $("#city");
  sel.replaceChildren(...cities.cities.map((c) => el("option", { value: c.id }, c.name)));
  sel.value = state.city;
  sel.addEventListener("change", () => { state.city = sel.value; writeHash(); renderFooter(); render(); });

  const dis = $("#include-disabled");
  dis.checked = state.includeDisabled;
  dis.addEventListener("change", () => { state.includeDisabled = dis.checked; writeHash(); render(); });

  $("#quest-filter").addEventListener("input", (e) => { state.filter = e.target.value; if (hist) renderQuestTable(hist); });
  $("#compare-quest").addEventListener("change", (e) => { state.compareQuest = e.target.value; writeHash(); renderCompare(); });
  for (const t of document.querySelectorAll(".tab"))
    t.addEventListener("click", (e) => { e.preventDefault(); setView(t.dataset.view); });

  sortHandler("#quest-table", () => state.questSort, () => renderQuestTable(hist));
  sortHandler("#compare-table", () => state.compareSort, renderCompare);

  renderFooter();
  writeHash();
  await render();
}

main();
