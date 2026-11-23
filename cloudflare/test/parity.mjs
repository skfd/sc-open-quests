// The preview's number against the published data: for every city, ?city=<id> must say the `open` that
// docs/data/cities.json carries (the app's default quests on the city's newest day), and a link to the
// city by its place id must say the same. Run: node cloudflare/test/parity.mjs [docs]. Exit 1 on a miss.
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { askFrom, previewFor } from "../src/preview.js";

const docs = process.argv[2] || path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "docs");
const read = async (p) => { try { return JSON.parse(await readFile(path.join(docs, p), "utf8")); } catch { return null; } };
const quests = await read("data/quests.json");
const registry = quests.quests.map((q) => ({ name: q.name, defaultDisabled: !!q.defaultDisabled }));
const load = { registry: async () => registry, site: read, world: async () => null };
const nf = new Intl.NumberFormat("en-CA");
const cities = (await read("data/cities.json")).cities;

let missed = 0, checked = 0;
for (const c of cities) {
  for (const query of [`city=${c.id}`, c.place ? `place=${c.place}` : null].filter(Boolean)) {
    const params = new URLSearchParams(query);
    const meta = await previewFor(askFrom(params), params, load);
    checked++;
    if (!meta || !meta.title.startsWith(`${nf.format(c.open)} open StreetComplete quest`) || !meta.title.endsWith(` in ${c.name}`)) {
      missed++;
      console.log(`MISS ?${query}: cities.json says ${c.open} in ${c.name}; the preview: ${meta ? meta.title : "none"}`);
    }
  }
}
console.log(`${checked - missed} of ${checked} links say cities.json's number`);
process.exit(missed ? 1 : 0);
