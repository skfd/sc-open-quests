## Pinned chart titles in sentence case again (2026-11-16, evening; owner: "was it always there?")

- Pinned quest cards showed titles Capitalized On Every Word ("Is There A Shelter At This Stop?"). Not always:
  pins came 10-21 in sentence case; the places page's `.card h3 { text-transform: capitalize }` (10-24, for
  lowercase place kinds like "county (12)") reached them too. `.multiples .card h3 { text-transform: none }`
  in `docs/style.css` undoes it for the pins only; places headings keep their capital.
- **Day 3 and the planet punch: done, exact (11-16, 13:36-19:25).** DESIGN.md, "Compaction". Day 3 (diff 5167) on
  the compacted store exact against the 11-05 clip (control 1,489). The punch's dry run equal to the independent
  count to the byte; 9.40 GiB of pack 0 given back, every live tile the same, generation 3 against the clip the
  same after; generation 0's pairs (21.25 GiB) gone. **It took 5.45 h** (0.47 s a range); later punches skip what
  is already given back (31b7c503). **Now:** `.scratch/planet-cut/store` at 11-05, generation 3, compacted at 2,
  punched at 3; `.scratch/planet-day/planet.loc` at 11-05. C: 141 GB free. `europe-2026-11-03` unpinned (its check is
  done); `europe-2026-11-02` stays pinned for the engine's count on a read of the planet store. **Next:** the punch's
  per-call cost (measure, then decide daily or weekly); days 5168-5176 are kept in `.scratch/planet/diffs-keep`
  (their Europe clips age out of the store 14 days after their day, so 11-06 goes about 11-20); the 12-07 plan (cut
  fresh or keep this store going) is the owner's call, with disk.
**Owner's answers (13:10): all four as recommended.** Next session: the unified place page first
(planet store waits); the chart opens on 90 days, notes at the import steps; density tiles replaced;
zero rows folded into "N done here". Details at the end of the review file. Also fix the phone table's
clipped questions and `app.js:1506`'s stale "no history yet" line.
- **Why the punch was slow: found and fixed (11-16, evening; owner: "work out why the punch is slow").** DESIGN.md,
  "Why the punch was slow". Its own hash pass read pack-0000 through a memory mapping; while those pages stay in
  memory every zeroing call and flush of that file is slow (0.4-0.9 s on the planet pack; on a 30 GiB test file 21
  ms after a mapped read, 0.04 ms without; not the extents, not cached pages). The hashes now come from block reads
  (the change is in 41dacebd, swept into another session's commit): the clip's punch phase 12.9 s to 0.1 s, exact.
  pack-0000 is back to 0.04 ms calls (its mapped pages were pushed out by reading other data). Not yet shown at
  planet size: the next planet punch. Test files deleted; the scripts stay in `.scratch/punch-cost/`. **Rule: no
  reader of packs may use a memory mapping.**
- **The planet store, kept daily (11-16, 20:15; owner: "yes catch up and setup daily").** The owner chose to keep
  the store going rather than cut fresh at 12-07. `tools/stream/planet_store_day.py` moves it forward by every diff it
  has not had: update (`--world --group-mib 512 --prune-pairs`), node file forward and held against the Europe clip
  of the same sequence, the new generation against a cut of that clip at 2 km with every difference explained
  (`tools/stream/tilecheck/why.py`), then `compact --min-dead 0.25` and `punch`. Any failure writes
  `.scratch/planet-cut/STOPPED` and later runs refuse until a person removes it. It keeps each diff it uses in
  `.scratch/planet/diffs-keep` (hard links). Log `logs/planet-store.log` (stdout of the task in `planet-store.out`).
  - **Task `kk-SCOpenQuests-planetstore`, daily 14:45** (from 11-17; waits for the 12:15 run, and up to 8 h for the
    monthly planet job, then leaves the day to the next run). Registered with the owner's yes.
  - **Caught up (11-16 20:16 to 11-17 00:41): eleven days, 11-06 to 11-16, each exact** (generation 14 at 11-16;
    node file equal to each clip, 37 differing tiles a day all explained, no STOPPED). DESIGN.md, "The planet store
    caught up". One slow punch (generation 13, 25 min, the machine busy with other sessions' work), the rest seconds.
    **For the world loop: D-1 is readable only between the store's `update` and its `compact`** (compact and punch
    mark older generations unreadable), so the world day goes between them. C: 258 GB free after.
- **12-07, the plan rewritten (owner: keep the store going):**
  - **No fresh cut and no node-file rebuild.** The planet store and its node file move by daily diffs and never read
    `history-261102` again; the monthly job retiring that file does not touch them.
  - **The monthly job still runs** (`kk-SCOpenQuests-planet`, Monday 12-07 07:30, up to 14 h: the history file, the
    clips' re-cut and months). It needs about 170 GB while it writes the new history file, plus the 40 GiB floor:
    **about 213 GB free by 12-07 07:30, against 138 GB now, so the owner frees about 75 GB** (the store stays about
    flat under compaction, so today's free space is the baseline).
  - That day the planet store's 14:45 run waits for the monthly job (or skips; the next run catches up).
  - Superseded by this: the fresh-cut option, "`planet.loc` must go before 12-07", and rebuilding the node store from
    the 12-07 file. The world stream (tier 1), if taken up again, could read the store's node file
    (`.scratch/planet-day/planet.loc`, the same layout and `.state` form) only if it never writes it; not designed.
  - Still on 12-07 as before: the batch engine's canary on polar and antimeridian cells, when a world count runs.
- **The monthly planet job: disabled (11-16, evening; owner: the Europe clips' re-cut "lets avoid unless critical",
  name-ru-repair "let that project download on demand, it is not yet operational").** `kk-SCOpenQuests-planet` is
  `Disable-ScheduledTask`d, still registered (`Enable-ScheduledTask -TaskName kk-SCOpenQuests-planet` brings it
  back). So nothing runs on 12-07 and **the owner does not need to free 75 GB for it**. The daily run (`run.py
  update`) does not read the planet history. The diffs since 11-02 stay in the shared store while the history file
  is behind (osm-extracts keeps what a pass needs), a few GB a month. Open: what a repin recounts now (the owner asked
  for a suggestion: only back to the previous major version, or another sane rule), and whether
  `history-261102.osh.pbf` (171 GB) and `europe-history-261029.osh.pbf` (8 GB) can go.
- **History files deleted (11-16, evening; owner: "sure go ahead"):** `~/Code/.osm-data/planet/history-261102.osh.pbf`
  (171 GB) and `europe/europe-history-261029.osh.pbf` (8 GB). Their `.meta.json` and `planet/latest.json` stay as
  records, so `osm_extracts.py path planet` names a missing file and anything needing the history fails loudly; a
  new history is downloaded on demand (hours). C: 140 GB free to 306 GB. Nothing scheduled reads them: the daily run
  counts from extracts, the planet store from daily diffs, the monthly job is disabled. Consequences: a recount from
  history (`backfill_history.py`, the clips' months, `recut`) needs a fresh history first; name-ru-repair downloads
  its own when it becomes operational.
