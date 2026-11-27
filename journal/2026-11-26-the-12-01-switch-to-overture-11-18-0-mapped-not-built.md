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
