## The 12-01 switch to Overture 11-18.0: mapped, not built (2026-11-26, 18:00-18:30; owner: "we are going to do it on 12 01 right?")

Read by two explorers (code only, nothing run). Loop dead at 18:20 (pid 7908 gone, no engine), C: 105 GB free, v64.1 still
the newest quests file. **The switch = prepare (any time, new folders only) + cutover (under a hand-written HOLD, at the
store's day D).**

- **Builders read the live state, no flags:** `place_ids.load()` with no path in `places.py:431`, `world_cells.py:141`,
  `add_parts.py:74`; `world_cells.py places` reads fixed `data/overture/world` (the only 10-21.0 copy after about 12-20; never
  pull over it) and has no `--src`; every builder stamps `config/places.json`'s release, not the one read (`places.py:422`,
  `small_squares.py:384`, `world_cells.py:195`, `add_parts.py:204`); `config/small-squares.json` fixed for readers
  (`places.py:428`, `run.left_out_places`, `run.py:532`); `add_parts.py` writes `config/parts` and `data/boundaries/parts` in
  place and needs Docker osmium plus regional extracts (no longer fetched); `places.py build` deletes every `*.json` under
  `--out`, default `docs/places` (the live name layer); `places.py regionids` may run a Gradle build (`places.py:130`);
  `rel()` (`world_cells.py:120`) stores paths relative to ROOT. **Chosen: flags (registry, src, release, squares, outputs), one
  resolver per release, refusing any live output path.**
- **Prepare recipe** (N = `data/overture/2026-11-18.0`, NEW = `.scratch/planet/world-1118`): `overture_pull.py 2026-11-18.0
  --world --out N` and `--outlines --out N` (two runs, about 7 GB); `small_squares.py build --src N --out <new>` (2 min);
  `places.py build --src N --out <new name layer>`; `world_cells.py places --out .scratch/world-places/world-1118` (26 min,
  395 MB `places.json` last time; geo files named by our ids); NEW gets W's `nodegrid.json`, `cities.poly`, each file's
  `cities.json`/`bbox.poly`/`cells/` (linked) and the new `places.json`; `world_cells.py plan --grid NEW/nodegrid.json --out
  NEW --cities <all> --file-nodes 115e6` (chain4.sh:25-38, check the same 128 files); `partcache --out NEW` last (870 s,
  5.8 GB; stamped by `places.json`'s size and mtime). Open: does `config/parts` need rebuilding at all (ids are stable)?
- **Cutover recipe** (seed1101.sh minus its 11-01-only storecheck/history steps): loop finishes D, HOLD by hand (storecut's own
  hold ends with it, and the loop would take D+1 on the old world); pin `europe-D`; `storecut --at D` (46 min, +80 GB; needs
  the store at D, leaves it untouched); `notes` (4 min); `count --state` (canary f47, 2 engines at 30 GB, retry at 40 GB;
  2.4 h, +56 GB; delete the cut); `world_state seed` (54 min); `counts_at(NEW, D)` as notes1101.py (10 min; the seed's
  `counts` has no note quests); `world_gate.py NEW D --out NEW/days/D`. Then flip the world pointer and lift the HOLD.
  About 4.5 h. The horizon resets to D + 64.
- **Hard-coded world:** `WORLD` in `planet_store_day.py:60`; `world-1101` also in `world_publish.py:51`,
  `archive_backup.py:46`, `day_metrics.py:30`, `rename_places.py:46`, `world_compare.py:28`, `facts.py`; `FIRST="2026-11-01"`
  in `world_publish.py:55` (used by `run.py:1226`, `world_cities.py:106,137`, `facts.py`); `world_tier2` defaults. To make one
  pointer (the flip, and the rollback). **History join not built:** `gated_days` (`world_publish.py:172-189`) walks one folder
  without gaps; to try: hard-link the old world's `counts/<d>/` and `days/<d>/gate.json` into NEW, keep FIRST.
- **Publishing:** `MAX_DELETE` can be overridden (`--max-delete`, `--keep-gone`), but `daily` calls `upload` with defaults:
  under 2,000 deletes it deletes ended places' files unattended; **"ended page stays" is not implemented** (a place missing
  from the name layer is deleted, `world_publish.py:493,519`). The events cache is thrown away at the pin bump (`DAY_CAP`
  200,000 unchecked).
- **Disk is the hard limit:** 105 GB free; the cutover peaks about 80 GB (the cut) and nets about 112 GB with the old
  `world.bin` kept as the only fallback; the loop wants 115 GiB free to start a day.
- **Plan:** loop-imported modules edited in a worktree (the owner may lift the HOLD any time), merged only with tests green
  and behaviour unchanged before the flip; the cutover as a detached chain with step markers (background jobs die at 2 h);
  rehearsal = the full prepare + the f47 canary on the new list + a publish dry run counting deletes; before the first loop
  day on NEW (no way back): `world_gate` at D, and old vs new counts at D for the kept ids.
- **Owner, 18:35 (wizard):** disk: **the old world's `world.bin` files go once the new world passes its gate at D**, and **the
  regional extracts may be deleted early** (not Ontario, shared with kk-ontario-update; only if the space is needed, after
  checking whether `config/parts` needs them). Ended places: **files kept as they are (unmarked, frozen), nothing deleted,
  "ended" marking later** (so `daily` must publish with keep-gone before the first day on NEW). The laptop is back later
  tonight; the HOLD stays the owner's.
- **Built, on branch `overture-switch` (worktree `../sc-open-quests-switch`), not merged yet (19:30):** `data/world.json` names
  the world folder once (seven constants read it); `daily` publishes with keep-gone; `place_ids.release_inputs`/`refuse_live`
  and `--release` on `places.py build`, `world_cells.py places`, `small_squares.py build`; **`tools/overture_switch.py`**
  `prepare | cutover | adopt | status RELEASE`, resumable by markers in `<new world>/switch/`. Suite 426 passed. **Waiting to
  merge:** session sc-open-quests-5e has uncommitted loop edits in main (`planet_store_day.py`, `world_day.py`,
  `engine_room.py`, `day_cache.py`); asked to say when committed. Then: merge, `prepare 2026-11-18.0` (only between world
  days or under the HOLD), the f47 canary on the new list, a publish dry run counting deletes. `config/parts` not rebuilt
  (our ids are stable; ended parts show as `noFile`): a follow-up, so the regional extracts are not needed for the switch.
- **Merged 19:45 (06ac3b7d4, over sc-open-quests-5e's c3b998fd1; suite 440 passed).** The worktree is removed. 5e is running a
  resume proof on day 11-26 under the HOLD (`world_finish` reads WORLD via `data/world.json`). **Until 5e says done: no
  HOLD lift, no loop, no `prepare`.** Then `overture_switch.py prepare 2026-11-18.0`.

## 2026-11-27: prepare held for disk

- **05:10:** 5e's proof done ("You're clear to run `overture_switch.py prepare 2026-11-18.0`"). `status` showed every step
  undone. C: had 34.5 GiB free (131 GiB after 11-25's day): 11-26's mid-day footprint (`before/` with 11-25's rows, 22.5 GB of
  the day's work), which store_tail deletes once 11-26 passes its gate. 5e, a minute later: prepare "would take it to about
  30 GB. Running it after the owner lifts the HOLD and 11-26 completes is safer."
- Prepare's writes, from the live copies: `data/overture/world` 6.7 GB, `parts.cache` 5.5 GB, `places.json` 0.4 GB, names
  0.1 GB: about 14 GB, leaving about 20 GiB, under tilestore's 40 GiB floor. Held.
- The one large thing not in the loop's way: `.scratch/planet/world-places`, 64 GB (58 GB `files/`), the 11-13 planet count
  with places; `tools/world_publish.py` names its `report.json` in a docstring. Asked the owner whether it may go.
- 5e's note that two clean runs number a day's new place sets differently does not touch the switch's `compare`: it sums
  counts by part name (`open_by_part`), never by set id.
- **05:45, the owner (wizard):** "Wait for 11-26 (Recommended)": nothing deleted; prepare runs after the HOLD is lifted and
  11-26's store_tail frees its space, in a gap between world days.
- **09:20, the owner:** "start the day". HOLD moved to `.scratch/planet-cut/hold-history/HOLD-lifted-20261127-0921`, the loop
  task run by hand; it logged "day 2026-11-26: resuming (the store at generation 25, the world at 2026-11-26)". Prepare runs
  in the gap after 11-26's store_tail.
- **09:33:** 11-26 done (gate, then "punch skipped: 117 GiB free"); "no diff to 2026-11-27 on disk yet; done for now".
  09:48 publish exit 0 in 916 s. 117 GiB minus prepare's 14 GB would be under the 115 GiB a new day needs, so 14:45 would skip
  11-27. Asked the owner (wizard): **"Prune, then prepare (Recommended)"**: `osm_extracts.py prune <region> --keep 1
  --keep-days 0` for alberta, berlin, berlin-history, bremen, british-columbia, canada-germany, germany, hamburg, manitoba,
  new-brunswick, newfoundland-and-labrador, nova-scotia, quebec, saskatchewan, ukraine (Ontario, Europe, planet, notes
  untouched): 35 GB, 150.9 GiB free.
- **09:52:** `prepare 2026-11-18.0` started detached (venv python, `logs/switch.log`), 162 GB free by its own count.
- **Prepare's three fixes (09:55-10:06):** squares needs shapely (system python only; the venv lacks it), so squares and
  names run under system python; places under system python's duckdb 1.5.6 died twice at ~150 s with "INTERRUPT Error:
  Interrupted!" in `fetchmany` (also fully detached, so not a console Ctrl+C); under the venv's duckdb 2.0 it ran out at the 8GB
  limit in 9 s; with `memory_limit = '24GB'` (60 GB RAM free) it ran in 784 s. Detached jobs now start through a launcher
  with DETACHED_PROCESS, CREATE_NEW_PROCESS_GROUP and breakaway from the job.
- **Prepare done 10:26:** pulls 61 s and 134 s; squares 81,883, left out 64,199 (live 63,800); names 59 s (146 cities, city
  ids as live: Toronto `cdeece264a53` in `ca/ec52fcb974ff.json` both); region files 4,292 against 4,290 (Angola's regions
  redrawn: `ao/a2de740d5e25` ends, three begin; `hk/fe481f58e0b9` ends; `ws/ce87e16f04e4` begins); places 1,073,190, 403 MB
  (395 MB for 10-21.0); plan 128 files, 2,244 cells, checked equal to the old plan; partcache 5,806 MB in 344 s. 125 GiB free.
- **adopt-names keeps ended region files** (`keep_ended`): replacing docs/places would have dropped the two ended ones from
  the site; the owner's "nothing deleted" keeps them as they were.
- **Canary on f47 (10:26-10:34):** storecut f47 at 11-26 (0.53 GiB, 23 s), notes, then f47 counted with the old and the new
  place list on the same cut and notes: old 13,422 parts (55 s), new 13,463 (49 s); in both 13,405, equal in every quest
  13,193, differing 212; only old 17, only new 58; open summed over parts 60,490,634 against 60,499,562; f47 has no cities;
  largest moves -444 and +758.
- **Publish estimate:** against `bucket.json` (969,503 place files, 93,515 children files): the new name layer changes 729
  place files (name 421, subtype 287, both 20, country 1), parents of 748 places (at most 563 children files); 630 published
  places are not in the new layer (kept). The series of the ~1.6% of places whose outline moved change too: about 16k files at
  the world's scale, on top of a day's ~60k; DAY_CAP 200k holds (estimate). The release stamp is in `events.key`, so the first
  build after adopt rebuilds the events cache from every gated day.
- **10:45, the owner (wizard), when to cut over:** "After 12-01's day (Recommended)": the loop takes 12-01 on the old world
  at 14:45, the cutover starts when it ends (D = 12-01), adopt follows, the owner lifts the HOLD before midnight.
- **Disk across the cutover:** about 118 GiB after a day; the cut peaks +80 GB; the new world keeps about 65 GB (the old one's
  `files/*`: world.bin 52.6 GiB, world-keys 7.9, notes 2.2); even with the old world.bin gone, about 110 GiB, under the 115 a day
  needs. **10:48, the owner:** "Delete files/ now (Recommended)": `.scratch/planet/world-places/files/` (128 folders, the 11-13
  count's world.bin) deleted; its report.json (crosscheck), plan.json (test_world_tier2) and places.json stay. 178 GiB free.
- **11:00, the owner, on a full dress rehearsal of the cutover:** "we will do it live, no rehersal please". The cutover's first
  run on real data is 12-01's.

## 2026-11-27 (afternoon): the deleted files/ held the live world's cells

- **14:51, 11-27 stopped** (found by sc-open-quests-5e): tier 1's t1/f0 found no
  `.scratch/planet/world-places/files/f0/cells/f0c0.json`. The 10:48 delete above was described as "the 11-13 count's
  world.bin": it also held `files/*/cells/`, and world-1101's `files/*/cities.json` point all 2,244 cell boundaries there
  (world-1101 was set up from world-places and kept its paths). Nothing checked the live world's paths before the delete.
  5e restored the 2,244 cells (3.2 MB, from world-1101's own `files/*/cells`); the owner chose "Restart now", resumed 15:49.
- **What points where (checked 16:10, every string in the small files and the head of places.json):**
  world-1101: `files/*/cities.json` into `.scratch/planet/world-places/files/F/cells` (2,244, now present again);
  `plan.json` cityParts into `.scratch/planet/world-places/geo/` (147, present); `places.json` geometry into
  `.scratch/world-places/world/geo/` (present). world-2026-11-18.0: cities.json into its own `files/F/cells` (2,244),
  plan.json into its own `geo/` (147), places.json into `.scratch/world-places/2026-11-18.0/geo/`; all present. So the
  cutover and the new world have no path into anything deleted; the restored cells matter only while world-1101 is live.
- **Repointing world-1101's cities.json to its own cells: not done.** It is a write into the live world for a world that
  retires at 12-01's adopt; the 3.2 MB stay until then and go with the old world's world.bin once the new gate at D passes.
