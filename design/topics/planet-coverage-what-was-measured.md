## Planet coverage: what was measured (2026-10-24)

The owner asked for planet coverage. Before building, four checks; the owner's choices are still open
(HANDOFF.md, "Planet coverage").

- **Clipping keeps the counts exact.** Ontario clipped to its cities' bboxes padded by 2 km
  (`osmium extract -s smart`, 46 s, 985 MB to 339 MB, `--output-header=osmosis_replication_timestamp=...`
  or the engine refuses the file) gives the same snapshot, grid and quests.json as the published
  2026-10-23. One relation more lands "in some city" (a route or boundary losing far members); no count
  moves. A production clip should keep `-S types=multipolygon,boundary,route` (not yet run).
- **Heap follows the biggest city, not the extract.** The 34 GB peaks are a lazy collector under
  `-Xmx40g`. Ontario runs in 12-16 GB, clipped or not; Berlin's 7.9M nodes need 4-8 GB, all of it
  the whole-city area pass. Time is the same story: about 150 s of Ontario's 188 s is the area pass.
  So the planet is not a memory problem once it is clipped to city envelopes; a Tokyo or a Chongqing
  is, and needs an area cap or a split.
- **Engine limits for arbitrary countries** (file:line in the session report, summarised):
  at most 64 cities per run (a 64-bit city mask, AreaPass.kt); one time zone and one output folder per
  run (Main.kt, run.py), so a region cannot be split into two runs on one extract; only 16 of SC's
  country_metadata files are bundled, and a missing one falls back to default.yml silently;
  `add_city.py` needs country codes and zone typed by hand and its `slug()` drops non-ASCII names;
  notes are clipped once per region (46 s each, the whole dump each time); osm-extracts knows 12 URLs
  and has no replication diffs. Already global: SC's boundaries.ser, quest gating, geometry, the grid.
- **Cities from Wikidata** (P1082 population, P402 relation; `.scratch/world-cities/`):

  | population at least | settlements and municipalities | with an OSM relation | of those, not province-sized |
  |---|---|---|---|
  | 1M | 732 | 536 | 255 |
  | 500k | 1,313 | 898 | 594 |
  | 250k | 2,482 | 1,602 | 1,287 |
  | 100k | 6,001 | 3,666 | 3,342 |

  P402 is missing for nearly all of India, Pakistan, Bangladesh and Egypt, and half of Russia and China;
  where OSM has the boundary it often links the parent province item instead (Istanbul, Izmir, Tokyo).
  "Province-sized" is mostly China's prefecture-level cities (Chongqing 82,403 km²), Turkey's
  metropolitan provinces and Tokyo-to. Wikidata areas and populations are often wrong by a factor.
- **Publishing breaks first, and already at today's size.** GitHub Pages publishes at most 1 GB.
  `docs/` holds 334 MB, 316 MB of it the 1,485 snapshot files kept forever, growing 2.5 MB a day: the
  cap is about 9 months away with no new city. A snapshot is 21.8 KB per city, history 1.2 KB per city
  per date, and the compare view downloads every region's snapshot. At 1,000 cities the monthly history
  alone is 2.6 GB. Fix, needed regardless of the planet: publish only the newest snapshot per region
  (archive outside `docs/`), a small per-quest file for compare, and at a few thousand cities daily data
  out of git (R2 or release assets).
- **Disk.** 151 GB free on C:, with the 163 GB planet history file in the store. A planet pbf is about
  85 GB more.
