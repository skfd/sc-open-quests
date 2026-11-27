## The world day resumable (2026-11-27)

Owner, 11-26 18:05: "is there a way for this process to be pausable/resumable?", then "build a resumability please".
Built in c3b998fd1 (`tools/stream/day_cache.py`; its docstring is the design), proven on day 11-26 (the story and the
numbers: journal/2026-11-26-the-world-day-resumable.md).

- **The world writes are always replayed, never kept.** A finish that stops is put back to `before/` and its writes (tier 1's
  rewrite, tier 2's delta, the hidden flags, the counts) run again in order, as before. Ingesting a dump numbers place sets,
  so dumps are read again in order on every run; ingested rows are never kept.
- **What writes nothing into the world is kept behind a marker:** the cover and its rectangles (`t2/`, with `cstats`, `rinfo`
  and their seconds), tier 1's small PBF (`t1/`), every tier 1 engine, every tier 2 group and date (its `tilestore read`
  skipped too), every note engine (its counts). The marker (`done.json` in the step's own output folder) is written last,
  through a temporary name, after the step ended well; an output folder without one is emptied before the step runs again.
  `SCOQ_DAY_CACHE=0` ignores every marker.
- **PAUSE** beside the store stops a running day at its next engine start, room wait or step; running engines end and keep
  their output; the run ends with no STOPPED and takes or resumes no day while PAUSE exists. HOLD is unchanged: a reader's,
  the running day finishes.
- **Taking over a dead RUNNING ends its leftovers** (`end_orphans`): the dead pid's python, java, tilestore and osmium
  descendants, and any engine or tilestore naming the days' work, never the run itself or its parents.
- **What was proven on 11-26:** stopped in tier 1's engines, tier 2 old, tier 2 new (by PAUSE), inside the delta and in the
  note engines, then resumed, the world ends byte for byte where an uninterrupted run on the same engine outputs ends (263 of
  263 entries). A late stop costs about 18 min, not the 2.8 h finish. **Not reproducible run to run, cache or not:** the
  numbering of a day's new place sets (two uninterrupted runs: rows, place sets and counts equal up to numbering).
- **Only tested with mocks, or not at all:** PAUSE through the real task (`guarded`, `days()`, RUNNING removed) and the pause
  before the store's update with `prepare` redone after it (mocked); `end_orphans` ending a live process (its selection on a
  faked process list only: on 11-27 a killed python's note engine died with it); kills inside the cover, tier 1's rewrite and
  the counts' save.
