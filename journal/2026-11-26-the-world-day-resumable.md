## The world day resumable (owner, 11-26, 18:05: "build a resumability please"; the laptop stays on, only the owner is offline)

- **Built: c3b998fd1** (`tools/stream/day_cache.py`, its docstring is the design; `tests/test_day_cache.py`, 12 tests; suite 432
  passed, then 440 with `overture-switch` merged in 06ac3b7d4 by the other session). A finish that stops is still put back to
  `before/` and its world writes (tier 1 rewrite, tier 2 delta, hidden flags, counts) replayed in order, so the place-set
  numbering stays; what writes nothing into the world is **kept behind a marker** (`done.json` in its own output folder, written
  last): the cover and rectangles (`t2/`, with `cstats`, `rinfo` and their seconds), tier 1's small PBF (`t1/`), every tier 1
  engine, every tier 2 group and date (also skipping its `tilestore read`), every note engine (its counts). No marker: the folder
  is emptied first. **`SCOQ_DAY_CACHE=0` ignores every marker** (the way back). By 11-25's timers a late stop now costs the
  replay (about 25-35 min) instead of the whole finish (2.8 h).
- **PAUSE** (`.scratch/planet-cut/PAUSE`, its text the reason): the day stops at the next engine start, room wait or step;
  engines running end and keep their output; the run ends with "paused:", no STOPPED; while it is there no day is taken or
  resumed. Delete it and `schtasks /Run /TN kk-SCOpenQuests-planetstore` to go on. HOLD is unchanged (a reader's: the day finishes).
- **Taking over a dead RUNNING ends its orphans** (`end_orphans`: the dead pid's python, java, tilestore, osmium descendants and
  any engine or tilestore naming `world-days`), so a killed run's engines no longer write into the work being reused.
- `day.json`/`world.json` of a resumed day carry `"kept"` (what was reused); its seconds are partly the stopped run's.
- **The proof, running since 18:22 (detached harness pid 27752, `.scratch/resume-proof/proof.py`, log `proof.log`, its pid in
  RUNNING, under the HOLD):** A = 11-26's finish killed and resumed at five points (tier 1 engines; tier 2 old; a PAUSE in tier 2
  new; mid delta; a python-only kill in the note engines with `end_orphans`), then to the end; B = the same from `before/`,
  uninterrupted, `SCOQ_DAY_CACHE=0` (the day's record). Every world.bin and keys file, place-sets, touched, rects, counts/11-26,
  and world.json's and day.json's last day (minus seconds and kept) compared: `RESULT.txt`. Then `finished` is written; no gate,
  store_tail or publish; **HOLD stays (the owner's)**. Expected end about 03:00-04:00. The other session holds
  `overture_switch.py prepare` (DuckDB) until then. If it dies: read `proof.log` and the `A*.out`/`B.out`; rerunning is safe
  (each run restores from `before/`).
- **5e's resume proof runs all night (from 18:22, harness pid 27752 in RUNNING, `.scratch/resume-proof/proof.log`; ends about
  03:00-04:00 with `RESULT.txt`).** `prepare` waits for `RESULT.txt` or 5e's message (DuckDB beside the engines risks the 11-23
  commit-limit failure).
- **The proof stood still 18:24-22:52: the laptop was in Modern Standby** (System log, Kernel-Power: "power source change"
  18:16, "entering Modern Standby" 18:24, sleep 22:36, plugged in 22:52). Desktop processes are frozen there: A1's first
  `tilestore ways` read 15,982 s against 197 s at 17:38, with no work done. Nothing was wrong with the code; the run went on by
  itself on waking. **A keep-awake helper** (`.scratch/resume-proof/keep-awake.ps1`, pid 14192) holds a "system required" power
  request until the harness (27752) exits; a closed lid or battery policy can still sleep the machine. New estimate: RESULT about
  07:00 on 11-27. **The loop itself has no keep-awake** (no `SetThreadExecutionState` anywhere): a world day on an unplugged or
  idle laptop stands still the same way. Proposal for the owner, not built: the loop holds that request while RUNNING exists.
- **22:55:** the laptop slept 18:24-22:52 and the proof stood still; it runs again under a keep-awake helper, and 5e now expects
  `RESULT.txt` about 07:00 on 11-27. `prepare` still waits.
- **Proof progress (00:35 on 11-27):** A1 (kill in tier 1, 3 engines kept), A2 (kill in tier 2 old: the cover reused in 9 s, 128
  tier 1 engines kept), A3 (**PAUSE: the child ended 58 s after it, at the next group's read; the engines running finished and
  were kept, 10 -> 14; no engine left**), A4 (meant mid-delta, but the delta took about 7 min, not 13, so the kill fell in the
  note engines, 121 of 128 kept), A5 (its trigger already true: killed at its start, no engine alive, nothing to end), A6 to the
  end. **Supplement C** (`proof_c.py`, chained by `chain-c.ps1` pid 19716 to start when the harness exits, keep-awake of its
  own): C1 killed inside the delta, C2 a python-only kill with note engines alive then `end_orphans`, C3 to the end; held against
  B's fingerprint (`RESULT-C.txt`); B's world.json and day.json put back only if C equals B.
- **A ended (00:53 on 11-27); B and the result (02:26).** A6, with every step kept, replayed the whole finish in 1,064 s.
  B (uninterrupted, cache off) took 5,511 s. **RESULT.txt: DIFFER, 6 of 263**: `files/f0`, `f67`, `f110` `world.bin`,
  `place-sets.json`, `counts/2026-11-26/counts.json` and `counts.npz`. Every other world.bin, every keys file, touched, rects and
  both records (minus seconds) equal.
- **Supplement C stopped (02:27)**, so it would not overwrite B's world, which the diagnosis needs. C1's restore had begun:
  f0-f7 went back to 11-25 (B's f0 lost) while world.json stayed at D, a half-restored world that the next finish puts back whole.
  B's f67, f110, place-sets and counts kept in `.scratch/resume-proof/B-keep/` (hard links).
- **R1 (02:29-02:49, `proof_r.py`): the finish replayed from B's kept outputs, cache on: EQUAL to B, 263 of 263.** Given the
  same engine outputs, the resumed path reproduces the uninterrupted day byte for byte, place sets and counts included. So A
  differed because some of its engine outputs were made in other runs than B's. **R2** (from 02:49): a second uninterrupted run,
  cache off, to see whether two clean runs of the same day differ the same way; then `canon.py` compares B and R2 up to place-set
  numbering (`R2-keep/`).
- **R2 (02:49-04:18): a second uninterrupted run, cache off, DIFFERS from B in 5 entries of the same kind** (f67, f110
  world.bin, place-sets, counts.json, counts.npz). `canon.py` on B's and R2's copies: both tables hold the same 1,795,925 parts
  and 7,213,113 sets as sets of names, numbered in another order from part 1,784,532 and set 6,993,147 (the day's new ones);
  f67 and f110 equal in every field but `place`, which differs in 185 and 165 rows, **equal up to numbering**. So the numbering
  of a day's new place sets is not reproducible run to run (cause unconfirmed: probably the order an engine lists a dump's sets in), cache or not; A's
  difference from B is that kind. A's own files were gone by then (B rewrote them), so A against B up to numbering is inferred
  from R1 and R2, not measured. The counts files differ with the numbering only: checked 05:05, B's and R2's 27,772,395 count rows
  equal by part name, quest and measures.
- **Supplement C (04:20-05:02, against R2): EQUAL, 263 of 263.** C1 killed inside tier 2's delta (checked: the delta's own line
  not yet written), C2 a python-only kill while note engines ran (8 note markers removed so they ran again): **the note engine
  died with its python** (0 alive right after), so `end_orphans` found nothing; its ending of a live orphan is untested on
  real engines. C3 to the end. R2's world.json and day.json put back: **the world is R2's uninterrupted 11-26, `finished`
  written**, its seconds an uninterrupted day's (5,447 s finish). RUNNING gone, HOLD on.
- **What the proof shows:** a finish stopped anywhere (tier 1, tier 2 old, tier 2 new by PAUSE, the delta, the note engines)
  and resumed ends byte for byte where an uninterrupted run on the same engine outputs ends (R1, C); engines rerun after a
  stop can renumber a day's new place sets, as any two runs do (B, R2). A late stop costs about 18 min (A6, C3).
- **Closing (05:10 on 11-27):** the resume state checked read-only (store at 11-26 gen 25, node file 11-25, world 11-26,
  `finished`, the 11-26 Europe clip pinned): the next start resumes at the gate. `end_orphans`' selection tested on a faked
  process list (`tests/test_day_cache.py`, 13 tests). The settled design: `design/topics/the-world-day-resumable.md`, with what is
  tested only with mocks or not at all. `B-keep/` and `R2-keep/` deleted after the comparisons. Read order for the result:
  `.scratch/resume-proof/README.txt`.
- **11-27, about 11:30 (owner, wizard): keep-awake for the loop: "No".** Not built; a day on a laptop in standby stands
  still until it wakes, then goes on. The owner had lifted the HOLD at 09:20 ("start the day"); 11-26 resumed at its gate:
  PASS (worst city 0.00177%), store checks explained, done 09:33, published 09:48. 11:15's inputs failed twice on the Europe
  fetch (Docker Desktop not running); started 11:31, try 3 fetched diff 5189; a loop run started by hand at 11:30 takes 11-27.
- **11-27 15:45 check: 11-27 STOPPED at 14:51.** Tier 1's engine t1/f0: `FileNotFoundException:
  .scratch/planet/world-places/files/f0/cells/f0c0.json` (as the engine names it, with backslashes). world-1101's `files/*/cities.json` name all 2,244 cell
  boundaries under `.scratch/planet/world-places/files/<f>/cells/`, the folder the owner let go this morning (58 GB, with the
  other session). world-1101 holds its own `files/*/cells`, all 2,244 matching plan.json's rects and names, byte-equal to
  `.scratch/planet/world` and `world-2026-11-18.0`'s; copied back to the named paths (3.2 MB), nothing missing after. Owner
  (wizard, about 15:48): "Restart now". 15:49 the loop resumed 11-27: the world put back (0 files: tier 1 had not written),
  **cover and rectangles kept from a run that stopped (284,371 rectangles) in 12 s**, tier 1's engines from scratch (none had
  ended). Also found: prepare ended 11:54:35 and the store's update started about 14:19: `world_day.quiet` still waits out
  `backfill_history.QUIET` (16:55-19:15 UTC), the deleted 12:15 city run's window. Owner (wizard): "Remove it": branch
  `no-city-window` (6ace25759), to merge after the day. Publish at 14:54 exit 0 (no new gated day).
