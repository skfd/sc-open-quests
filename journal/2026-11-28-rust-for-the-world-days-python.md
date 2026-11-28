## Rust for the world day's Python: surveyed, the owner chose "world day only, later" (2026-11-28, 00:00-00:35)

Asked in a conversation about osmium (owner, about 00:05: "we need to consider replacing all python code with rust
please"). Read-only: nothing built, run or installed. The decision is in
design/topics/rust-for-the-world-days-python.md; this is the survey behind it.

**How it came up.** osmium is used two ways: pyosmium in the stream (`stream.py`, the old Python tile store) and
osmium-tool in Docker (`world_cells.py` cut, `backfill_history.py`, `add_parts.py`, the history-cut rehearsal).
Retiring the Python tile store (BACKLOG) removes only the tile store's pyosmium: `stream.py` keeps `read_diff`, the
node lookups through `osmium.index` (`DenseLocations`, read-only on the planet's node file since `tilestore loc
advance` writes it) and `write_small_pbf`, and the live world code imports it. No pyosmium-against-native benchmark
exists; 11-16 measured native osmium-tool against Docker's only (journal/2026-11-16-parked-benchmark-a-native-windows-osmium.md).

**The Python, 32,141 lines tracked** (`git ls-files '*.py'`; imports traced statically from the daily entry points
`run.py`, `planet_store_day.py`, `overture_release.py`, `world_publish.py`, `cloud_publish.py`, `spend_breaker.py`):
- **The world day's data work, ~8.8k, reached daily:** `tools/stream/` `planet_store_day`, `world_day` (1,156),
  `world_tier2` (1,073), `stream` (634), `store_context`, `tier2`, `world_state`, `qos`, `engine_room`, `day_metrics`,
  `notes_day`, `world_gate`, `place_counts`, `placesets`, `file_pool`, `day_cache`, `store_lock`, `storecheck_cities`;
  and `tools/world_cells.py` (922).
- **Other daily jobs, ~5.2k:** `run.py` (1,674; its city-run parts go with HANDOFF Next 7), `world_publish` (945),
  `overture_release` (1,136), `place_ids`, `backfill_history` (imported), `cloud_publish`, `spend_breaker`, `site_quests`.
- **Not run daily, ~9.9k:** the Python tile store (`tilestore.py` 1,005, `tiles.py` 395; not reached from any entry
  point), `proto/` 1,474, `tilecheck/` 1,031, `overpass/` 276, the Overture/places tools run by hand, one-offs, share
  card and Cloudflare scripts.
- **Tests:** 8,254 (50 files), several holding Rust against Python.
- **Third-party:** numpy (34 files), osmium (14), shapely (9), duckdb (8), pyarrow (3), PIL (2), playwright (1),
  timezonefinder, pandas. The Claude judge, the R2 upload and the headless-Edge share card are subprocess or HTTP glue.
- For scale: Kotlin 22,361 lines (the engine, stays), Rust 7,576.

**Where 11-25's day went** (12,643 s, then publish 1,155 s; journal/2026-11-26-performance-review-of-the-traces-and-logs.md,
mostly the agents' reading of the code, so estimates):
- Python's own steps about 4,000 s, overlapping (estimate): tier 1's serial rewrite 520, engine files 624 (558,000
  small files), tier 2 delta 819, counts and note quests 737 (part note engines), notes decompressed twice 436, cover
  254, read diff 162, places and old rows 160, the day's end 327.
- Not Python: the engines' memory waits about 45-50 min, tier 2's phases 5,384 s of wall, the Rust update 708 s, the
  points 438 s (since about 25 s with the points fix).
- The review guessed pools would save 2,000-2,500 s with no change of language; those pools were merged 11-26
  (`perf-python`, 81df89fd). 11-26 and 11-27 were resumed days with no `steps.json`, so **11-28 (from 14:45) is the
  first clean measure of what Python still costs.**
- One link to the biggest cost, unmeasured: on 11-24 the loop's own python reached 17 GB and took commit the engines
  were waiting for. A Rust step might hold the same rows in less.

**Asked as a wizard, the owner chose (00:33): "World day only, later (Recommended)":** write it down now; after the
12-01 cutover and release 1, read 11-28's `steps.json`, then port the world day's slow Python steps into the tilestore
binary one at a time, each proven equal over real days; the glue stays Python. The other options were "measure first,
decide then", "everything, after release 1" and "not now". This folds in the earlier offer of a BACKLOG line for
`stream.py`'s pyosmium parts.
