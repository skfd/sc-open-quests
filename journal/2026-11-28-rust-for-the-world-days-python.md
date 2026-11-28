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

**Brought forward (00:40).** Owner: "I think I would like to start building now in work tree please". Asked which
step first (diff reader + small PBF, the row-file rewrites, or a scaffold until 19:00), the owner answered "work
autonomously thorugh the night pls". Chosen: the small PBF, then the diff reader; branch `rust-world-day`, worktree
`../sc-open-quests-rust-day`. Loop idle (no RUNNING, 11-27 done 17:27), 185 GB free.

**The first two steps, built and proven (00:45-01:20, branch `rust-world-day`, loop idle, nothing of ours beside).**
- `tilestore smallpbf --diff --loc --stamp --out` (`tilestore/src/smallpbf.rs`): `stream.write_small_pbf` rule for
  rule from the diff (`osc.rs`) and the planet's node file, read only. Kept on purpose: the synthetic nodes a way's
  earlier refs got stay when a later ref has no place (as the Python loop leaves them); a repeated tag key keeps its
  first place and last value; the counter's keys in the Python order, present only when non-zero.
- `tilestore diffcols --diff --out` (`diffcols.rs`, `osc::parse` split out of `osc::read`) and `stream.load_diffcols`:
  per kind the last version of each id at its first version's place, deleted ones too, as .npy columns and one tag
  file per kind; Python builds read_diff_osmium's dicts from them (UTC datetimes cached per second, places / 1e7).
  The first build shared one tag blob with per-kind offsets from 0, so ways read the nodes' tags; the unit test
  caught it before any real run counted.
- **Equal on real diffs** (`tools/stream/tilecheck/diffcmp.py`, `smallcmp.py`; node file `.scratch/planet-day/planet.loc`
  at 11-27, both sides reading the same file, so the check is valid whichever day the diff is):

| | Python | Rust | result |
|---|---:|---:|---|
| read diff 5189 (4,496,007 nodes, 691,583 ways, 35,604 relations) | 103.8 s | 22.7 s with the load | same keys in order, 0 values differ, 46,239 relation versions both |
| read diff 5185 (4,277,047 / 827,128 / 56,783) | 157.5 s | 23.9 s | equal |
| small PBF 5189 | 71.6 s | 12.1 s (8.7 of it reading the diff) | 5,059,037 objects, 0 differ, 0 ways unplaced |
| small PBF 5185 | 40.7 s | 18.2 s | 6,025,839 objects, 0 differ, 945 ways unplaced both |
| small PBF 5187 | 27.6 s | 17.0 s | 5,460,292 objects, 0 differ, 694 unplaced both |

- Wiring: `stream.read_diff` takes the Rust read for .osc/.osc.gz when the binary exists (`SCOQ_RUST_DIFF=0`: pyosmium);
  `world_day.finish` writes tier 1's PBF by `small_pbf_rust` on the planet's node file (`SCOQ_RUST_SMALLPBF=0`: Python),
  falling back to Python when the diff it read is not the day's (a rehearsal's `keep` narrowed it) and building the
  node overlay only when the Python writer needs it. `planet_store_day` pins `stream.TILESTORE` to the loop's daily
  copy, as it pins `WD.EXE`.
- Tests: `tests/test_rust_day.py` (3: the read, the PBF, the fallback). Affected tests 143 passed, full suite 476
  passed, 1 skipped (01:18). **Not yet run inside a real world day**; the saving is about 2-3 min of a 3.5 h day,
  as the survey expected for this step: the larger costs wait for 11-28's `steps.json`.

**Reviewed and closed out (01:20-01:50).** A review asked for four things before a merge; done:
- **The engine as the reader.** One tier 1 engine (main's install, world-1101's plan files f4 and f37, read only) on the
  Python and the Rust small PBF of 5189: the snapshots differ only in the source file's name, hash and run seconds; the
  dumps' bytes differ, but their rows with each place set spelled as part ids are equal (19,732 rows on f4, 7,675 on
  f37). The run-local set numbering is what differs; `placesets.ingest` remaps it by part id.
- **A merge without a rebuild** would leave the loop's daily binary without `diffcols` and `smallpbf`: both callers
  now log why and take the Python way (test with a stand-in binary that knows neither command).
- **Which reader ran** is on the day's read-diff line ("(tilestore diffcols)" or "(pyosmium, as ...)");
  day_metrics' patterns (`^tilestore read:` and the rest) match none of the new lines.
- **The small PBF's timings were order-biased:** with Rust first on diffs nothing had read (5188, 5186) Rust took
  55-64 s, Python after it 36-39 s on the warmed pages. The cost was the 115 GB node file's random page faults, one
  ref at a time. Now every ref the diff does not place is read once, sorted, on all threads: 5184 cold and Rust first
  17.9 s (node file 2.6 s for 2,309,544 refs), Python after it 32.3 s; equal, 1,258 ways unplaced both. Earlier
  "12-18 s" figures were Rust second (warm).
- Six diffs equal in all (5184-5189); full suite 477 passed, 1 skipped (01:40). The test PBFs deleted (the reports
  kept in the worktree's `.scratch/`).
