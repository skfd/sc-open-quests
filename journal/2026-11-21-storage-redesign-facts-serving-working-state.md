## Storage redesign: facts, serving, working state (owner, 2026-11-21, 13:10)

- Owner: "we store data in a shape too close to how we publish it, and do not publish/back it up. how should we do
  it properly?" Proposal accepted in a wizard, all four as recommended: Parquet + DuckDB for the canonical counts;
  a public copy under ODbL at `sc-data.comentality.com/facts/`; the world's row files checkpointed to R2 monthly,
  two kept; `docs/data` out of git after the builders read facts. The design and the six steps are in DESIGN.md,
  "Storage: facts, serving, working state".
- This is independent of schema 2 (`world-stable`): that changes a serving shape, this changes what serving is
  built from. The world publisher keeps reading `W/counts/<D>/` until step 4.
- **Step 1, the counts: done (13:45, c8134f5e).** `archive_backup.py` also copies the world's gated days
  (`counts/<D>/`, `days/<D>/day.json` and `gate.json`, plus `plan.json` and `world.json`) to
  `sc-open-quests-archive` under `world/`; a day without a passed gate is left out, and a checkout without the
  world folder skips it. `--only archive|grid|world`, `--world <folder>`. First run by hand: 13 days, 11-01 to
  11-13, 53 files; `--check --only world`: 53 equal, 0 missing or different. The daily city run does it from now
  on as its last step (each new gated day is about 140 MB). To restore: `rclone copy
  r2:sc-open-quests-archive/world .scratch/planet/world-1101`.
- **Not started:** the state checkpoint (wait for the catch-up to end and a day to close: the loop replaces the
  row files while it runs), and steps 3 to 6.
- **Owner, 13:25 (wizard):** switch to Parquet; the backfill **keeps running** and pauses between two days only to
  swap in the new code and the upgrades; the list of upgrades is dug out and proposed for the owner to confirm or
  cut; **schema 2 lands first**, the publisher's input moves to facts after it.
- **Step 2 built (13:33, 6e5d11c6): `tools/facts.py`**, tests `tests/test_facts.py`. `cities` and `world` write
  `data/facts/{counts,places}/source=<S>/date=<D>/data.parquet` (not in git) from the archive's snapshots and the
  world's gated days; `verify` rebuilds each snapshot (keys, values, order) and each world day (arrays) from its
  facts and compares. Bremen: 148 days, 0 different, 3.5 MB against the snapshots' 13 MB. The run over everything
  (2,282 snapshots, 13 world days, then `verify`) was started 13:34 beside the daily city run, so a snapshot that
  run rewrites meanwhile may show as different: rerun `cities` and `verify` before reading that as a fault.
  DESIGN's path (`facts/source=world/date=<D>.parquet`) is now a folder per day, so DuckDB reads source and date
  off the path.
- **The catch-up will stop at day 11-19 (found 13:40, checked).** `~/Code/.osm-data/europe/` has clips for 11-14 to
  11-18 and 11-21 only: the daily city run was down 11-19 to 11-21, so no clip of 11-19 or 11-20 was made, and
  `planet_store_day.py` (`diff_to`) writes STOPPED when a day has no clip to gate against. The loop is on 11-14,
  so it gets there in about a day. Not acted on; put to the owner with the upgrade list.
- **Do not edit `tools/stream/world_tier2.py` or `notes_day.py` on main while the loop runs:** they start
  ProcessPoolExecutor workers, which on Windows import those files from disk again, so an edit reaches the running
  day. The Rust binary is safe (the loop runs its own copy); `installDist` of the engine is not.
- **Upgrade candidates for the loop, surveyed 13:40 (not decided):** tier 2's engines are 55-73% of a day's
  `finish` (7,365 s on 11-12, 16,426 s on 11-13; DESIGN estimated 40 min); punch is slow, cause unknown, and is
  skipped every day; `world_publish.py build` to be wired in after schema 2; facts written as a day's last step;
  each run its own output file (the 14:45 task exits 1 on the held `planet-store.out`); the task's 6 h limit
  against 11-13's 6 h 56 min; no log line for hours during tier 2; the untraced gate differences; the hiking-route
  marking that can go; a container wider than about 7 km not found.
- **The proof over everything passed (about 14:30):** `facts.py verify` rebuilt 2,295 days (2,282 snapshots, 13
  world days) from their facts, 0 different or missing. On disk: the world's counts 2.0 GB (159 MB a day), all
  the rest of `data/facts` 177 MB against the archive's 559 MB of JSON. Snapshots the daily run adds are picked up
  by the next `python tools/facts.py cities` (nothing runs it daily yet: step 4).
- **Owner, 14:05: "agree with your assessment, go ahead."** So: (a) cut the two missing clips from 11-18 plus a
  diff each; (b) at the first swap: facts as a day's last step, an output file per run, the task's time limit,
  a progress line in tier 2; the publisher's build follows schema 2; the state checkpoint at the same pause; (c)
  tier 2's engine time investigated in a worktree while the loop runs; the slow punch, the gate differences and
  the last row wait until the loop has caught up. **The last row (drop the hiking-route marking; find containers
  wider than 7 km): when its time comes, first explain it to the owner and ask for the go-ahead. Do not build it
  unasked.**
- **(a) done (13:47 and 13:56 by the files' clock): both clips exist.** `europe-2026-11-19.osm.pbf` (sequence
  5181, from 11-18) and `europe-2026-11-20.osm.pbf` (5182, from 11-19), nodes in ways missing 0 after the API fill
  (34 to 0 on 11-20; those few nodes are the API's current ones, as on any day); `latest.json` still names 11-21,
  the clip's last sequence still 5183, no work file left. About 7 min a day. So the loop has a clip for every
  day through 11-21. Committed in `../osm-extracts` ("fill: the dated files a clip lacks between two it has").
  How it works: `python osm_extracts.py fill europe`
  (`fill_clip`): for each sequence a clip lacks between two dated files, the
  day before's file plus one diff, cut back to the polygon, stored as a dated file with `"filled_in": true` in its
  meta; latest, the clip's last sequence and pruning untouched. It should leave `europe-2026-11-19.osm.pbf`
  (sequence 5181) and `europe-2026-11-20.osm.pbf` (5182); the loop pins a clip past its clock on sight.
- **(c) tier 2's engine time, analysed 14:50 (read-only; nothing built).** Measured from the per-engine lines of
  `logs/planet-store.out`: the time is skew, not volume. 11-13's D-1 pass: 128 engines, 30,055 s summed, 8,600 s
  wall, median 34 s, and 11 engines over 600 s hold 72% of the sum; 11-12's wall (3,999 s) is one engine (f3,
  3,971 s). The same files are slow every day: f3 (the Atlantic strip, about 4,000 s a day since 11-08), f53,
  f107, f127, f47, f69, f109. D and D-1 cost the same. The design's fit predicts about 8,100 s for 11-13; f3 took
  114 s in the design run. JVM start-up (about 5%) and the reads (1,100-1,300 s a day) are not the cost.
  **Inferred, not measured:** `AreaPass.kt` (829-838) rebuilds a relation's whole geometry from all its member
  ways for every rectangle holding it, and `areaCities` defaults to 1, so a slow engine probably runs its
  rectangles on one core. Candidates, in order: cache a relation's geometry within an engine run (`AreaPass.kt`
  only, exact by construction); `-Dopenquests.areaCities=4..6` for tier 2 (`world_day.py`, one line); one pool
  for both dates, largest first (8-13%). Dropping the D-1 recount is not exact: not proposed. Not determined:
  what the slow engines do inside, their cores, why f3 jumped on 11-08, why 11-13 had 11 slow groups against 5.
  **A probe is waiting for 11-14's tier 2** (`.scratch/t2-probe/probe.sh`, started 14:55, reads only): it keeps
  f3's `old.osm.pbf`, json and parts and its `engine.log` (per-rectangle seconds and relation counts) in
  `.scratch/t2-probe/2026-11-14/`, and samples the java processes' cores into `probe.log` there. Read those
  before choosing; an offline rerun of f3 with `-Dopenquests.assembleTrace=true` only once the loop is not using
  every core.
- **(c) measured on 11-14's live run (16:00), and the cause is the relations.** From the engines' own logs
  (kept in `.scratch/t2-probe/2026-11-14/logs/`): f31 2,234 rectangles, 932 of 959 s in "map data"; f23 872 of
  905 s; f24 498 of 565 s; f2 433 of 468 s; all of it in rectangles that hold a relation (0 s in those that hold
  none), 1-6 s for a rectangle of two thousand nodes. Three engines sampled over 20 s used 0.95-1.29 cores each
  (24 threads free). f3 was not slow on this day (pass 148 s), so the survey's "f3 every day" attribution, which
  guessed group ids from start order, is not to be trusted; the skew itself is measured. The first probe hung on
  `t2/parts` (308,583 files: never list or copy that folder whole) and hit its 2 h limit without sampling.
- **(c) fix built, not merged: branch `t2-relcache`, worktree `.claude/worktrees/t2-relcache`, b7150976.**
  `AreaPass.kt`: `relationWithGeometry` once per relation and run (`relationCache`, soft references,
  `-Dopenquests.relationCache=false` turns it off) instead of once per city holding it; nothing of it depends on
  the city. Built there (`installDist`, JDK 21). **A/B on f3, 16:20: the same rows, twice as fast.** Cache off
  pass 109.5 s, on 54.5 s (peak heap 5,286 against 4,752 MB); 695,396 rows each, none on one side only, between
  off and on, and between each and the loop's own f3 dump; the snapshots equal but for `runSeconds`. Compare
  dumps with `.scratch/t2-probe/samerows.py <dir> <dir>`, never by bytes: a dump numbers its place sets in the
  order threads met them, so two runs of the same engine differ in bytes (`ab.sh`'s own `cmp` says DIFFERENT for
  that reason). f3 is a fast group; the gain on a slow one is still to measure. **A/B started 16:10** (`.scratch/t2-probe/ab.sh`, results in
  `.scratch/t2-probe/ab/<name>/`): f3's kept D-1 inputs through that engine with the cache off and on, the dumps
  and snapshots compared byte for byte, and against the loop's own f3 dump. `.scratch/t2-probe/keep.sh` is
  waiting to keep f31's and f23's D inputs (the slow ones) for the same A/B. It goes in at the swap with
  `installDist` on main, **never while the loop runs** (the loop starts the installed engine).
- **(c) the gain on slow groups, measured (18:30).** f31's D inputs of 11-14 (2,234 rectangles, kept by
  `keep.sh`): cache off pass **1,191.0 s**, cache on **17.3 s**; 220,264 rows each, none on one side only
  (`samerows.py`); "map data" 1,180 s against 1 s. f107, the day's slowest (4,955 rectangles; its D-1 pass took the
  loop 4,050.9 s, peak heap 8,617 MB): D inputs with the cache on, pass **78.1 s**, peak heap 7,182 MB; its rows
  are being compared with the loop's own f107 D dump when that engine ends (kept in
  `.scratch/t2-probe/2026-11-14/loop-f107-new/`; no cache-off run of f107 was made, it would be over an hour).
  Kept inputs: `.scratch/t2-probe/2026-11-14/{f31,f23,f107}/` and `parts-f*`; results `.scratch/t2-probe/ab/`.
  `ab.sh` takes `MODES=on` for one run. So a day's tier 2 engines should fall from hours to minutes; the day then
  costs what the rest of `finish` does (about 1.5 h on 11-12 and 11-13).
- **Why six rounds of engine speed-up missed it, and what watches for the next one (owner, 19:10: "why didn't
  we do it when optimizing engine? ... keep collecting metric or at least observing").** Every round measured one
  file, Germany f0: 18 large cells over 113M nodes, where a relation is made 18 times at most and the collector
  and the quests' runs are the cost. Tier 2 is the other shape, thousands of small rectangles over one file, and
  was never a benchmark; its design run (`.scratch/rectgroups`) happened to have no long relation in many
  rectangles. In production the evidence existed but was thrown away: `engine.log` has a line per rectangle and
  goes with the day's work, and the loop's log named no engine. **Built on `world-swap` (f0814ae6):
  `tools/stream/day_metrics.py`**, test `tests/test_day_metrics.py`. At a day's end, before the work is deleted,
  every engine's log becomes numbers in `W/days/<D>/engines.json` (per engine: areas, map data seconds, the
  quests' seconds, main pass steps, heap, the three slowest areas; per phase: sum, median, longest, the five
  longest's share), backed up with `day.json`; the loop's log gets a line per phase and a `watch:` line for an
  engine over 120 s that is 10 times its phase's median with one step holding half of it. `python
  tools/stream/day_metrics.py report` lists the kept days. **11-14 so far, the old engine** (harvest of the live
  work at 19:15, the D pass not ended): t2 old 127 engines, 32,470 s summed, median 42 s, longest 4,287 s (f53),
  map data 27,262 s (84%), quests 1,111 s, main pass 943 s; t1 128 engines, 1,062 s. `.scratch/t2-probe/baseline.sh`
  (detached) harvests the whole day when its finish ends and puts `engines.json` beside 11-14's `day.json`: the
  "before" to hold the first day with the cache against.
- **Metrics for everything a day runs, not only the engines (owner, 20:05: "i want it collected for rust etc
  but not necessarily in the same place. as long as we can then read it and find optimisations").** On
  `world-swap` (0c897d6f; 21 tests pass): `day_metrics.py` also writes **`W/days/<D>/steps.json`**, read off
  `logs/planet-store.log` after the day's `done` line: every step the loop times whatever ran it (the Rust tile
  store's update, loc advance, loc check, cut, subcmp, compact, punch; prepare's and finish's own parts; the gate
  per region; the reads' count and seconds; the update's own JSON; each pack's dead share), the day's wall
  seconds and the seconds in no step (11-10: 7,434 s, the wait beside the daily run). A `watch:` line for a step
  at twice its median over at least three earlier days and 300 s over it. `engines.json` also carries the tile
  store's reads per tier 2 date (seconds of tiles, merge, write; bytes; the most memory; the three longest), from
  the `<pbf>.json` each `tilestore read` leaves. **Backfilled 20:10 for 11-02 to 11-13** from the log (11-02 and
  11-03 are partial: their days ran before this log's last run of them). `python tools/stream/day_metrics.py
  report` prints both tables. What it already shows: without tier 2's engines a day is about 7,000-8,500 s (reads
  about 1,200, prepare 750-950, tier 2 delta 600-870, tier 1 about 800, update about 700, counts and note quests
  about 600, engine files 420-960, store context before 300-490 and **after 346-1,117, flagged on 11-09 and
  11-12**). Not in it: what a Rust command does inside beyond the numbers it prints (the update's JSON is kept
  whole), and Python steps the log does not time.
- **f107, the last check before the swap (20:26 by the clock): the same rows.** The loop's own D pass of f107 on
  11-14: 3,870.6 s, peak heap 8,444 MB. The same inputs with the cache: 78.1 s, 7,182 MB. 2,940,732 rows each, none
  on one side only (`samerows.py 2026-11-14/loop-f107-new ab/f107-new/on`).
- **THE SWAP IS DONE (21:08-21:12 by the log; the pause was 3 min 20 s).** 11-14 closed at 21:07:53, gate ok (20
  of 32 equal, +11 of 19,288,012), the loop ended under HOLD after 11 days. Then: `world-swap` merged into main
  (fast-forward; `t2-relcache` is in it) and both worktrees can go; `installDist` on main (the engine's source is
  byte for byte b7150976's: `git diff b7150976 HEAD -- engine` is empty); 21 tests pass;
  `state_checkpoint.py link`: 128 files, **52.5 GiB of rows**, `.scratch/planet/checkpoint/2026-11-14/`;
  `facts.py world`: 11-14 written (27,747,364 rows, 159 MB); the task `kk-SCOpenQuests-planetstore` now runs
  `python tools\stream\planet_store_day.py` with no redirect, limit PT12H (next 11-22 14:45; it steps aside while
  a run holds RUNNING); HOLD removed; **the loop restarted 21:11:13, pid 13948, `--max-days 20`, on 11-15** (its
  prints in `logs/planet-store-20261121-2111*-13948.out`; it pinned the clips of 11-19, 11-20, 11-21 on sight).
  - **A first restart at 21:10 sat waiting "for today's daily run" and was killed (pid 19596, nothing begun).**
    The city run of 16:46 died of `OutOfMemoryError` at 17:25 (`-Xmx13g`, beside the catch-up) and so never logged
    `update done`; `daily_run_going()` took that for a run still going and would have waited 3 h. Fixed
    (5651c2ce): an `] ERROR:` among the day's last lines ends the run too.
  - **The city task was not run in the pause:** its download alone took 36 min today, over the hour allowed. The
    cities are at 11-18. With tier 2's engines down to minutes the machine should have the heap for the
    scheduled run on 11-22; if it fails again, run it by hand between two world days.
  - **The installed engine was not smoke-run on the kept inputs:** the kept `cities.json` files point at the day's
    cell outlines under `world-days/2026-11-14/work/t2/cells/`, which went with the day. The kept inputs under
    `.scratch/t2-probe/2026-11-14/` can no longer be rerun; the A/B results stand. The first proof of the
    installed engine is 11-15's gate.
  - **Running beside the loop since 21:13, detached** (`logs/state-checkpoint.log`):
    `state_checkpoint.py upload` (133 files to `r2:sc-open-quests-archive/state/2026-11-14/`, `done` last), then
    `archive_backup.py --only facts`, then `--only world` (11-14 with its `engines.json`, and the backfilled
    `steps.json` of every day).
  - **To check when 11-15 closes:** its gate; `python tools/stream/day_metrics.py report` (11-15's engines against
    11-14's: t2 old was 32,470 s summed, 84% map data); the `facts:` and `steps:` lines in the log; the `watch:`
    lines. If the gate fails: `-Dopenquests.relationCache=false` in tier 2's `opts` (`world_day.py`), under HOLD.
- **11-15, the first day on the new engine: gate PASS, 2 h 47 min (21:11:13 to 23:58:23).** 20 of 32 cities
  equal, clip 19,290,909, world 19,290,920 (+11), worst city 0.00159%: the same margin as every day before, so the
  cache changed no count the gate sees. The day 10,030 s against 11-14's 36,923 (10 h 15 min) and 11-13's 24,992.
  `finish` 7,973 s: tier 2 engine **2,462** (was 7,205-22,986), tier 2 reads 1,775, tier 2 delta 823, tier 1 751,
  counts and note quests 599, engine files 523, store context after 454; prepare 724, update 668. Engines
  (`engines.json`): t2 old 127 in 6,344 s summed, median 36 s, longest 302 s, **map data 283 s** (11-14: 32,470 s
  summed, 27,262 s map data, longest 4,287 s); t2 new 6,463 s; heap up to 10,679 MB. No `watch:` line. `steps:`,
  `engines,` and `facts:` all wrote (11-15's facts 159 MB in 15 s). 11-16 began 23:58:38.
  - **The checkpoint is in the bucket and whole (about 23:00):** `state/2026-11-14/`, 134 objects, 57,239,496,536
    bytes, `done` written; `state_checkpoint.py list` says whole. Its log's "uploaded 22 files" is a miscount of
    rclone's lines (multi-part copies log differently); the size check passed for every file. Then
    `archive_backup.py --only facts` (4,592 files) and `--only world` (14 days, 70 files) ran.
  - **At this pace** 11-16 to 11-21 are six days of about 2.8 h, plus the daily window's pause: the catch-up
    reaches 11-21 about 17:00-19:00 on 11-22, so the owner's 18:00 has 11-20 for sure and 11-21 maybe.
  - **What the metrics point at next (not built, for the owner):** tier 2's engines are now 12,807 s summed on 4
    workers for 2,462 s of wall, the quests' runs and the main pass in equal parts and no skew, so **more workers**
    is the cheap lever (`WORLD_T2_WORKERS`, set to 4 in `planet_store_day.py`; a group's heap reached 10.7 GB, the
    machine has 87 GB and the city run needs its 13 GB); **tier 2 reads 1,775 s** (the Rust `tilestore read`, one
    at a time by design: "the reader uses the threads") is the largest single step after them; tier 2 delta 823 s
    and tier 1 751 s follow.
- **Cities paused for the world's backfill (owner, 2026-11-22 01:20: "you can pause city processing in favour of
  finishing up world backfill. do cities after backfill is done. cities are the vestigial feature, we are keeping
  still, useful, but lower priority than world processing").**
  - Task `kk-SCOpenQuests` is **disabled** (01:25). `data/cities.paused` exists (not in git), and while it does
    `backfill_history.wait_for_quiet` waits for nothing (c76202ee), so the loop no longer stands still from 11:55
    to 14:15 local. The cities are at 11-18.
  - The running loop still has the old rule in memory: **HOLD placed 01:30** for a restart at the next day
    boundary (11-16's close, about 02:45). `.scratch/restart-after-hold.sh` (detached; `logs/restart-after-hold.log`)
    removes HOLD and starts the loop again once the run has ended cleanly; it does nothing if STOPPED is there.
  - **To resume the cities, once the loop has reached today:** `schtasks /Change /TN kk-SCOpenQuests /ENABLE`,
    delete `data/cities.paused`, `schtasks /Run /TN kk-SCOpenQuests`; then `python tools/facts.py cities`. The
    days 11-19 to today's eve cannot be counted for the Canadian and German regions (Geofabrik's extracts are
    today's only); Europe's clips of those days exist.
- **More tier 2 workers: asked for by the owner (01:20), measured, not done.** With 4 workers the machine is at
  94% CPU on average during tier 2 (60 s of samples at 01:20: min 81, max 100; 24 threads; each engine runs its
  quests on all of them), with 21-28 GB of memory available. The engines' 12,807 s on 11-15 were not waiting for a
  worker but for cores. More workers would add memory pressure for no time. Told the owner.
- **The loop stopped on a full disk at 01:43 on 11-22 and stood still until 07:12; the checkpoint's links did
  it.** 11-16's tier 2 engine f116 failed with `IOException: There is not enough space on the disk`; STOPPED; the
  restart helper rightly did nothing. Found at the 07:05 check: 8.5 GB free. Cause:
  `.scratch/planet/checkpoint/2026-11-14/` held hard links to the 128 row files as they were at 11-14; each day the
  loop replaces every file, so the links kept 54 GB of old rows alive, beside the day's own `before/` (another
  54 GB once tier 1 has replaced the files). Free space at a day's end went 129 GiB (11-14) to 72 (11-15), and
  11-16 ran out in tier 2. The upload had ended about 23:00; the links should have gone then.
  - **Fixed by hand (07:10):** the bucket copy checked whole, the local links removed (62 GB free, 114 after the
    loop put the world back), STOPPED and HOLD removed, **the loop restarted 07:12:26, pid 12048**: "day
    2026-11-16: resuming (the store at generation 15, the world at 2026-11-15)", the documented resume (the world
    from `before/`, `finish` again from `day.pkl`). The restart also picks up the paused-cities rule.
  - **Fixed in the tool:** `state_checkpoint.py upload` removes the links it uploaded; `link` refuses unless the
    disk has twice the rows and 40 GiB free (it does not today: 114-126 GiB at best); `upload --from-world` takes
    the checkpoint with the loop held (HOLD, no run), from the world's own files, the loop standing still about
    an hour and a half. On this disk the monthly checkpoint is that.
  - **Cost:** 5 h 29 min of standstill and 11-16's finish done twice (about 1 h 45 min of it lost). At 2.8 h a day
    from 11-16's close (about 09:30): 11-17 about 12:20, 11-18 about 15:05, 11-19 about 17:55, 11-20 about 20:45,
    11-21 about 23:30. So the owner's 18:00 has 11-18 for sure and 11-19 on the edge, not 11-20 or 11-21.
  - **Not built, worth having:** the loop taking no day when the disk has less free than a day needs (about
    75 GiB: `before/` and the work), instead of failing in the middle of one.
- **11-16 closed 09:59:32 on 11-22, gate PASS** (20 of 32 equal, clip 19,294,535, world 19,294,546, +11, worst
  city 0.00159%), after the 07:12 resume: `finish` 9,083 s (tier 2 engine 2,938, tier 2 reads 1,696, store
  context after 831, tier 1 751). Disk: 51 GB free at the day's low (09:46), **142 GiB at its end**. 11-17 began
  09:59:33. **The first `watch:` lines of the new engine: f116, 658 s (D-1) and 708 s (D), 18-20 times the
  median, with 32,222 rectangles** in one group (its earlier log: pass 413 s of 704 total, so about 290 s is
  outside the pass: start-up over 32,222 cities and their parts, or writing the dump). Not map data (248-285 s
  for the whole phase). A candidate: split a group by its number of rectangles, not only by area
  (`WORLD_T2_GROUP_KM2`), or look at what start-up does per city. Not built.
- **11-17 closed 12:38:41 on 11-22, gate PASS** (+11 of 19,301,653), 9,548 s (2 h 39 min): tier 2 engine 2,174 s,
  reads 1,722. The loop did not stand still in the 11:55-14:15 window (the paused-cities rule holds). Facts for
  11-16 and 11-17 written by the day's last step. 11-18 began 12:44:39; at 14:43 its second tier 2 pass was at 83
  of 128 groups, 49 GB free (the day's low), so it closes about 15:25; then 11-19 about 18:05, 11-20 about 20:50,
  11-21 about 23:30.
- **11-18 closed 15:37:05 on 11-22, gate PASS**, 10,346 s: 20 of 32 equal, clip 19,304,285, world 19,304,300,
  **+15** (every day before: +11), worst city 0.00177% (before: 0.00159%). Inside the bar (0.1%) by far, but the
  first change of the margin since 11-02: 11-18 is the day the 261118 notes dump was cut into the world, the
  likely reason; not traced. 11-19 began 15:37:22 (the first day gated against a filled-in clip); at 17:45 its
  second tier 2 pass was at 110 of 128, 45 GB free (the day's low). So at the owner's 18:00: **11-15 to 11-18
  closed, 11-19 closing about 18:10**; 11-20 about 20:55, 11-21 about 23:40. No new `watch:` line since f116.
  - **When the loop reaches 11-21 it has no clip for 11-22** (the city task, which fetches Europe's clip and the
    diffs, is paused), so it ends its run or stops for want of a clip: either is the sign to resume the cities.
    After the city run has fetched, `python ../osm-extracts/osm_extracts.py fill europe` makes the days the fetch
    skipped (it applies every missing diff at once), then start the loop again.
- **11-19 and 11-20, the two days gated against filled-in clips, both PASS.** 11-19 closed 18:34:36 (+13 of
  19,308,665, worst city 0.00177%, 10,634 s); 11-20 closed 22:07:04 (+16 of 19,316,066, 0.00177%, 12,732 s). So
  `fill`'s clips are good oracles. 11-21 began 22:07:18 and was in tier 2 at 23:40 (54 GB free); it closes about
  00:50 on 11-23. **Three `watch:` lines on 11-20, all the same thing: `store context before` 1,735 s (4.9 times
  its median of 353 s) and `after` 1,781 s (3.9 times 456 s), and so `world prepare` 2,210 s.** That is the Rust
  store's context query (ways of moved nodes, crossings, relations), flagged on 11-09 and 11-12 too and back to
  316 s on 11-21's prepare: it swings by day, cause unknown, about 45 minutes on a bad day. The next thing to
  look into, with the reads (about 1,750 s every day).
- **What happens when 11-21 closes (set up 23:45, detached: `.scratch/after-backfill.sh`, log
  `logs/after-backfill.log`).** The loop has no diff 5184 on disk, so it takes no further day and ends its run
  cleanly. The helper then: enables `kk-SCOpenQuests`, deletes `data/cities.paused`, runs the task, waits for it
  to end, `facts.py cities`, `osm_extracts.py fill europe` (the clip days the fetch skips), and starts the loop
  again (`--max-days 20`) unless RUNNING, STOPPED or HOLD is there. It does nothing if the loop stopped on a
  failure or 11-21 is not done. **To check in the morning:** that log; the city run's `update done` in
  `logs/scheduler.log` (it ran out of heap on 11-21 beside the catch-up; alone it should not); the loop's days
  11-22 on.
- **The anomalies looked into (2026-11-23, 00:05-00:20 by the clock; owner: "lets look into the metrics and performance
  anomalies we observed"). Read-only beside the live loop: nothing built, nothing changed, proposals wait for the
  owner.** Kept: `.scratch/anomalies/1121-f116/engine-{old,new}.log` (11-21's f116, before the work went) and
  `.scratch/anomalies/1121-points/{before-points,after}/` (11-21's `in-points.npy`, `p_*.npy`, `context.json`:
  generations 19 and 20, to replay `--points` against while the store still holds them).
  - **Store context is the `points` query, and it is two different things.** Every other part of a context call
    is steady (ways 20-85 s, crossings 26-39 s, nodes 5-30 s); `points` (the closed ways and multipolygons holding
    each changed tagged node) is 105-1,590 s. (1) **11-20 was input volume:** 337,479 points before and 346,278
    after against 11,000-44,000 on every other day, at an ordinary 4.7 ms a point: 1,575 s and 1,591 s. That day's
    change had 345,556 tagged nodes (usual 20,000-35,000): a mass edit, its changesets not traced. (2) **The other
    slow days are cost per point, 3 to 28 ms, at ordinary counts** (day D asks `before` at generation D-2 and
    `after` at D-1): generation 8, 31,352 points, 778 s, is 11-09's `after`, and generation 11, 33,994 points,
    911 s, is 11-12's: **the two earlier watch lines (933 s and 1,117 s) are this.** Also generations 12 and 13
    (11-14: 549 s and 716 s) and 15 (11-16: 592 s), days with no steps row. Against generation 1, 31,541 points,
    105 s. Not machine load: generation 15's same inputs took 592 s and 604 s seven hours apart (before and after
    the disk stop).
  - **Two candidate mechanisms, both read in `tilestore/src/context.rs` and neither measured (the stat counts
    no way or relation tested).** One thread. (a) Lines 652-680: for every point, every closed way of the nine
    tiles around it is placed again (a binary search per node ref, a new vector) before its box is even compared
    with the point: points times the closed ways around them, so changes in built-up tiles are slow. (b) Lines
    691-706: for every point inside a multipolygon's box, a node map and the segment list of the whole relation
    are made again: a large multipolygon has a large box, so points inside a forest or an administrative-size
    landuse are slow. Either fits "the cost per point follows where the edits sit". **Proposed, in this order:**
    counters and seconds for each (ways placed, rings tested, multipolygons tested, blob fetch) in the stat; one
    day of them; then the fix they name: each tile's closed ways placed once per chunk with their box, a
    relation's segments made once, the homes of a chunk in parallel. Same output files: the proof is `ctxcmp`
    and the `p_*.npy` of the old and the new binary on the same inputs (the kept 11-21 ones, or a day under
    HOLD). A guess, not a measurement: the step from 165-1,590 s to under a minute, twice a day. Needs a `cargo
    build`, so between two days.
  - **f116 is not skew: it is linear in its own size, 16-24 ms a rectangle from 11,000 to 32,000 rectangles**
    (11-17: 11,442, 189 s; 11-20: 19,511, 338 s; 11-16: 32,222, 708 s). f116 (north Norway, Svalbard) has 11-13
    parts a rectangle where other large groups have about 6 (f127: 31,405 rectangles, 181,896 parts, 230 s), so
    parts may be the unit, but that is not established: start-up is 0.5-0.9 ms a part in most large groups and
    2.6 in f21, the pass 0.5-1.1 ms a part in f116 and f127 and 1.7-7.4 in f53, f3 and f21. What holds: splitting
    a group by its number of rectangles would move the time, not remove it. **11-21's f116 log, 11,290 rectangles,
    208 s, says where it is not:** the main pass's four steps 10.6 s, the quests 1.3 s, the parts cache 0.2 s. It
    is in four places no line names: registry and cities 13.5 s, parts outside the cache's own timers 15.7 s, "the
    engine and its indexes" 56.8 s, and about 108 s of the pass between the `relations` step and the `pass` line
    (the area pass over 11,290 areas, `state.bin`, the dumps).
  - **Over all of tier 2** (`engines.json`, 11-15 to 11-20, each of the two phases): about 6,400 s summed, of which
    start-up 1,300-1,580 s and at least 2,300-2,800 s of pass time outside the main steps and the areas (a lower
    bound if the areas' seconds are summed over threads; the main steps are wall-clock in f116's log). Map data
    212-289 s, the quests about 1,100 s, the main steps about 1,080 s. So **more than half of tier 2's engine
    time is in no line of the log**, which corrects "the quests' runs and the main pass in equal
    parts" above. **Proposed:** first timers (cities loading, `loadParts` outside the cache, `Engine`'s indexes
    by index, the pass after `relations` by part), one day of them, then the fix the numbers name. Engine change:
    between two days, with the gate as proof.
  - **Seen in the table, not traced:** tier 2 reads went from 1,100-1,390 s (11-04 to 11-13) to 1,558-1,825 s
    from 11-15 on with fewer tiles read (`engines.json`: 11-14 1,391 s summed over 973,308 tiles, 11-15 1,616 s
    over 858,065). That rests on 11-14 alone, where only the D read was faster (613 s against 778 s for D-1), and
    whether the step's log lines mean the same since the swap was not checked: no cause named. `rectangles` and `engine files` climb through a run of
    days (118 to 366 s, 418 to 963 s over 11-04 to 11-13) and fall after a restart (139 s, 522 s on 11-15): not
    looked at. 11-14 and 11-16 have no `steps.json` row (the swap day and the day that ran twice). The gate's
    margin moving from +11 to +13/+15/+16 since 11-18 was not examined here.
  - **The watch rule misses both kinds:** it compares a step with its median, so a slow day at ordinary volume
    under twice the median passes, and f116 trips it only because the group is large. Rates would say it: ms a
    point for `points`, ms a part for an engine.
- **Counters and timers: owner "go, but be careful" (2026-11-23, 00:17). Under way at 00:23, nothing in main but
  this file.** Rules kept: no build and no install in main while `RUNNING` exists or the city task runs; measuring
  code only, the fix later and apart, so a gate has one suspect.
  - **Tile store, branch `points-counters`** (worktree `.claude/worktrees/points-counters`, edb0521e, built there):
    the `points` stat of `context.json` gains `secondsTiles`, `secondsBlobs`, `secondsWays`,
    `secondsMultipolygons` and the loops' counts (`closedWaysSeen`, `wayRefsSearched`, `closedWaysPlaced`,
    `ringsTested`, `ringSegments`, `multipolygonsSeen`, `multipolygonsInBox`, `multipolygonNodesMapped`,
    `multipolygonSegments`, `homeTiles`, `blobsAsked`). The clock is read per chunk and per point and tile, not
    per way. Nothing reads the stat strictly (`store_context.py` logs it whole).
  - **Its proof, done 00:42-00:49 (the store STOPPED and still, generations 19 and 20 both readable; no HOLD was
    ever placed):** the worktree binary on the kept 11-21 points inputs; `p_offs`, `p_kind`, `p_id` byte for
    byte the day's own, both calls; outputs `.scratch/anomalies/replay/`. **The split, an ordinary day:**
    generation 19, 12,284 points, 180 s: the closed ways' loop 91 s, the multipolygons' 58 s, blobs 21 s, tiles
    11 s. Generation 20, 25,358 points, 207 s: 131 s, 59 s, 8 s, 9 s. **Both candidates are real.** Closed ways:
    193 and 370 million placed (1.9 and 3.4 billion binary searches) for 35,704 and 65,973 rings whose box held
    the point: 5,400 placed for one tested. Multipolygons: 17,442 and 25,489 in a box, 327 and 431 million
    nodes put in a map for them (18,000 nodes each time). So the fix proposed above takes both loops.
  - **Engine timers: built by a subagent, branch `worktree-agent-a3eb722146f115366` (9dc17f7d), not reviewed by
    this session yet and NOT ready to install.** `timing:` lines only (startup, engine, area, area cities, area
    map data, over threads, before the pass, pass, outside total), `day_metrics` reads them into `"timing"`.
    Its proof: `.scratch/rectgroups/exact/groups/f10`, 428 rectangles, old against new, the outputs the same as
    two old runs are the same. Still owed: the diff read for anything held longer in memory; an old-against-new
    run of a gate region with `--notes` on a still machine, with the peak heap; `CountryMetadataTest` (fails in
    the worktree, on `AD.yml`'s sha) run on the base commit.
  - **THE LOOP STOPPED AT 00:40:41 ON 11-21's GATE, WHILE THIS WORK RAN BESIDE IT.** The clip-side engine for
    europe-central died of `OutOfMemoryError: Java heap space` in `AreaPass.wayColumnsOf` (`maxHeap=14336 MB`;
    its log kept: `.scratch/anomalies/1121-gate-oom/log.txt`). Not a count that differs and not the store:
    `finished` is there, europe-west had counted (71 s against the usual 54-58: the machine was loaded). What
    ran beside it: the subagent's gradle build, its engine runs on the fixture (00:32-00:34, 00:43) and its
    unit tests; this session's cargo build had ended at 00:21. Another process cannot fill a JVM's heap, so the
    load can only have moved the timing of 24 threads' allocations in a heap that was near its limit already;
    that is a guess. The city run died of the same error at `-Xmx13g` on 11-21 "beside the catch-up". **The
    gate engine's heap is in no metric: an anomaly of its own.** `after-backfill.sh` saw STOPPED and did nothing
    (00:40:54).
  - **The cause, found on the rerun: memory, not timing.** The gate's engine takes `-Xmx` from what the machine
    can spare when it starts (`run.engine_heap_gb`): 14 g at 00:39 beside the subagent's gradle, its engine
    runs and unit tests, **27 g on the still machine**, where europe-central then peaked at 27,189 MB (sum of
    pool peaks) and counted in 148 s. So this session's work took the memory the gate needed: the stop was
    caused here. The rule waits only for `HEAP_MIN_GB`, which is less than europe-central needs; the city run's
    `OutOfMemoryError` at `-Xmx13g` on 11-21 is the same thing. **Not built, worth having:** a minimum per
    region (wait, do not start with less), and the heap given and the peak kept as a metric.
  - **Restart 00:52:24 (pid 64404), STOPPED removed, nothing of this session running:** "day 2026-11-21:
    resuming (the store at generation 20, the world at 2026-11-21)", the gate only. **Gate 11-21: PASS**, 20 of
    32 equal, clip 19,321,402, world 19,321,415 (+13), worst city 0.00177%. `loc advance`, `loc check`, the
    cut, `subcmp` (13,968 same, 32 differ, 5 only planet), `why` (37 of 37 explained): all as every day.
  - **THEN STOPPED AGAIN AT 00:59:37: `compact` exit 101, "under the disk floor: nothing written".** The floor
    is 40 GiB free (`nodefile.rs`); the disk had 36.76. Nothing was written: the store is whole at generation
    20, the node file at 11-21, the world at 11-21 and gated; what is left of the day is the compaction (it
    copies 0.09 GiB and then frees about 14), the day's record, the delete of `world-days/2026-11-21` (about
    90 GB back) and the facts. `after-backfill.sh`, started again at 00:53, saw STOPPED and did nothing (00:59:52):
    **the cities are still paused and the task disabled.**
  - **This session's part of the disk: about 1 GB** (two worktrees' builds and the subagent's proof runs), now
    deleted; the proven binary kept as `.scratch/anomalies/tilestore-points-counters-edb0521e.exe`. Free after
    that: 39.4 GiB, still 0.6 under. The day's margin over the floor at this step was never recorded; the
    day's low was 45-54 GiB during tier 2 on the days before.
  - **Asked of the owner (01:05), nothing deleted that is not this session's:** what may go to get over the
    floor: `logs/opbench-full.log` and `opbench-rehearse.log` (4.6 GB, the Overpass benchmark's logs of 11-14),
    or `.scratch/planet-day/clip-1103`, `-1104`, `-1105` (7.3 GB, the store's first checks, written up in
    DESIGN.md), or one compaction under a lower floor (`TILESTORE_TEST_FLOOR_GIB`). **Then, to resume:** remove
    STOPPED, start the loop (`planet_store_day.py --max-days 20`, as `.scratch/after-backfill.sh` starts it): it
    takes the branch "the store's checks and compaction, resumed"; once RUNNING is there start
    `.scratch/after-backfill.sh` again (it resumes the cities, fills Europe's clips, starts the loop).
  - **Also found, for the engine's install:** `run.py`, `backfill_history.py` and `places.py` rebuild the engine
    themselves when a source file is newer than the installed jars (`engine_is_stale`). So engine source merged
    into main is installed by the next city run, whoever is ready: merge it only when it may be installed.
  - **Owner (01:10, asked as a wizard): the Overpass logs may go.** `logs/opbench-full.log` and
    `opbench-rehearse.log` deleted (4.6 GB; the results under `.scratch/overpass/` stay): 47.2 GiB free.
  - **11-21 CLOSED 01:20:06.** STOPPED removed, the loop started 01:16:00 (pid 23036): the store's checks again,
    `compact: exit 0 in 2 s`, the engines' metrics written, the day's work deleted, **124 GiB free**, "no diff
    to 2026-11-22 on disk yet; done for now". `after-backfill.sh` (started again 01:16) went on at 01:20:07:
    the city task enabled and running, then `facts.py cities`, `fill europe`, the loop.
    **Owed for 11-21, because it closed on a resume:** its world facts (the loop's next day writes every gated
    day without facts; else `python tools/facts.py world`, not beside a city run) and its `steps.json`.
  - **THE COUNTERS ARE INSTALLED (01:21).** `points-counters` merged into main (7ef35c56), worktree and branch
    gone. `tilestore/target/release/tilestore.exe` is the proven binary itself, copied, not rebuilt (sha256
    6249b9b1..., built in the worktree from edb0521e); the one before (165a0bd7..., of 11-17) is
    `.scratch/anomalies/tilestore-before-counters-1117.exe`: copy it back to undo. The loop copies the binary
    at its next start, so **the first day with the split in `context.json` and in the log's "store context at
    generation" lines is 11-22.** To read after a few days: `secondsWays` against `secondsMultipolygons` on a
    slow day; then the fix (both loops), apart, with its own proof.
  - **The engine timers: diff read by this session (additive: clock reads and `init` blocks between
    properties in their order; nothing reordered), NOT installed, branch `worktree-agent-a3eb722146f115366`
    kept.** Owed before install, on a still machine only (no RUNNING, no city task; the gate's engine takes
    27 g): old against new on one gate region with `--notes` (europe-east, about a minute), the outputs and
    the peak heap compared; `CountryMetadataTest` on the base commit. Install: merging engine source into main
    makes the next city run rebuild the engine (`engine_is_stale`), so merge and `installDist` together, under
    HOLD, the install folder copied aside first.
  - **The lesson of the night, for whoever works beside the loop:** an engine's heap is what the machine can
    spare when it starts, and compaction needs 40 GiB free. A build, a test run or a few GB beside the gate or
    a city run can stop the day. Work in the gap between runs, or under HOLD.
  - **The city run the helper started failed in 20 s (01:20:27): `osm_extracts.py fetch ontario`, HTTP 404.**
    Geofabrik's `ontario-latest.osm.pbf` redirects (307) to `ontario-261122.osm.pbf`, which was a 404 at 01:22
    (06:22 UTC): probably their daily publication under way, not checked further. So no Europe clip of 11-22
    and no diff 5184 were fetched; `facts.py cities` wrote 6 snapshots, `fill europe` had nothing to fill, and
    the loop the helper started ended at once ("no diff to 2026-11-22 on disk yet"). **State at 01:25: nothing
    running, no HOLD, no STOPPED; store and world at 11-21, generation 20; the city task enabled (next 12:15),
    `data/cities.paused` gone; 124 GiB free.**
  - **Scheduled for 07:30 on 11-23, into this session** (scheduled task "Engine timers proof, city run retry"):
    on the still machine, the engine timers' proof under HOLD and, if clean, their install; then, if
    Geofabrik answers, the city task, `facts.py cities`, `fill europe` and the loop (11-22 is the first day
    with the points counters). If that session does not come, the 12:15 city run and the 14:45 store task do
    the fetching and the day on their own; the timers then wait.
- **07:10 check on 11-23 (the storage session).** Read the night's entries above (the other session's): 11-21
  closed 01:20:06 with its gate passed after two stops that session caused and cleared; the helper resumed the
  cities, whose fetch met Geofabrik's 404; nothing is running, no HOLD or STOPPED, 126 GB free, the city task
  enabled, `data/cities.paused` gone. **The backfill is done: 11-01 to 11-21, every day gated.** This session
  started nothing: the 07:30 task of the other session has the city retry, `fill europe` and the loop, and wants
  a still machine for its engine proof. Done here, on the still machine, in under a minute: **11-21's owed facts**
  (`facts.py world`: 27,761,653 rows; all 21 gated days now have facts; `verify --sample 2`: 0 different) **and its
  `steps.json`**. That showed `day_metrics.day_steps` read only a resumed day's last fragment; fixed (a day is
  read from its last "diff N on generation G" line through every resume, with `resumes` counted) and 11-16 and
  11-21 rewritten: 11-16 36,054 s with 24,848 in no step (the disk stop), 11-21 11,568 s with 1,959 in no step.
- **The 07:30 follow-up on 11-23 (the anomalies session; the machine still, a HOLD of its own 07:31-07:37, removed).**
  - **THE ENGINE TIMERS ARE INSTALLED (07:35).** Proof first, as the gate runs a region (`storecheck_cities.engine`:
    `--notes`, `--dump-state`, `--today`), europe-east on `europe-2026-11-21.osm.pbf`, both at `-Xmx32g`, one
    after the other: old (main's install of 11-21) 45 s, new (the worktree's build) 39 s. `quests.json` and
    `state.bin.json` byte for byte; the snapshot the same but for `runSeconds`; `state.bin` the same 4,058,708
    records as a multiset (its order is the threads'). Peak heap (sum of pool peaks) 31,194 MB old, 27,205 MB
    new: not higher. Then merged into main (fb9c233d; one conflict, two tests added at the same place in
    `tests/test_day_metrics.py`, both kept; 259 Python tests pass), `installDist` in main, `engine_is_stale()`
    False, and the installed engine run once more on the region: the same outputs (the snapshot differs in
    `engineCommit` and `runSeconds` only). **To undo:** the install of 11-21 is
    `.scratch/anomalies/engine-install-before-timers-1121/`; copy it over
    `engine/build/install/sc-open-quests-engine/` and revert fb9c233d (else the next city run rebuilds from
    source). Proof kept: `.scratch/anomalies/timers-proof/europe-east/` and `timers_proof.py`. Worktree and
    branch gone.
  - **What the timers give:** `timing:` lines in every `engine.log` (startup, engine, area, area cities, area
    map data, over threads, before the pass, pass, outside total), and from the next closed day
    `engines.json` has them per engine under `"timing"`. **To read after 11-22 closes:** f116's
    `timing: engine` (which index holds the 39-57 s) and `timing: area cities` (which of ways chosen, tagged
    nodes chosen, relations chosen, map data assembled holds the 108 s), and their sums over all of tier 2.
    Not measured at scale yet: the subagent's guess is the per-city scan of every way, node and relation of
    the file, and the cities-times-parts loop in `Engine`.
  - **`CountryMetadataTest` fails on main as well, since the LF conversion of 11-17, not from the timers:**
    `SC-VERSION.txt` records `AD.yml`'s sha256 with CRLF (86c4bd7b...), the file in git and on disk is LF
    (f300507e...; the same bytes with CRLF give the recorded sum). So the bundled `country_metadata` files are no
    longer SC's bytes and the test that says so has been red since. Not touched: whether these files are
    exempted from LF or the sums recorded anew is the owner's.
  - **Geofabrik answers again** (`ontario-latest` to `ontario-261122.osm.pbf`, 200, last modified 00:06 UTC; the
    404 at 01:22 was their publication under way). `.scratch/after-backfill.sh` started 07:37 (detached): the
    city task is Running (downloading at 07:38; **the first run on the timers engine**), then `facts.py cities`,
    `fill europe`, the loop (`--max-days 20`): **11-22 is the first world day with the points counters and the
    timers.** To check: `logs/after-backfill.log`, `update done` in `logs/scheduler.log`, 11-22's gate.
  - **Still open from the night:** the fix of the points query (both loops; wait for a slow day's split); a
    minimum heap per region for the gate and the city run, and the heap as a metric; the loop refusing a day
    it has no disk for; tier 2 reads slower since the swap; the gate's margin since 11-18.
- **The noon check on 11-23 (owner: "whats next"): the 07:37 run died on Docker; started again 11:59.**
  - **What happened:** the city run of 07:37 fetched every region, then failed at `fetch europe` at 09:35:
    "docker is not answering" (Docker Desktop was not running; `com.docker.service` Stopped, start type Manual;
    why it was down is not known). So no 11-22 clip or diff for Europe, `facts.py cities` wrote 0, and the loop
    of 09:35 ended with "no diff to 2026-11-22 on disk yet": **the world is still at 11-21, generation 20.**
  - **Done:** Docker Desktop started (29.9.3, answered in 5 s; `name-ru-repair-osmium` runs, osmium 1.18.0), then
    `.scratch/after-backfill.sh` started again, detached, at 11:59 in a gap (no RUNNING, STOPPED or HOLD, task
    Ready, 127 GB free). At 12:01 the task was Running and Europe's fetch was past the failure (diffs 5184 and
    5185 downloaded, so the clip goes to 11-23's sequence and `fill` makes 11-22). Nothing built or tested.
  - **To check:** `update done` in `logs/scheduler.log`; `fill ended` and `loop started` in
    `logs/after-backfill.log`; then 11-22's gate in `logs/planet-store.log`, and after it the timers (above).
  - **The task's time is right, the status line was not:** the trigger is 17:15 UTC (fixed `-05:00`), so 12:15
    EST in winter and 13:15 in summer ("Daylight time" above); the planet store's 14:45 moves with it (13:45 EST).
    The line under "Status and next steps" now says so. Nothing changed in the Task Scheduler.
  - **`CountryMetadataTest`, the sums (cf18da81):** the LF files are SC's own bytes (`AD.yml` on disk and SC's
    raw file at the pinned commit both give f300507e...), so the sums were recorded anew, not the files exempted.
    `.scratch/rerecord_sc_sums.py` showed for each of the 613 files and 7 upstream sums that the old sum is the
    same bytes with CRLF, then wrote the LF sums; `sync-sc.ps1` now copies text with LF (`Copy-Lf`;
    `boundaries.ser` as it is), so a repin on a CRLF checkout records the same. **Not run: the engine's tests**
    (a gradle run beside the city run); the sums were checked by the script. **Left:** the test "byte for byte
    against the SC checkout" compares raw bytes and would fail against a CRLF checkout (today it is skipped:
    `Temp/sc-v64.1` has lost its `country_metadata`); the fix is to drop `\r` from the checkout's side, but a
    touched file under `engine/src` makes `engine_is_stale()` true, so it waits for a gap.
  - **Docker Desktop not starting by itself** is a way for every day to stop; the owner: leave it.
- **Owner, 12:05 on 11-23 (phone): "lets fix all these, except docker".** Read as: the two calls above (done)
  and the night's five open items. **Under way since 12:15, nothing in main, nothing built or run:**
  - Two agents writing in worktrees of their own (`.claude/worktrees/agent-*`, branches `worktree-agent-*`; two
    older worktrees there are other sessions'): (A) the points query fix in `tilestore/src/context.rs`, a
    draft that has never been compiled; (B+C) the heap given and its peak as a metric, a minimum heap per
    region, and the loop taking no day it has no disk for. Decided for B+C before the brief: a region without its
    minimum waits a bounded time (60 min, a line every few minutes), then the gate ends the run cleanly with
    no STOPPED (the next start resumes at the gate) and the city run fails naming memory; under about 115 GiB
    free the loop takes no new day and ends its run cleanly.
  - Two agents reading only: tier 2 reads since the swap (notes in `.scratch/anomalies/t2-reads/`) and the
    gate's margin since 11-18 (`.scratch/anomalies/gate-margin/`; it copies 11-22's gate outputs if the day's
    work would delete them). Each may end in a named cause and no fix.
  - **The gap's order (no RUNNING, city task not Running; no HOLD is placed to make one, world days come
    first):** free disk; gradle `CountryMetadataTest`; the whole Python suite; merge B+C after reading it;
    then A alone: `cargo build` in its worktree, old binary against new on a day's `--points` inputs (the kept
    11-21 ones in `.scratch/anomalies/1121-points/` only while generations 19 and 20 are readable), `p_*.npy`
    byte for byte, and installed on a day of its own so a gate has one suspect. The test's `\r` edit goes with
    the next engine install.
  - **(A) the points fix: drafted, NEVER COMPILED, not in main.** Branch `worktree-agent-a0045fbd7abb56a4c`
    (5dc1fbe6; worktree `.claude/worktrees/agent-a0045fbd7abb56a4c`), only `tilestore/src/context.rs`, on top of
    main 1541a916. Per chunk of 512 homes: each tile's closed ways placed once with their box (`tile_idx`,
    in parallel), the box tested before a way is placed again; each multipolygon's box once per chunk (the
    old code rescanned the blob's places for every point and multipolygon seen: a third cost); a relation's
    node map and segments once, for all its points; homes and relations in parallel (rayon, already there),
    all writes afterwards on one thread in the old order. **It now uses every core where it used one.**
    Tests in the file (the old loop kept as an oracle), unrun. **Proof owed in the gap:** `cargo test` and
    `cargo build` in the worktree; the old binary is `.scratch/anomalies/tilestore-points-counters-edb0521e.exe`;
    `replay.py`'s `EXE` points at a removed worktree: point it at the new build and compare against
    `.scratch/anomalies/replay/{before-points,after}/` (`p_*`, `e_*`), every file but `context.json`; the
    counters `ringsTested`, `ringSegments`, `multipolygonsSeen`, `multipolygonsInBox`, `homeTiles`,
    `blobsAsked`, `tilesRead` must equal the old ones (the others change meaning: per tile and per relation
    a chunk, not per point). That replay is points only: also one full `after` call (`ctxcmp.py`, or a day's
    kept `context/after/in-*.npy`) old against new, every output. Generations 19 and 20 must still be
    readable, else a day under HOLD. Memory: per chunk, about 55 MB at ordinary density, 1.8 GB if every
    tile is dense.
  - **(B+C) heap and disk: written, NO TEST RUN, not in main.** Branch `worktree-agent-aaad0db7d023acc9a`
    (bd22fd81, d5cb7a80; worktree of the same name): `run.py`, `config/regions.json`,
    `tools/stream/{planet_store_day,world_gate,storecheck_cities}.py`, `tests/test_heap.py`, new
    `tests/test_loop_safety.py`, DESIGN.md, DATA-FORMAT.md. (1) The gate logs `gate heap: <region> given N MB,
    peak M MB` and writes `"clip heap"` into `gate.json`; the city run's heap line names the region (its peak
    is in `scheduler.log` only, in no record). (2) `"minHeapGb": 27` on europe-central alone;
    `engine_heap_gb` waits for it up to `HEAP_WAIT_MINUTES` (60), a line every 5 min, then raises
    `MemoryBusy`: the city run exits 1 naming the numbers; the loop logs "not now", writes no STOPPED and ends
    its run, the next start resuming at the gate (`one_day`'s `loc_at == prev and w_at in (prev, day)`
    branch). (3) `DAY_NEEDS_GB = 75` + `DISK_FLOOR_GB = 40`: under 115 GiB free a new day is not taken, one
    line, no STOPPED. **To settle before the merge, read by this session in the gap:** 27 is the edge, not a
    measured need (the peak follows the heap given: 27,189 of 27,648 MB, 28,251 of 28,672; it died at 14 g; a
    still machine gives 37-40 g); 115 GiB is close to what the disk has at a day's end (124-127), so the loop
    could stand still with one quiet line a run and nothing frees space by itself; with neither RUNNING nor
    STOPPED after a clean end at the gate, `store_lock.reading` lets readers take a store that is at D before
    its checks and compaction (that state used to come only with STOPPED); the old `HEAP_MIN_GB` timeout at
    the gate now ends cleanly too; a day resumed so gets no `steps.json`.
  - **Tier 2 reads: looked into (the read-only agent, done 12:35), no cause established, nothing wrong with
    the reader; and a leak found beside it.** Notes: `.scratch/anomalies/t2-reads/NOTES.txt`. The step is
    measured as before the swap (the same span in `world_day.rect_rows`, 4 workers, no commit in `tilestore/`).
    Like for like, seconds a GB of map data: 53-73 on 11-04 to 11-13, 80-93 on 11-15 to 11-19, 77-80 on 11-20
    and 11-21; 11-14's D-1 phase, on the old code, already 84. A phase's first reads cost what they did; the
    excess grows along the phase (1.07 to 1.65 times), and the stage with no I/O (merge) rose most: so not
    the binary, the index, the generations or the disk. **Leading guess: the reads share the machine with
    busier engines** (the old engine's long runs held slots and used about one thread; the new ones are
    short and many). `tier 2 engine` is wall minus reads, so judge tier 2 by the sum of the two. To settle: a
    row per read in `engines.json`, and one day's last 32 groups replayed idle under HOLD. **A saving that
    holds either way, not built:** each of 254 reads a day loads the whole index (`idx` 772 MB, `relidx`
    305 MB), bounded at 250-350 s a day; a mapped index or one reader process would remove it.
  - **The `rectangles` climb is a leak, fixed on a branch, not in main: `syspath-leak` (efaab49d, worktree
    `.claude/worktrees/syspath-leak`).** `world_day.quiet()` put `tools/` on `sys.path` again at every call,
    about 512 times a day; the pool's 22 spawned workers get the list whole and every import scans every
    copy: the pool part of `rectangles()` went 50 to 302 s over the eleven days of one process and fell at
    each restart (measured apart: an interpreter's imports 0.22 s with no copy, 5.7 s with 2,560). The fix
    inserts once. `world_day.py` is imported by the loop: merge in the gap only. `engine files` is volume and
    machine state, no leak.
  - **The gate's margin since 11-18: traced (the read-only agent, done about 12:25), nothing to fix in the data;
    not the notes dump.** Notes and scripts: `.scratch/anomalies/gate-margin/notes.md`. Every new row is an
    aged-only one. (1) **Bratislava AddCycleway +4 to +6, for good:** ways 4911921 and 184347348
    (`cycleway:both=no`, last edited 2022-11-18) reached the 4-year resurvey age on 11-18; they lie where SC's
    boundaries say Austria, so the world counts them and the clip's `["SK"]` city counts no AddCycleway: the
    known country-gate difference of DESIGN.md, growing as more of them age. (2) **Sofia, +1 to +4 for one day
    each:** the world's cell (`f2c7`) runs in Europe/Belgrade, the clip's Sofia in Europe/Helsinki, so an
    element last edited in the hour before Belgrade's midnight ages in a day sooner in the world; 6 of the 7
    rows shown by their edit times (11-18's CheckExistence +1 not found). DESIGN (about line 1906) foresaw it.
    (3) Istanbul AddHousenumber +2 to +1 from 11-20, not traced. **Corrections to the above:** the margin was
    not +11 since 11-02 but +9 (11-02 to 11-04), +10 (to 11-10), +14 (11-11, Sofia again, not traced), +11
    (11-12 to 11-17); the dump cut in on 11-18 was `planet-notes-261121`; the worst city moved from Athens to
    Bratislava. **Would make it +0, not built, the owner's:** Sofia's ground in a UTC+2 cell (DESIGN's "cut a
    cell along zone lines") and the clip's city gated by position. **The one proof left:** keep the clip
    side's `state.bin` of europe-east for a day (`world_gate.py` line 84 deletes it) and diff Sofia's rows.
    Per element nothing of the clip side is kept; 11-22 had not begun, so nothing was copied (its
    `gate.json` is kept in `days/<D>/` anyway).
- **13:00 on 11-23, the anomalies session's reading (nothing run).** The 07:37 city run died at 09:35 on `fetch
  europe` ("docker is not answering"); the helper was started again at 11:59 (not by this session), the city run
  ended with `update done` at 12:32 (the first on the timers engine: `timing:` lines are in `logs/scheduler.log`),
  `fill` wrote `europe-2026-11-22.osm.pbf`, and the loop began 11-22 at 12:44 (pid 15328); it closes about 15:20.
  **The first split from production, 11-22's `before` at generation 20:** 11,643 points, 127 s: the closed ways'
  loop 67 s (181 million placed, 1.7 billion binary searches, 35,652 rings tested), the multipolygons' 30 s
  (14,138 in a box, 162 million nodes mapped), blobs 20 s, tiles 11 s: the same picture as 11-21's replay. This
  session reads 11-22's `after` and the engines' `timing` once the day has closed (scheduled 15:30); the fixes
  themselves are with the session of the owner's "fix all these" (12:16).
- **HOLD placed 14:57 on 11-23 (owner: "can we pause work at around 5 pm? i need my laptop offline").** The loop (pid
  15328) ends its run when 11-22 closes and takes no 11-23. `.scratch/after-backfill.sh` starts nothing while HOLD
  is there. Not to be removed before the owner says the laptop is back; then remove it and start the loop
  (`python tools\stream\planet_store_day.py --max-days 20`, detached). The laptop being off also drops the 21:30 gap
  check, the 23:20 city check and any scheduled task due then; they are due again when it is back.
  - **The "fix all these" session, 14:58:** a check at 16:00 into that session: if 11-22 has closed, the quiet
    stretch under this HOLD is used for light gap work only (11-22's gate, timers and points split read; free
    disk; gradle `CountryMetadataTest`; the Python suite; if green, `syspath-leak` merged), idle by 16:50, HOLD
    left alone. The heap and disk branch and the points fix wait for the laptop's return and the owner's word.
- **STOPPED at 15:20:23 on 11-23, day 11-22 in `world finish` (tier 2 `old`, engine f8 exit 1); HOLD is also there.** All
  four engines of that moment (pids 11428, 26484, 55252, 57228: `hs_err_pid*.log` in the repo root) died at
  14:57:11: the machine's commit limit was used up (limit 112 GB, RAM and page file; 6-7 MB left in three reports, with 13 GB of physical
  memory free). What held the commit is not known: nothing was recorded at that moment. Not a count mismatch. Free
  disk fell from 108 GiB (14:42) to 52 GiB (15:20); not traced. The store is at generation 21 and the world at
  11-21; `day.pkl` is kept and `finished` is absent, so the documented resume redoes finish (about 2.5 h). **Not
  restarted: the laptop goes offline about 17:00.** When it is back: remove STOPPED and HOLD, look at the commit
  (`Win32_OperatingSystem`, big processes) and the disk first, then start the loop. Both sessions were told.
  - **The commit at rest, read 15:26 by the "fix all these" session (no engine alive): 71 GB of 108.6 committed,
    37 GB left.** By process 54.5 GB: 53 `claude` processes 16.4 GB, `svchost` 4.6, WindowsTerminal 4.4, vmmem
    4.0 and vmmemWSL 1.9 as Windows shows them, Chrome 2.7, qBittorrent 2.6; about 17 GB is in no process
    (kernel pools 9 GB; the rest probably the Docker and WSL machines, whose limit is 43 GiB: a guess). The
    engines that died were tier 2's four at a fixed `-Xmx8g` (`hs_err`: "G1 virtual space", 67 s in): 32 GB of
    heap and the JVMs' own memory do not fit in 37 GB. **So the rest is the cause as far as one reading goes:
    tier 2 starts four 8 g engines without asking what the machine can commit; the gate's engine asks.** What
    this session added today: Docker Desktop (11:57, the city run needs it) and four agents, ended by 12:36.
    **For the heap and disk branch before it is merged: tier 2's engines under the same rule (wait, or fewer
    workers), and the commit left as a metric.** Before the resume: close what can be closed (old Claude
    sessions first) and read the commit again.
  - **Run in that stretch (15:26-15:28, the machine still), nothing else:** the Python suite, 210 tests, OK
    (`python -m unittest -q`); gradle `CountryMetadataTest`, 5 passed, the checkout one skipped: **the sums'
    test is green again.** `engine_is_stale()` still False. `syspath-leak` NOT merged: 11-22 is half done, and
    code changes between two days. The 16:00 check deleted. **The gap check is now 06:30 on 11-24** (moved 20:58 on 11-23: the loop was restarted 20:57 with two tier 2 workers and resumes 11-22; it does nothing heavy beside a running loop or city task).
- **15:30 on 11-23, the anomalies session's last reading (logs only; nothing run, nothing restarted; 11-22 is
  STOPPED and under the owner's HOLD, see the entries of 15:26).** What the new measures say, from the day's
  work folder as it stands:
  - **Points, 11-22's `after` at generation 21:** 23,553 points, 152.5 s: the closed ways' loop 91 s (299 million
    placed, 2.7 billion binary searches, 57,940 rings tested), the multipolygons' 32 s (22,189 in a box, 210
    million nodes mapped), blobs 20 s, tiles 9 s. With the `before` (67, 30, 20, 11 of 127 s) and 11-21's
    replay: on ordinary days the closed ways are 55-63% and the multipolygons 21-32%; a slow day's split is
    still to be seen. The drafted fix covers both loops.
  - **The engines' `timing:` lines, the 122 tier 2 engines of the D-1 pass that ended before the stop** (5,227 s
    summed, 227,500 rectangles, 1,957,716 parts; the D pass has none). **The time no line named is now named,
    and it is no single thing:**
    - the pass 3,912 s: the area pass 2,865, of it the quests' runs 965 wall (1,949 over threads), **map data
      assembled 585, ways chosen 274, dates 263, city sets holding the city 230, tagged nodes chosen 217**,
      results counted 80, relations chosen 77; the main steps 957.
    - start-up 826 s: **boundary read 259, parts file read 179, parts file look-up 92** (one small file read
      per rectangle: 530 s of file reads), boundary polygon 90, registry 63 (128 JVMs), part outlines 59.
    - the engine's indexes 409 s: **parts of each city 316** (a loop of cities times parts), gates 56.
    - outside `total` 392 s more: snapshot made 216, quests.json 82, JVM start 42, git head 27.
  - **f116 (13,178 rectangles, 160,427 parts, 238 s): parts of each city 100 s, city sets holding the city
    38 s**, the start-up's file reads 33 s, the quests' runs 14 s, map data 10 s, relations chosen 9 s, ways
    chosen 8 s. So f116's slowness is the two loops that grow with rectangles times parts (or times city
    sets); on 11-16, with 32,222 rectangles, they will have been most of the 708 s.
  - **What each names, largest first, none built:** (1) the per-rectangle choosing (`ways chosen`, `tagged nodes
    chosen`, `relations chosen`, `city sets holding the city`: about 800 s of 5,227, each rectangle scanning
    what the file holds): an index from city set to its elements, made once. (2) the start-up's file reads
    (530 s): the rectangles' boundaries and parts lists in one file per group, or in the parts cache. (3) `parts
    of each city` (316 s, 100 of them f116's): group the parts by city in one pass. (4) `snapshot made` (216 s)
    and `dates` (263 s): look before touching. The quests' runs and the map data are the work itself. On 4
    workers the summed seconds are about a quarter of that in wall time.
  - This session ends here: nothing of its own is running or scheduled, no HOLD of its own. The fixes, the
    restart of 11-22 and the laptop's return are with the other sessions' entries.
- **Resumed 20:57 on 11-23 (owner, about 20:45: "we're back to power and good internet, let's catch up on what we
  missed").** STOPPED (copy: `.scratch/anomalies/STOPPED-2026-11-23.txt`) and HOLD removed; loop pid 62660,
  `WORLD_T2_WORKERS=2` in its environment instead of 4, as 36 GB of commit was free (31 GB at 20:57 with the loop up)
  and four engines of 8 GB had died on the limit. 11-22 resumes at `finish`. Disk 53 GiB free at the start. To watch:
  free commit and free disk; if it stops again, the next try is 1 engine or closing sessions first.
- **No popups (owner, 20:15-20:50).** `taskrun.exe` (task-beholder baea6f0) is windowless for all its tasks. The
  city, planetstore and sidebyside tasks now run as `conhost.exe --headless cmd.exe ...` with the same arguments
  (backups in `~/Code/.task-backups`), like spend and worldpub: **Task Scheduler's result for these five is always 0**
  (conhost swallows the exit code), so read `logs/scheduler.log`, not the result. A runbook that rewrites the
  planetstore task's command must keep the `conhost.exe --headless` front. `kk-SCOpenQuests-planet` (disabled) is
  untouched.
- **STOPPED again at 22:55 on 11-23, 11-22 in `world finish` after both tier 2 passes; cause found and fixed; resumed
  03:50 on 11-24 (owner: "go").** `notes_day.notes_table` opened the stale `notes-prev.jsonl.table.npz` with `np.load`
  and never closed it, so Windows refused the replace (WinError 5). Not a lock from outside, not a count mismatch:
  any day after a notes refresh that finds an older cache there would stop the same way. Fixed in 14ddab6d (with a
  test that fails without it; the 20 notes tests pass), and both caches were built by themselves before the start. Copy
  of the stop: `.scratch/anomalies/STOPPED-2026-11-23b.txt`. Two engines again (`WORLD_T2_WORKERS=2`); 47 GB of commit
  free before the start. `finish` from the start again (about 2 h), then the gate, then 11-23. The gap check at 06:30
  will meet a running loop.
- **The 06:30 check on 11-24 (the "fix all these" session): the loop is running, nothing heavy done.**
  - **11-22 CLOSED 06:10:58, gate PASS** (20 of 32 equal, clip 19,324,940, world 19,324,952, +12, worst city
    0.00177%), on its third run. **11-23 began 06:10:58** (prepare 688 s, store context before 291 s); it has no
    11-24 diff after it, so the run ends with it, about 10:00 by 11-22's pace. The city task is Ready (next
    12:15). At 06:30: 37 GB of commit left with the loop up, 119 GiB of disk free.
  - **Read, not run: the heap and disk branch (`worktree-agent-aaad0db7d023acc9a`).** It merges into main
    without conflict, as do `syspath-leak` and the points fix. Its three open points, settled so: (1) the clean
    end at the gate stays: the store is whole at D and nothing is compacted, a reader's HOLD only delays the
    resume, and the next start heals it with no person, which a STOP would not; (2) 27 for europe-central stays,
    known to be an edge and not a need; (3) 115 GiB stays: days that began with 124-142 free had 45-54 at
    their low, so a day begun under about 120 would meet the 40 GiB floor in its middle; the refusal is right
    and the disk is the owner's (119 free this morning: one bad day from standing still).
  - **Added to that branch (6b39db7b), not run: `tools/stream/engine_room.py`, the commit rule for the world
    day's own engines** (tier 1, tier 2, the notes: `world_day.engine_dump` and `counts_at`). One enters when
    the commit left, less 8 GB, holds its heap and every engine of ours alive, counted whole; with engines
    alive it waits for one to leave; with none alive a line every 5 min and after 60 min a STOP. On 11-23's
    numbers (37 GB left) that is three engines at a time where four died. `WORLD_T2_WORKERS` stays the upper
    bound. Tests: `tests/test_engine_room.py`. Not yet a metric: `ROOM.most` and `ROOM.waited_s` are kept
    but written nowhere.
  - **Next check 10:00 on 11-24**, for the gap between 11-23's end and the 12:15 city run: commit and disk;
    the Python suite on each branch; merge `syspath-leak`, then the heap and disk branch; the points fix's
    `cargo test`, build and proof only if an hour is left before 12:00, else the next gap.
- **The 10:00 gap on 11-24 (the "fix all these" session). 11-23 CLOSED 09:10:00, gate PASS** (20 of 32 equal, clip
  19,329,755, world 19,329,767, +12, worst city 0.00177%), 10,742 s on two tier 2 workers (tier 2 engine 3,758,
  reads 1,110); the run ended 09:10:28, "no diff to 2026-11-24 on disk yet". No RUNNING, STOPPED or HOLD, the
  city task Ready; 47 GB of commit left, 124 GiB of disk free.
  - **MERGED INTO MAIN, the Python suite green before and after each (211, then 254 tests):** `syspath-leak`
    (5ccdac8a) and the heap and disk branch with the engine room (9d149279). One test of the engine room had
    its own arithmetic wrong (24 GB holds two engines, not one) and was corrected; nothing else failed on the
    first run of the agent's tests. `engine_is_stale()` False: no engine source touched. Read on the real
    machine after the merge: room for an 8 g engine (47 GB left), the gate's europe-central would get
    `-Xmx39g` against its 27, the disk check passes with 123 GiB against 115 (8 over).
  - **So from the next run on:** the city run (12:15) names the region in its heap line and refuses
    europe-central under 27 g after an hour's wait; the loop takes no new day under 115 GiB free, its gate
    logs `gate heap:` lines and ends the run cleanly when short of memory, and the world day's engines pass
    through `engine_room.ROOM`. **`WORLD_T2_WORKERS` is 4 again unless the starter sets it** (the 20:57 and
    03:50 starts set 2 by hand): with the room that is the upper bound, not a risk. **To watch on 11-24's
    day:** `engine room:` lines in `logs/planet-store.log` (none means it never had to wait), the `gate heap:`
    lines, `"clip heap"` in `gate.json`, and `rectangles` back near 120-140 s for the whole run.
  - **To undo:** `git revert -m 1 9d149279` (heap, disk, engine room) and `git revert -m 1 5ccdac8a` (the
    leak); neither touches data or the engine's install.
  - **11-26: the source is merged into main (2596a3ae, owner's wizard: "merge source only"); still NOT INSTALLED.** Main's
    `context.rs` is now ahead of the installed `tilestore.exe`: the next `cargo build --release` in main installs it, so
    don't run one before the owed items below. Branch and worktree removed; the proven exe is in `.scratch/anomalies/`.
  - **THE POINTS FIX IS BUILT AND PROVEN, NOT MERGED, NOT INSTALLED (10:03-10:19).** In its worktree (5dc1fbe6):
    `cargo build --release` clean at the first try, `cargo test` 7 passed (the old loop as oracle among them).
    Then `.scratch/anomalies/points_fix_proof.py 22`, as a reader of the store (its HOLD placed and removed), the
    old binary (`tilestore-points-counters-edb0521e.exe`, the installed one, sha 6249b9b1...) against the new
    on generation 22 with 11-21's two kept point lists: (A) `--points` alone; (B) with half of the ways and
    relations A found asked first by `--ways` and `--rels`, so `elements` holds them before the points
    section. **All four pairs: every output file the same bytes (8 files in A, 30 in B), the counters that
    kept their meaning equal. 12,284 points: 177 s to 11 s. 25,358 points: 241 s to 13 s.** Inside: the closed
    ways 95-158 s to about 1 s (placed 194-371 million to 29-34 million), the multipolygons 51-70 s to 1.1-1.4 s
    (nodes mapped 327-431 million to 16-19 million); what is left is tiles 4-5 s and blobs 3-4 s. Outputs:
    `.scratch/anomalies/points-fix-proof/`; the proven binary kept as
    `.scratch/anomalies/tilestore-points-fix-5dc1fbe6.exe` (sha256 a3c49f7e...).
  - **Owed before its install:** (1) a call with `--nodes` and `--node-places` beside `--points` (no day's
    `in-nodes.npy` is kept: the work goes when a day closes; copy `context/before` and `context/after` inputs
    from the next day while it runs, or replay under HOLD); (2) its peak memory against the old one's (not
    measured; it runs on every core now); (3) **a day of its own:** 11-24's world day is the first on the
    leak fix, the heap and disk rules and the engine room, so the binary goes in for the day after, not
    this one. Install: merge the branch (only `tilestore/src/context.rs`), copy the proven exe over
    `tilestore/target/release/tilestore.exe` (the loop copies it at its start); undo by copying
    `tilestore-points-counters-edb0521e.exe` back.
- **Clock times in this section from "19:10" on were written without reading the clock and run up to 45 minutes
  ahead**: it was 19:25 when the entry above ("20:05", "20:10") was written, and the HOLD ("19:30") was placed a
  little after 19:00. The order of events is right; the files' own times are the record.
- **THE SWAP IS TONIGHT (owner, relayed 19:25 by the catch-up status session: "place HOLD now so the loop stops
  after day 11-14, then do the swap tonight"; goal: as many world days as possible published by 18:00 on
  11-22).** `.scratch/planet-cut/HOLD` placed 19:30; the loop (pid 60100, `--max-days 20`) ends its run when 11-14
  closes (guessed about 21:00). `world-swap` now holds everything: main and `t2-relcache` merged into it, plus
  `tools/state_checkpoint.py` (5055f641; 19 tests pass). **Runbook, in this order, once RUNNING is gone and
  there is no STOPPED:**
  1. Check the day: `W/days/2026-11-14/gate.json` ok, the log's `== day 2026-11-14 done`. `baseline.sh` puts 11-14's
     `engines.json` (the old engine's numbers) beside it.
  2. On main: `git merge world-swap`; `cd engine; ./gradlew.bat installDist` (JAVA_HOME = Android Studio's jbr);
     the tests of the files touched.
  3. `python tools/state_checkpoint.py link` (seconds: hard links of the 128 `world.bin`).
  4. `python tools/facts.py world` (11-14's facts; later days write their own).
  5. Task `kk-SCOpenQuests-planetstore`: its command without `>> ...planet-store.out 2>&1`, its limit PT12H.
  6. The city task (`schtasks /Run /TN kk-SCOpenQuests`) only if it would not hold the restart back by more than
     about an hour (the loop waits up to 3 h on a daily run that is going; the peer's suggestion, not the owner's
     words).
  7. Remove HOLD; start the loop detached: `python tools\stream\planet_store_day.py --max-days 20` from the repo
     root, no redirect (it writes `logs/planet-store-<started>-<pid>.out` itself; `WORLD_T2_WORKERS` is set by the
     script).
  8. Beside the running loop: `python tools/state_checkpoint.py upload` (48 GB or so; hours), then
     `python tools/archive_backup.py --only facts`.
  9. After the first day with the cache: `python tools/stream/day_metrics.py report`, 11-15 against 11-14; the
     gate must pass as before. If a gate fails, `-Dopenquests.relationCache=false` is the way back without a build
     (`world_day.py`, the tier 2 `opts`).
- **(b) built, not merged: branch `world-swap`, worktree `.claude/worktrees/world-swap`, 6a153857.**
  `planet_store_day.py`: `write_facts()` after `store_tail` (a process of its own, never a STOP);
  `own_output()` sends a run's prints to `logs/planet-store-<started>-<pid>.out` unless `--console`.
  `world_day.py` `rect_rows`: a log line per tier 2 group with its engine seconds. `archive_backup.py`: `data/facts`
  is a source (`facts/` in the bucket). **Merge only between two days** (HOLD, wait for the day to end, merge,
  remove HOLD, start): `world_day.py` is imported by the running loop. At the same pause, the task
  `kk-SCOpenQuests-planetstore`: drop `>> ...planet-store.out 2>&1` from its command and raise its limit from
  PT6H to PT12H; and the first state checkpoint.
