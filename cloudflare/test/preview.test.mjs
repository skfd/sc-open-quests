// node --test cloudflare/test/  (tests/test_preview_worker.py runs it with the repo's check)
import test from "node:test";
import assert from "node:assert/strict";
import { askFrom, selectionFrom, seriesPairs, worldPairs, worldLatestOk, summarize, questWords, texts,
         countryName, previewFor } from "../src/preview.js";

const q = (s) => new URLSearchParams(s);
const REG = [{ name: "AddA", defaultDisabled: false }, { name: "AddB", defaultDisabled: false }, { name: "AddOff", defaultDisabled: true }];

test("a link names a place the way the page reads it", () => {
  assert.deepEqual(askFrom(q("city=toronto")), { kind: "city", city: "toronto", part: "" });
  assert.deepEqual(askFrom(q("city=toronto&part=dbb37f753302")), { kind: "city", city: "toronto", part: "dbb37f753302" });
  assert.deepEqual(askFrom(q("place=dbb37f753302&in=ca/eb1eed766420&city=guelph")),
    { kind: "place", place: "dbb37f753302", placeIn: "ca/eb1eed766420" });
  assert.equal(askFrom(q("")), null);
  assert.equal(askFrom(q("view=compare&city=toronto")), null);
  assert.equal(askFrom(q("place=ca")), null, "a country by its code has no file");
});

test("no path is built from text that is not an id", () => {
  assert.equal(askFrom(q("city=../secret")), null);
  assert.equal(askFrom(q("city=toronto&part=../../x")), null);
  assert.equal(askFrom(q("place=DBB37F753302")), null);
  assert.equal(askFrom(q("place=dbb37f753302&in=../../etc")).placeIn, "");
  assert.equal(askFrom(q("city=toronto&data=x")), null, "the test hooks keep the page's own head");
  assert.equal(askFrom(q("city=toronto&world=x")), null);
});

test("the selection is base, on and off", () => {
  assert.deepEqual([...selectionFrom(q(""), REG)], ["AddA", "AddB"]);
  assert.deepEqual([...selectionFrom(q("base=all"), REG)], ["AddA", "AddB", "AddOff"]);
  assert.deepEqual([...selectionFrom(q("base=none&on=AddOff,Unknown"), REG)], ["AddOff"]);
  assert.deepEqual([...selectionFrom(q("off=AddA&on=AddOff"), REG)], ["AddB", "AddOff"]);
  assert.deepEqual([...selectionFrom(q("base=bogus"), REG)], ["AddA", "AddB"]);
});

const series = (dates, quests) => ({ dates, quests });
const s = (open, agedOnly) => ({ open, agedOnly });

test("4 weeks back is the newest count at least 28 days older", () => {
  const h = series(["2026-10-01", "2026-10-20", "2026-10-25", "2026-11-22"], { AddA: s([100, 90, 80, 70], [10, 10, 10, 5]) });
  const p = seriesPairs(h);
  assert.equal(p.date, "2026-11-22");
  assert.equal(p.since, null);
  assert.deepEqual(p.pairs.get("AddA"), { now: [70, 5], then: [80, 10] });   // 10-25 is exactly 28 days back
});

test("a young series is compared with its first count, and says since when", () => {
  const p = seriesPairs(series(["2026-11-10", "2026-11-22"], { AddA: s([5, 9], [0, 4]) }));
  assert.equal(p.since, "2026-11-10");
  assert.deepEqual(p.pairs.get("AddA"), { now: [9, 4], then: [5, 0] });
  const one = seriesPairs(series(["2026-11-22"], { AddA: s([5], [0]) }));
  assert.equal(one.pairs.get("AddA").then, null);
  assert.equal(summarize(one.pairs, new Set(["AddA"])).change, null);
});

test("the total and the change count selected quests only, like for like", () => {
  const h = series(["2026-10-01", "2026-11-22"], {
    AddA: s([100, 80], [0, 0]),
    AddB: s([null, 40], [null, 0]),        // not counted then: in the total, not in the change
    AddOff: s([500, 900], [0, 0]),         // not selected
    AddGone: s([7, null], [0, null]),      // not counted now
  });
  const r = summarize(seriesPairs(h).pairs, new Set(["AddA", "AddB", "AddGone"]));
  assert.equal(r.open, 120);
  assert.deepEqual(r.change, { open: -20, aged: 0 });
  assert.deepEqual(r.top, [{ name: "AddA", open: 80 }, { name: "AddB", open: 40 }]);
});

test("no selected quest counted is no number, and a missing aged split is said as unknown", () => {
  const h = series(["2026-10-01", "2026-11-22"], { AddA: s([1, 2], [null, 0]) });
  assert.equal(summarize(seriesPairs(h).pairs, new Set(["AddB"])).open, null);
  assert.deepEqual(summarize(seriesPairs(h).pairs, new Set(["AddA"])).change, { open: 1, aged: null });
});

const LATEST = { schema: 2, v: "abc", date: "2026-11-17", first: "2026-11-01", back: "2026-11-01", quests: ["AddA"], place: "place/", children: "children/" };

test("a world place is read at latest.date and never past it", () => {
  const pf = { quests: { AddA: [[0, 10, 1], [5, 12, 2], [16, 20, 3], [17, 99, 9]] } };   // day 17 is past 11-17 (day 16)
  const p = worldPairs(LATEST, pf);
  assert.equal(p.date, "2026-11-17");
  assert.equal(p.since, "2026-11-01");
  assert.deepEqual(p.pairs.get("AddA"), { now: [20, 3], then: [10, 1] });
});

test("a world place counted late starts at its own first day; one counted after the date is none", () => {
  const p = worldPairs(LATEST, { from: 10, quests: { AddA: [[10, 4, 0], [12, 6, 0]] } });
  assert.equal(p.since, "2026-11-11");
  assert.deepEqual(p.pairs.get("AddA"), { now: [6, 0], then: [4, 0] });
  assert.equal(worldPairs(LATEST, { from: 20, quests: {} }), null);
  assert.equal(worldPairs({ ...LATEST, date: "2026-11-01" }, { quests: { AddA: [[0, 4, 0]] } }).compared, false);
});

test("after 28 world days the change is over 4 weeks", () => {
  const p = worldPairs({ ...LATEST, date: "2026-12-10" }, { quests: { AddA: [[0, 10, 0], [11, 7, 0], [12, 5, 0]] } });
  assert.equal(p.since, null);
  assert.deepEqual(p.pairs.get("AddA"), { now: [5, 0], then: [7, 0] });   // day 39 against day 11
});

test("a latest.json of another schema is as good as none", () => {
  assert.equal(worldLatestOk(LATEST), true);
  assert.equal(worldLatestOk({ ...LATEST, schema: 1 }), false);
  assert.equal(worldLatestOk({ ...LATEST, date: "soon" }), false);
  assert.equal(worldLatestOk(null), false);
});

test("quests are named by their class, not the app's question", () => {
  assert.equal(questWords("AddBenchBackrest"), "bench backrest");
  assert.equal(questWords("AddHousenumber"), "housenumber");
  assert.equal(questWords("OsmNoteQuestType"), "OSM notes");
  assert.equal(questWords("CheckExistence"), "check existence");
});

const T = { name: "Agincourt North", where: "Toronto", date: "2026-11-22", since: null, top: [{ name: "AddHousenumber", open: 312 }, { name: "AddBuildingType", open: 201 }] };

test("the words: a fall, a rise by aging, a young series", () => {
  assert.deepEqual(texts({ ...T, open: 1284, change: { open: -120, aged: -10 } }), {
    title: "1,284 open StreetComplete quests in Agincourt North, Toronto",
    description: "Down 120 in the last 4 weeks. Most open: housenumber 312, building type 201. As of Nov 22, 2026.",
  });
  assert.match(texts({ ...T, open: 1284, change: { open: 120, aged: 100 } }).description, /^Up 120 in the last 4 weeks, mostly resurveys coming due\. /);
  assert.match(texts({ ...T, open: 1284, change: { open: 120, aged: 20 } }).description, /^Up 120 in the last 4 weeks\. /);
  assert.match(texts({ ...T, open: 1284, change: { open: 120, aged: null } }).description, /^Up 120 in the last 4 weeks\. /);
  assert.match(texts({ ...T, open: 1284, since: "2026-10-27", change: { open: 0, aged: 0 } }).description, /^No change since Oct 27\. /);
  assert.match(texts({ ...T, open: 1284, change: null }).description, /^Most open: /);
});

test("the words: almost done only where it is falling, and nothing open", () => {
  assert.equal(texts({ ...T, open: 14, change: { open: -3, aged: 0 } }).title, "Almost done: 14 StreetComplete quests left in Agincourt North, Toronto");
  assert.equal(texts({ ...T, open: 1, change: { open: -3, aged: 0 } }).title, "Almost done: 1 StreetComplete quest left in Agincourt North, Toronto");
  assert.equal(texts({ ...T, open: 14, change: { open: 0, aged: 0 } }).title, "14 open StreetComplete quests in Agincourt North, Toronto");
  assert.equal(texts({ ...T, where: "", top: [], open: 0, change: null }).title, "No open StreetComplete quests in Agincourt North");
  assert.equal(texts({ ...T, where: "", top: [], open: 0, change: null }).description, "As of Nov 22, 2026.");
});

test("countries are named as the page names them", () => {
  assert.equal(countryName("CA"), "Canada");
  assert.equal(countryName("PS"), "Palestine");
  assert.equal(countryName(""), null);
});

// ---- the whole preview, over loaders ----
const CITY = series(["2026-10-01", "2026-11-22"], { AddA: s([100, 80], [0, 0]), AddOff: s([9, 9], [0, 0]) });
CITY.name = "Toronto";
const PART = { ...series(["2026-10-27", "2026-11-22"], { AddA: s([30, 20], [0, 0]) }), name: "Agincourt North", en: null };
const SHARD = { places: [
  ["eb1eed766420", "Ontario", 2, -1, 0, 0, 0, 0, null, null],
  ["9fc3a6b4bdda", "Toronto", 3, 0, 0, 0, 0, 0, null, "toronto"],
  ["dbb37f753302", "Agincourt North", 8, 1, 0, 0, 0, 0, null, "toronto/dbb37f753302"],
  ["be76926172b2", "Rivière <Aveugle> & \"Co\"", 5, 0, 0, 0, 0, 0, "Blind River", null],
] };
function loaders(over = {}) {
  const asked = [];
  const files = {
    "data/history/toronto.json": CITY,
    "data/history/toronto/dbb37f753302.json": PART,
    "data/cities.json": { cities: [{ id: "toronto", name: "Toronto", place: "9fc3a6b4bdda" }] },
    "places/ca/eb1eed766420.json": SHARD,
    ...over.site,
  };
  const world = { "latest.json": LATEST, "place/be/be76926172b2.json?v=abc": { name: "Rivière", subtype: "locality", cc: "CA", quests: { AddA: [[0, 5, 0], [3, 7, 2]] } }, ...over.world };
  return { asked, registry: async () => REG,
           site: async (p) => { asked.push(p); return files[p] ?? null; },
           world: async (p) => { asked.push("world:" + p); return world[p] ?? null; } };
}
const preview = (query, load = loaders()) => { const p = q(query); return previewFor(askFrom(p), p, load); };

test("a city, a part, and a selection", async () => {
  assert.equal((await preview("city=toronto")).title, "80 open StreetComplete quests in Toronto");
  assert.equal((await preview("city=toronto&base=all")).title, "89 open StreetComplete quests in Toronto");
  const part = await preview("city=toronto&part=dbb37f753302");
  assert.equal(part.title, "Almost done: 20 StreetComplete quests left in Agincourt North, Toronto");
  assert.equal(part.description, "Down 10 since Oct 27. Most open: a 20. As of Nov 22, 2026.");
});

test("a counted place under its place id says the daily count, with or without ?in=", async () => {
  const load = loaders();
  assert.equal((await preview("place=9fc3a6b4bdda&in=ca/eb1eed766420", load)).title, "80 open StreetComplete quests in Toronto");
  assert.equal((await preview("place=9fc3a6b4bdda", load)).title, "80 open StreetComplete quests in Toronto");
  assert.equal((await preview("place=dbb37f753302&in=ca/eb1eed766420", load)).title,
    "Almost done: 20 StreetComplete quests left in Agincourt North, Toronto");
  assert.deepEqual([...new Set(load.asked.filter((p) => p.startsWith("world:")))], ["world:latest.json"],
    "a counted place reads no world place file (this latest.json has no city files)");
});

// The world's days of a city and its parts (latest.city, latest.cityParts): the page shows them on top of
// the city's history file, whose days end where the city run stopped.
const LATEST_C = { ...LATEST, date: "2026-11-27", city: "city/", cityParts: "city-parts/" };
const REG_C = REG.map((x) => ({ ...x, status: x.name === "AddB" ? {} : { toronto: "counted" } }));
const WORLD_C = {
  "latest.json": LATEST_C,
  "city/toronto.json?v=abc": { quests: { AddA: [[0, 80, 0], [20, 70, 5]], AddOff: [[0, 9, 0]], AddB: [[0, 500, 0]] } },
  "place/db/dbb37f753302.json?v=abc": { quests: { AddA: [[0, 25, 0], [10, 15, 0]] } },
  "city-parts/toronto.json?v=abc": { noFile: ["d00000000001"] },
};
const PARTS_C = { "data/parts/toronto.json": { parts: [{ id: "dbb37f753302", name: "Agincourt North", en: null }, { id: "d00000000001", name: "Empty Park", en: null }] } };
const loadersC = (world = WORLD_C) => ({ ...loaders({ site: PARTS_C, world }), registry: async () => REG_C });

test("a city's history file joined with the world's days, over the quests counted there", async () => {
  const city = await preview("city=toronto", loadersC());
  assert.equal(city.title, "70 open StreetComplete quests in Toronto");
  // 4 weeks before 11-27 is 10-30: the file's 10-01, its 11-22 replaced by the world's days
  assert.equal(city.description, "Down 30 in the last 4 weeks. Most open: a 70. As of Nov 27, 2026.");
  // AddB is in the world's file but not counted in Toronto
  assert.equal((await preview("city=toronto&base=all", loadersC())).title, "79 open StreetComplete quests in Toronto");
  assert.equal((await preview("place=9fc3a6b4bdda", loadersC())).title, "70 open StreetComplete quests in Toronto");
});

test("a part from the world's file, a part with no file says nothing open, else its history file", async () => {
  const part = await preview("city=toronto&part=dbb37f753302", loadersC());
  assert.equal(part.title, "Almost done: 15 StreetComplete quests left in Agincourt North, Toronto");
  assert.equal(part.description, "Down 10 since Nov 1. Most open: a 15. As of Nov 27, 2026.");
  assert.equal((await preview("city=toronto&part=d00000000001", loadersC())).title, "No open StreetComplete quests in Empty Park, Toronto");
  const { "place/db/dbb37f753302.json?v=abc": _, ...noPartFile } = WORLD_C;
  assert.equal((await preview("city=toronto&part=dbb37f753302", loadersC(noPartFile))).title,
    "Almost done: 20 StreetComplete quests left in Agincourt North, Toronto");
});

test("without the world host a city and a part are their files alone", async () => {
  const load = { ...loadersC(), world: async () => { throw new Error("down"); } };
  assert.equal((await preview("city=toronto", load)).title, "80 open StreetComplete quests in Toronto");
  assert.equal((await preview("city=toronto&part=dbb37f753302", load)).title, "Almost done: 20 StreetComplete quests left in Agincourt North, Toronto");
});

test("a world place takes the name layer's English name and its parent, else its own name and the country", async () => {
  const named = await preview("place=be76926172b2&in=ca/eb1eed766420");
  assert.equal(named.title, "7 open StreetComplete quests in Blind River, Ontario");
  assert.equal(named.description, "Up 2 since Nov 1, mostly resurveys coming due. Most open: a 7. As of Nov 17, 2026.");
  assert.equal((await preview("place=be76926172b2")).title, "7 open StreetComplete quests in Rivière, Canada");
});

test("nothing to say is null, so the page keeps its own head", async () => {
  assert.equal(await preview("city=nowhere"), null);
  assert.equal(await preview("city=toronto&part=000000000000"), null);
  assert.equal(await preview("place=000000000000"), null);
  assert.equal(await preview("city=toronto&base=none"), null);
  assert.equal(await preview("place=be76926172b2", loaders({ world: { "latest.json": { ...LATEST, schema: 1 } } })), null);
  assert.equal(await preview(""), null);
});
