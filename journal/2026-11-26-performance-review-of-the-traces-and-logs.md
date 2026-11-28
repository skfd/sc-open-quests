## Performance review of the traces and logs (2026-11-26, 06:15-07:30; owner: "lets review the traces and logs for performance improvements")

Read-only, under the HOLD: nothing edited but this file, nothing built, run or installed; proposals wait for the owner.
Read: 11-22 to 11-25's `engines.json` and `steps.json`, 11-25's day in `logs/planet-store.log` (cut out as
`.scratch/perf-review/day-1125.log`), `logs/site.log`, the tail of `logs/scheduler.log`, the four `hs_err` files. Three
read-only agents read the code (the world day's Python steps, the engine's loops, the publish and city run). Scripts:
`.scratch/perf-review/{crunch,room}.py`. **Every saving below is a guess unless it says measured.** 11-25 is the day
measured: 12,643 s, then the publish 1,155 s.

- **(1) The engines wait for memory: the largest cost, about 45-50 min of the day (measured waits, guessed saving).** On
  11-25 the engine room made tier 1's engines wait 1,849 s summed and tier 2's 6,190 s and 6,193 s (old, new). Tier 1
  ran strictly one at a time (all 127 starts say "1 alive", which counts the one starting); tier 2 ran alone at 137 of
  254 starts and two at a time at the rest. Tier 2's two phases took 5,384 s of wall for 6,696 s of engine and 1,074 s
  of reads: about 1.5 at a time, where 11-15 to 11-20 on 4 workers ran about 3.5. At 2.8 at a time (levers (a) and (b)
  below) tier 2 is about 2,800 s (2,600 s saved) and tier 1's engines about 350 s less; 3.5 needs more commit, (c).
  - **Why:** `engine_room.fits` asks `left - 8 >= heap + sum(alive)` with every engine at 8 g. The commit left was 16-26
  GB (median 24), so 24 - 8 = 16 holds one alive and one new at best, and the alive one's commit is already out of
  `left`: counted twice, as the docstring says. The engines get `-Xmx8g` and no `-Xms` (`stream.py:288`), so they commit
  as they grow: the `hs_err` files of 11-23 show 5.0 and 6.7 GB of commit at 67 s. Peaks on 11-25, tier 2: median 2.8 GB,
  p90 5.0, 4-5 of 128 over 6 GB; tier 1 median 2.4, notes 0.9.
  - **Levers, not exclusive:** (a) count an alive engine by what it can still take (its `-Xmx` less its own commit, read by
  pid) instead of whole; (b) a heap per group from its last days' peak, 8 g again on `Java heap space`: at 1.5 times the
  three-day peak tier 2's mean is 5.7 g (78 of 256 stay at 8, 7 would have passed 90% of theirs on 11-25; a group's peak
  moves 0.56 to 1.57 times day to day, p5 to p95, at most 2.41, hence the retry; the gate's peak follows the heap
  given, so the need may be lower than the peak: not measured for tier 2); tier 1's mean 4.3 g, the notes' 2.4; (c) more commit: the limit is 108.6 GB (87.6 RAM, a 21.5 GB system-managed page file on C:),
  77 GB taken at rest (49 `claude` processes 14 GB, WindowsTerminal 4.6, vmmem 5.9), 42 GB of RAM free: a larger page file
  raises the limit with no RAM, but C: is the only disk (G: is Google Drive) and must keep 115 GiB free for a day to be
  taken, so each GB of page file is a GB off that; closing sessions and Docker is the other way (11-24, 23:06: 26 to 35
  GB). The budget on 11-25 was 16-17 GB (23-25 left with none alive, less 8): (a) and (b) together hold about 2.8 tier 2
  engines in it. **On a day like 11-24 (9 GB left, the loop's own python at 17 GB in tier 2 `new`; "Day 11-24
  starved") (a) and (b) do nothing: only (c) helps.** `ROOM.most` and `ROOM.waited_s` are still written nowhere.
- **(2) The points fix, ready, the owner's go: about 410 s a day (measured).** 11-25's two `points` calls took 210 s and
  228 s of store context's 363 s and 459 s; the proven binary does such lists in 11-13 s. Its three owed items stand
  (the entry "THE POINTS FIX IS BUILT AND PROVEN").
- **(3) The world day's Python steps are serial file work (the agent's reading of the code; splits not logged).** The
  world's 52.6 GiB of rows is read whole five times a day and written twice, one file after another.
  - tier 1 (1,198 s) is 50 s of PBF, 628 s of engines and 520 s of serial `replace_in_file`; its engines need nothing
    of cover, rectangles or engine files (1,600 s of main thread before them) and could run beside those: about 600 s.
    The rewrite through a pool: about 350 s.
  - `engine files` 624 s: about 558,000 small files written on one thread (`world_tier2.py:885-926`); a pool: about 400 s.
    `place-bboxes.npz` is deleted with the day's work, so `places.json` (395 MB) is parsed daily: 30 s.
  - `tier 2 delta` 819 s (`world_day.py:481-522`): each `world.bin` read twice and rewritten, serial; a pool: about 400 s.
  - `counts and note quests` 737 s: the note engines beside the delta or `count_files`, `by_set` in a pool: about 350 s.
  - `old ways` and `member ways` (158 + 142 s): `tilestore ways` asks what the store context already holds; assert the
    two equal for a day, then drop the calls: about 300 s. Medium risk until the assert has passed.
  - the day's end: `rmtree` of the work, 170 s in no step (beside the store's checks); `touched.npy` 157 s untimed at the
    end of finish; `cut`, `subcmp`, `why` beside `loc check`: 107 s.
  - `places and old rows` 160 s: the threaded `world_tier2.old_rows` in place of `rows_of_keys`: about 100 s.
  - the notes dump is decompressed twice a day (337 s before the day, 99 s at the gate, which finds its clips unlinked):
    about 95 s; `world_notes` parses 2.4 GB of JSON for `id`: 40 s; both notes tables rebuilt daily: 35 s.
  - `read diff` 162 s and `cover` 254 s are the work itself. The rows overlap: together perhaps 2,000-2,500 s, not the sum.
- **(4) The engine's loops (11-25, one tier 2 phase: 3,349 s summed; the agent read `engine/src/main`).** The ranking of
  11-23 holds on 11-22 to 11-25. About 1,100 s of the 3,349 can go with the same output; in wall time that is divided by
  the engines at a time.
  - per-rectangle choosing 587 s (`AreaPass.kt:751-768`, `Cities.kt:285`): an index city to elements, made once: about 540.
  - `dates` 179 s (`AreaPass.kt:655-688`) repeats the same scans: 90-140.
  - start-up file reads 309 s (`Polygon.kt:59`, `Cities.kt:70,73`): one file per group; needs the Python writer too: 250.
  - `parts of each city` 106 s (`Engine.kt:147`, cities times parts): one pass, 5-8 lines: 105.
  - `boundary polygon` 50 s (`Polygon.kt:83`): 4,096 bands for a rectangle's four segments; one line, and about 100 KB
    less heap a rectangle (over 1 GB in f116): 45.
  - `snapshot made` and `quests.json` 172 s (`Output.kt:91-163`): 60-110.
  - `pass: nodes` and `pass: ways` 736 s are the file's full decode, already over threads: nothing cheap.
- **(5) The publish (1,155 s on 11-25).** Its history, git and cloud tail (259 s) should no longer run for a new day
  (`run.py` deploys only on a `docs/` or `config/` change); no run confirms it yet: read the next `logs/site.log`.
  - `verify` is the one term that grows: 9.4-12.6 s a kept day, 285 s at 25 days; newest day, the `back` day and a few
    rotating ones: flat near 100 s. Its 2,000 places are the same every day (seed 1).
  - build: the day before's state recomputed (42 s); text and hash made for 1,018,688 places to write 33,829 (90 s).
  - upload 283 s for 46,873 files (33,829 place, 12,901 children, 143 cities): about $0.21 a day, 1.4M Class A a month.
    Packs by id prefix would be about 8,000 a day (pack size a guess). **From 11-30 `back = di - 28` starts to move and
    the children uploads may double (a forecast).**
- **(6) The city run:** downloads are about 70% (1,598 s of 2,307 s on 11-25, Geofabrik's speed); it is to be retired, no
  win worth making.
- **Not looked at:** the Rust `update` (708 s: find 302, rule 214, write 131), tier 2 reads (1,074 s; the index per
  read, `.scratch/anomalies/t2-reads/NOTES.txt`), the gate's four engines (279 s).
- **The crash files in the repo root** (`hs_err_pid{11428,26484,55252,57228}.log`, two `replay_pid*.log`, 2 MB,
  untracked) are 11-23's four engines, diagnosed; they may go when the owner says.
- **Owner (wizard, 11-26, about 07:55): build all four** (the engine memory rule, the points fix's install, the Python
  steps in pools, the engine loops). Read as: build and prove; **the HOLD stays and is the owner's to lift.**
  - **Decided before the fan-out (08:05):** (i) the 558,000 small files stay as they are this round: the Python part
    writes them through a pool, the engine's "one file per group" is not built; (ii) file passes use a pool of 4 and the
    Python part reports its peak memory, since the loop's own python reached 17 GB on 11-24; (iii) engine source stays on
    its branch until proof and `installDist` go together (`engine_is_stale`); (iv) **one suspect a day, proposed order for
    the catch-up days, the owner's to change:** day 1 the points fix and the memory rule (neither can change a count: one
    is proven byte for byte, the other only moves when engines start), day 2 the Python steps, day 3 the engine.
  - **Under way, in worktrees under `.claude/worktrees/` (branches `perf-room`, `perf-steps`, `perf-engine`):** three
    agents; builds and tests only until 11:00 (the inputs run is 11:15, the city run 12:15), heavy proofs one at a time
    by this session. The points fix's owed checks are this session's.
  - **The points fix's owed checks (1) and (2): done 08:03-08:12, as a reader under the HOLD
    (`.scratch/perf-review/points_owed.py 24`, log `points-owed.log`, outputs `points-owed/`).** One call as a day's
    `after` has it, generation 24: 464,929 nodes with their places, 227,703 ways and 40,637 relations of diff 5187,
    11-21's 25,358 kept points, `--rel-geometry --vertex-ways`. Old binary 455 s (points 318), new 60 s (points 16).
    **40 of 47 output files the same bytes; the kept counters and every other stat equal. The seven `v_*` files (vertex
    ways) hold the same 220,164 ways, each with the same refs, places and tags, in another order:** that order is a hash
    map's (`context.rs:662`, `by_tile.keys()` unsorted, the same line in the old source), so it differs between any
    two runs of either binary (**shown 08:38: the new binary run again on the same inputs, the same seven files
    differ, the other 40 the same**); `store_context._geo` reads
    them into a dict by id. **Peak commit: old 6.81 GiB, new 7.21 GiB** (working set 7.44 and 7.43): 0.4 GiB more.
    Left of the owed list: a day of its own. Install is still the copy of `tilestore-points-fix-5dc1fbe6.exe`.
  - **The memory rule: built, branch `perf-room` (dc997ca3, a4e5d271; worktree `.claude/worktrees/agent-a1c0a9c6bc936fa2e`),
    NOT merged.** `engine_room.py`: an alive engine counts for its cap (`-Xmx` + 0.5 GB) less what its process tree
    has committed (Toolhelp walk from the launcher's pid; whole when there is no reading); a heap per engine, 1.5 times
    its highest peak of the newest 3 kept days, 3 g to the day's 8 g (`heap_for`; keys as `harvest` names them,
    `t2/groups/f12/old`); a memory failure under the day's heap is run once more at the day's heap (`in_room`,
    `-XX:+ExitOnOutOfMemoryError` on sized-down engines, the failed log kept as `engine-failed.log`); `given.json`
    beside each log and `"given MB"` in `engines.json`; a line a phase (`engine room: tier 2 old: most 3 at once,
    waited ... s summed`). **`SCOQ_ROOM_SIZED=0` is the old rule.** `stream.engine` and `notes_day` start the engine
    with Popen (`run_started`). Tests: pytest 392 passed, 3 skipped (31 new, `tests/test_engine_room_sized.py`).
    - **On real engines (this session, 08:25, `.scratch/perf-review/room_smoke.py`, log `room-smoke.log`):** main's
      installed engine on the f10 fixture, three at once at 4 g through `in_room`: the reading reaches `java.exe`
      (each tree 1.7-1.8 GB, so 2.7 of 4.5 GB still owed), `given.json` written, `state.bin.json` the same in all.
      The fixture ran to the same output in a 1 g heap (16 s; other runs' peak near 2 GB): an engine's need can be
      well under its peak.
    - **The second run after a memory failure, on a real engine (08:37, `checks2.py A`, the
      first attempt starved by a later `-Xmx64m`):** "retried failed for memory at 4 g (OutOfMemoryError); once
      more at 8 g", `given.json` with both heaps, `engine-failed.log` kept, `state.bin.json` the same as the other
      runs', no `hs_err` file.
    - **Its sizing on 11-25's real engine names (`heap_for`, history 11-22 to 11-24):** tier 2 a mean of 5.8 g (78
      of 256 at 8), tier 1 4.3 g, the notes 3.1 g; 2 of 256 tier 2 peaks of 11-25 pass the heap given.
    - **To watch on its first day:** `"given MB"` under 8192 for most engines (all 8192: the keys did not match);
      "they can take X g more" under alive times cap; the phase lines; "failed for memory ... once more" lines; no
      new `hs_err`. The 8 GB kept back is now the only slack for `tilestore read` and the rest.
  - **The engine loops: built, branch `perf-engine` (8a84d10c, 1c831f03, 1d661f56, 1650e0ca; worktree
    `.claude/worktrees/agent-a4ec03b1f84c678b7`, its own `installDist`), NOT merged, NOT installed.** Parts grouped by
    city in one pass (`Cities.partsByCity`); a polygon's bands scaled by its segments (`Polygon.bandsFor`); a city to
    elements index made once (`CityElements.kt`), read by `AreaPass.elementsOf`; `dateCandidates` over the rectangle's
    own lists. `-Dopenquests.areaIndex=false` is the old scan, `=verify` does both and fails on a difference. Not
    built: one file per group, `Output.kt`. Engine tests 115 passed, 4 skipped (109 before).
    - **Proofs:** the f10 fixture (the agent): `quests.json`, `state.bin.json` byte for byte against main's install,
      `state.bin` the same 564,816 records, with the index, with the scan and with `verify`. **A gate region (this
      session, 08:22-08:24, `gate_proof.py europe-east 2026-11-25` in the worktree's `.scratch/perf-engine-proof/`, log
      `.scratch/perf-review/gate-proof-east.log`): both at `-Xmx27g`, old 58 s, new 51 s, ALL EQUAL** (`state.bin` as a
      multiset). The index there: 3,498,214 pairs, 13.3 MB. Choosing 0.26 s to 0.00, `dates` 4.56 to 3.87 s; the
      saving shows only on tier 2's rectangles, which no kept input holds (f10: 0.7 s to 0.05 s).
    - **Install, when the owner says:** merge and `installDist` in main together, the install folder copied aside
      first (as on 11-23); until then keep the worktree (its install and scratch are the proof's).
  - **The Python steps: built, branch `perf-steps` (7 commits, head cea271d6; worktree
    `.claude/worktrees/agent-a2dd76c9aa4d4c5f4`), NOT merged.** Nothing of it has run on a real day.
    - *Timers:* tier 1 (small pbf, engines, ingest, rewrite), `tier 2 delta` (changed groups, first pass, second
      pass, rewrite), counts (note engines, sets save, count files, save), `touched and rects`; in
      `planet_store_day.py` `timer:` lines (day.pkl save, read back, load, the engines' harvest, the deletes), kept
      in `steps.json` under `timers`. `day.json` and `world.json` gain keys under `seconds`: the only output bytes
      that differ.
    - *Order-independent:* the day's record (`engines.json`, `day.json`) is now written BEFORE `compact`, and
      `work/` and `before/` are deleted in a thread beside it, joined before the free-space check (`record_work`,
      `delete_bulk`; a `recorded` marker for a resume). **So a STOP in `compact` now finds those two folders gone**
      (nothing reads them after the gate, and it gives compaction its disk: the stop of 11-25, 01:30); `day.pkl`,
      `finished`, `gate/` stay to the end, `gate.json` is still copied after `compact`. The refresh cuts the gate's
      four notes clips in its one pass over the dump (`world_gate.gate_clips`; a clip whose header names another
      dump is cut again by the gate). `W/place-bboxes.npz` stamped with `places.json`'s size and mtime.
      `old_rows_of` uses the threaded `world_tier2.old_rows` (same dtype and bytes, tested).
    - *Pools:* new `tools/stream/file_pool.py` (`WORLD_FILE_POOL`, default 4; 1 is the old loop, no pool; results
      consumed in file order, at most that many files held): tier 1's rewrite, both loops of the delta,
      `count_files`, the engine files' writer. Tests (`tests/test_file_pool.py`, 11): pool 1 against 4 on a
      seven-file world, every file byte for byte and every returned value; tier 1 and counts also against the old
      loop.
    - *The agent's small benchmark (8 files of 1.5M rows, pool 1 to 4):* tier 1 rewrite 2.2 to 0.8 s, delta 4.7 to
      2.4 s, counts 8.4 to 6.2 s, old rows 0.8 to 0.4 s, 20,000 small files 16.9 to 11.9 s (the writes themselves
      do not scale with threads: `engine files` will save well under the 400 s guessed above). Peak commit not
      measured by the agent; `WORLD_FILE_POOL=1` or `2` is the knob on a starved day.
    - **On the real world (this session, 08:38-08:54, `checks2.py C`, log `.scratch/perf-review/checks2.log`):** the
      counts' per-file sums (`by_set` through `file_pool.ordered`) over all 128 `world.bin`, 52.6 GiB: **pool 1
      397 s and 366 s, pool 4 172 s; the same 25,475,506 sums in the same order (one sha256); peak commit 2.8 GiB
      against 5.8 GiB.** So about 200 s of `counts` for 3 GiB more commit; the rewrites hold more a file (about three
      copies of its rows a worker) and are not measured on real data.
    - **Changed by this session (ceea7e76 on `perf-python`, the commit before it on `perf-steps`):** `before/` (52 GB,
      few files) is deleted before `compact` starts, `work/` beside it: the thread took the small files first, and
      compaction asks for the disk's free space as it starts.
    - *Not built, as decided:* tier 1's engines beside cover and rectangles, the note engines beside the delta,
      dropping `tilestore ways`, folding tier 1's rewrite into the delta's: after a day of the timers.
  - **Both Python branches together: branch `perf-python` (15c6a2cd; worktree `~/Code/sc-open-quests-perf-python`),
    main with `perf-room` and `perf-steps` merged** (two conflicts in `world_day.py`, both sides kept: the room's
    phase line beside the new timers). **pytest there: 410 passed, 3 skipped.** Not merged into main. `run.py`
    imports `tools/stream` modules, so a merge reaches the 11:15 inputs run and the 12:15 city run as well.
  - **ALL FOUR INSTALLED IN MAIN (11-26, 09:06-09:12; owner, wizard, about 09:00: "Everything now", told that
    today's 11:15 inputs run and 12:15 city run then import the changed Python and run the new engine, and that the
    first catch-up day has four suspects).** The machine was still (no RUNNING, tasks Ready, HOLD there).
    - `perf-python` merged (81df89fd: the memory rule and the Python steps); pytest in main 412 passed, 1 skipped.
    - `tilestore/target/release/tilestore.exe` is now the proven points-fix binary (sha256 a3c49f7e..., copied, not
      built); the one before (6249b9b1...) is `.scratch/perf-review/tilestore-before-points-fix.exe` and
      `.scratch/anomalies/tilestore-points-counters-edb0521e.exe`. The loop copies the binary at its next start.
    - `perf-engine` merged (9330eee8) and `installDist` run in main; `engine_is_stale()` False; the engine's tests
      pass in main. **The installed engine run once on europe-east (11-25's clip, `-Xmx27g`, 49 s): ALL EQUAL to the
      proof's outputs** (`.scratch/perf-review/engine-proof/gate/europe-east/installed`). The install before it:
      `.scratch/perf-review/engine-install-before-perf-1126/`.
    - **To undo, each by itself:** the points fix: copy `tilestore-before-points-fix.exe` back. The memory rule:
      `SCOQ_ROOM_SIZED=0` in the loop's environment (or revert). The pools: `WORLD_FILE_POOL=1` (the timers, the
      delete beside `compact`, the gate clips cut with the refresh and the bbox cache have no switch: revert
      81df89fd with `-m 1`). The engine's index: `-Dopenquests.areaIndex=false` in the engines' options, or copy
      the old install back and `git revert -m 1 9330eee8` (else the next city run rebuilds from source).
    - **Scheduled into this session for 13:20 today:** a read-only check of those two runs.
    - **To check after today's runs:** `inputs done` in `logs/inputs.log` (11:15) and `update done` in
      `logs/scheduler.log` (12:15, the first city run on the new engine: its counts against yesterday's).
    - **To check on the first world day after the HOLD is lifted (the owner's to lift; four suspects if the gate
      fails):** the gate; `engine room: ... most N at once, waited ... s` a phase (11-25: tier 2 waited 6,190 s a
      phase at 1-2 alive); `"given MB"` in `engines.json`; "failed for memory ... once more" lines; the `points`
      seconds in the two "store context at generation" lines (11-25: 210 s and 228 s); the new `timer:` lines and
      `tier 1:`, `tier 2 delta:`, `counts:` splits; `area cities` timers `ways chosen`, `tagged nodes chosen`, `city
      sets holding the city`, `dates` and `engine: parts of each city` summed over tier 2 (11-25: 213, 159, 165,
      179, 106 s a phase); the day's wall against 12,643 s; free commit and disk at their lows.
    - Worktrees and branches of this work removed (no links in them); nothing pushed. Outputs kept:
      `.scratch/perf-review/` (logs, scripts, the engine proof, the two installs before; the points and room check
      outputs deleted, their logs kept).
- **The delete was stopped at the 2-hour limit of a background job (11-26, about 07:00), not finished:** 250,000 of 1,129,125 old files gone,
  879,125 left in `bucket.json` "kept" (the sixth batch was cut mid-way; S3 deletes of a gone file are harmless, so a rerun is safe). A batch
  of 50,000 takes about 20 minutes, so the rest is about 6 hours: it needs a detached run, not a session's background job. Command:
  `python tools/world_publish.py upload --delete-kept --max-delete 1200000` (resumes). Nothing reads the remaining files.
- **The rest of the delete runs detached (owner, 11-26, 07:55: "start"):** bash pid 36972 (hidden), log `.scratch/overture-next/delete2.log`,
  879,125 files in 18 batches, expected done about 14:00; its last line is `exit 0` when finished. If it dies, start the same command again.
- **Before lifting the HOLD (read-only review, 11-26, 09:25-09:45; owner: "anything else we need to do before we enable world
  dailies?").** The machine: HOLD (11-25 20:02, the owner's pause), no RUNNING, no STOPPED; store and world at 11-25, no open day;
  `place-ids` and the other branches have nothing left unmerged; worktrees left are `agent-a9b152...` (kept) and `place-ids` (merged).
  C: 130 GB free (a day's lows on 11-25: 129-131 GiB).
  - **Owed by the rename's runbook (step 7, before "HOLD off"): a new state checkpoint.** `state_checkpoint.py list` has only
    2026-11-14, which holds the old place ids. `link` refuses on this disk (twice the rows and 40 GiB), so it is `upload --from-world`
    with the loop held (about 1.5 h standstill, about 48 GB up). Not run: needs a slot outside 11:15 and 12:15.
  - **Wait for the 13:20 check first:** the four speed-ups have not run on anything scheduled yet.
  - **The sc-data delete** (`upload --delete-kept`, no `daily.lock`) ends about 14:40-15:00 by its pace; it and a world day's
    `world_publish daily` both save `bucket.json` from their own copy, so the delete should show `exit 0` before the first day's
    publish (about 3.5 h after a 14:45 start, so no overlap expected). A clash only costs a re-upload.
  - `.scratch/world-places/world/places.json` (old ids, 11-13) is read by nothing in the loop, only `world_tier2.py`'s CLI defaults.
  - **Not built and possibly on the owner's "all the new things" list:** the Overture 12-16.0 ingest tool, the city run's retirement.
  - **After the first day:** the first-day checks above (gate, engine room lines, `given MB`, timers) and `rename_places.py check` again.
  - **Checkpoint running (owner, wizard: "Now, before 11:15"; started 10:50, later than planned because the question waited):**
    `state_checkpoint.py upload --from-world`, hidden bash pid 60084, log `.scratch/checkpoint-1126.log` (last line `exit 0` when
    whole), to `r2:sc-open-quests-archive/state/2026-11-25`, 52.6 GiB at about 44 MB/s (about 20 min). If it dies: the same command
    again, under the HOLD. The dry run leaves its links in `.scratch/planet/checkpoint/2026-11-25` (the real run reuses and removes them).
  - **Checkpoint DONE 11:13:21** (10:50-11:13, before the 11:15 inputs run): `2026-11-25: whole` in R2 (new ids), local links
    removed. `2026-11-14` (old ids) is still there; `prune --keep 1` would drop it, not run. **Left before the lift: the 13:20 check
    of today's runs, then the owner removes HOLD** (the 14:45 task takes the day if HOLD is gone by then; else start the loop by hand).

- **The crash files (2026-11-27, 18:40):** the owner asked how old and whether analysed. They were 11-23's four tier 2
  engines at a fixed `-Xmx8g` ("G1 virtual space", about 67 s in; out of commit, not heap), diagnosed above and in
  `journal/2026-11-21-storage-redesign-facts-serving-working-state.md`; the engine memory rule came of it. **They were
  already gone from the repo root** (no `hs_err*`/`replay_pid*` anywhere outside `.scratch`); who removed them and when is
  not recorded. The handoff's item is dropped.
