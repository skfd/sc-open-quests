## Release goals (owner, 2026-11-16, late evening)

- **Release 1: daily world updates, with 30 days of them published** (the widget's window and the place page's
  "Last 4 weeks" tile are 28 days). The place chart keeps opening on 90 days (`RECENT_DAYS`); for world places it
  starts at the first world day until 90 have built up. Every published day counts every quest (rule above).
- **Release 2: a monthly backfill for the world**, built and running (monthly points from 2017-01, as the cities have).
- **Backfill: from November 1 (owner, 2026-11-16, 21:40).** The first published world day is **2026-11-01**,
  the planet at 2026-11-01T00:00Z (snapshots are named by the instant they count, `data_date`; europe-west's and
  Ontario's published 11-01 snapshots are that instant). Day one is checked against every region's published 11-01
  snapshot; from 11-02 on, each day also against its Europe clip (the oldest kept is `europe-2026-11-02`, sequence
  5164). 90 days back was not taken (no check for most of it).
- **Supersedes** "daily from the 11-08 seed onward" (11-14, "The world's resolution"): the 11-08 seed has no area
  quests' dates, so under the rule it cannot start the published series. The 11-08 full count itself is still a valid
  all-quests world point.
- **The store is held, Claude's call at the owner's "you decide".** Each world day needs the map data at D-1 and D,
  and the daily run's compaction may not keep D-1 (not checked), so the store must not run ahead of the world loop.
  And the store is at 11-08 by tonight, past the seed day, so it is **cut again at 11-01T00Z** and held there until
  the loop is built; then store and loop go forward together, one day at a time, catching up.
- **Plan, in order:**
  1. The world read from the store (every file's cells to the engine) and the dated seed, built against today's store,
     which keeps running daily meanwhile as a rehearsal of the daily store run.
  2. A planet history file again, through osm-extracts (hours, about 170 GB; check what `fetch planet-history` does
     with `history-261102` missing first). Then the current store is deleted, the store cut at 11-01T00Z (about
     1 h 42 min, about 290 GB peak), the node file built at 11-01, the history file deleted, and
     `kk-SCOpenQuests-planetstore` disabled until step 4.
  3. The seed: the world at 11-01 from the store, counted with `--state` and area dates, checked against the
     published snapshots of 11-01 (every region).
  4. The world-day loop (tier 1 on the store's node file, tier 2 from the store, area dates), each day checked as
     above; caught up from 11-02 (diff 5164; download it again if the store has pruned it), then daily.
  5. Publish world places once 30 days are in (bucket `sc-open-quests-data` at `sc-data.comentality.com`, Cache Rule
     live since 11-17: every upload must carry `Cache-Control` or it is not cached).
  **When:** the catch-up counts towards the 30, so release 1 is the day steps 1-4 are built and caught up, any day
  after 11-30 (11-01 plus 30 days). The build time and a world day's cost (not measured) decide it, not a 30-day wait.
- **Oracles pinned (21:45):** `europe-2026-11-02` to `11-16` in `~/Code/.osm-data/europe/pins.json` (25 GB), reason
  "release 1". **Each new Europe clip needs pinning too until the loop has checked its day** (a clip goes 14 days
  after its date); unpin each day once it is streamed and checked. The planet diffs from 5165 are hard-linked in
  `.scratch/planet/diffs-keep` by the store run.
- **Building, 2026-11-16 from 22:00 (owner: "lets push towards first release"); the plan is DESIGN.md, "Release 1:
  the world day, designed".**
  - **The store's hold:** `tools/stream/store_lock.py` (a reader writes `.scratch/planet-cut/HOLD`, then waits while
    `RUNNING` exists or the log shows a run going); `planet_store_day.py` takes no day while HOLD exists ("held: ..."
    in `logs/planet-store.log`, not a failure) and keeps RUNNING while it works. **A HOLD left by a dead reader stops
    the store quietly: its text says who and when; remove it by hand.**
  - Built: `world_cells.py storecut` (the plan's files read from the store into `cut/`), `tools/stream/storecheck_cities.py`,
    the reader's size-bounded blocks and its peak memory in the stats file.
  - **Running hidden, both waiting for tonight's catch-up to end (about 23:30):** `.scratch/storecheck/run.sh` (log
    `logs/storecheck-cities.log`: the 32 European cities from the store against the 11-16 clip, row for row; output
    `.scratch/storecheck/cities/`), then `.scratch/storecheck/filesize.sh` (log `logs/storecut-filesize.log`: f0 and
    f19 read at full size into `.scratch/planet/storecut-test/cut/`, figures in `storecut.json`). Each holds the
    store while it reads; tomorrow's 14:45 store run waits or takes no day meanwhile. Rerun either the same way
    (`Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' -ArgumentList <script>`); a finished
    region or file is skipped.
  - **Keep `.scratch/planet/world-places/`** (the 11-08 count and seed state): when the re-cut store passes 11-08 it
    is the one planet-wide like-for-like check of the store's read and of seven streamed days.
  - **Built later the same evening (all on main):** after `update --prune-pairs` the generation before reads byte for
    byte (so a day reads D-1 and D before `compact`); the many-rectangles probe (about 14 ms a rectangle city in the
    engine; `.scratch/manyrects/`); a city's box inline in the reader (97 s to 1.8 s for 10,000 cities); **engine
    `--dump-state` with parts writes each record's place set** (`<state>.places`, `.places.json`; Bremen's part counts
    rebuilt from the records equal the snapshot's; `.scratch/placesets/check.py`; the installed engine has it, and
    without parts nothing changes); `tools/stream/placesets.py` (world rows WREC = the record plus a world place-set
    number, one append-only `place-sets.json` per world); `DenseLocations(readonly=True)`.
  - **Fanned out at about 22:20, four agents in worktrees:** A `tools/stream/world_tier2.py` (the global cover, the
    rectangles split at cells, their cities and parts files; a planet day's rectangle count); B `world_state.py` on WREC
    rows with places and the counts per place from the state; C `tools/stream/notes_day.py` (notes at the clock:
    hidden flags and note quests); D `tilestore ways` (ways' refs and places from a generation, for old geometry and
    relation members). Each reports back; merging is mine. Their worktrees are under `.claude/worktrees/` if a session
    ends first.
  - **C merged (22:40):** `tools/stream/notes_day.py` (`hidden_step`: hidden flags carried between clocks, only rows at
    notes that opened or closed plus the day's recounts; `note_quests`: the engine counts the note quests on an empty
    PBF with the cells and parts, so places stay the engine's), `notes_check.py`, tests. Bremen and Berlin: flags and
    note quests per city and part equal the engine's second run. **Engine change with it, `StateDump.e7`:** a dumped
    position keeps SC's 6-decimal truncation (plain rounding got 11 Bremen rows' hidden flag wrong). Dumps from engines
    with and without it differ by 1e-7 on such rows, so **the seed must come from an engine with it. Not installed yet:
    `installDist` after tonight's store check and file-size reads are done** (they compare two runs of the installed
    engine, so either is fine for them).
  - **B merged (23:30):** `world_state.py seed W` (each file's dump to `files/<f>/world.bin`, WREC rows sorted, plus
    `place-sets.json` and `world.json`), `apply --places [--readonly-nodes]` (tier 1 with the cells and their parts, so
    new rows carry places), `counts W [--clock]` with `tools/stream/place_counts.py` (per world `counts/counts.npz` +
    `.json`: per (place, quest) open, nodes, ways, relations, agedOnly, open05, aged05, open2, aged2; cells as
    `city:<cell>`; notes come in through `count_files(extra=...)`). **Engine change with it:** every `--dump-state`
    writes `.places`, and each city holding a record joins its set as `city:<id>`, so a cell's total never rests on a
    test of a rounded position. Checks: Bremen equal in all 9 measures; 30 days on, the main pass equal, area quests
    equal at the default setting; Bremen as 16 cells with 1,199 places equal; tier 1 with places on a Dublin box equal
    to the next day's count. About 15 min of one thread for 2 billion rows, files in parallel.
    **Open, for the rule:** the engine dates area quests at the default setting only, so the world's 0.5 and 2 counts
    of area quests go stale from the day after a seed (28 values in Bremen at +30 days). Either the engine dates them
    at all three settings, or the world publishes the default setting only. The default is what the site shows.
  - **D merged (23:20):** `tilestore ways --store S [--gen G] --ids W.npy [--rels R.npy] --out DIR` (`ways.rs`): each
    way's refs and their places in a generation, through its way pairs, falling back to the relation store for the
    relations given; npy files out (`ids`, `how`, `offs`, `refs`, `lat7`, `lon7`). Exact against the 11-12 clip on
    99,889 ways (half of them relation members) and 1,000 absent ids; 1,000,000 ways in 18 s, 3.1 GiB.
    **Order it forces on the world day:** a generation's way pairs go at the next `update --prune-pairs`, so the old
    geometry (generation D-1) is looked up **before** the day's update; the new member ways of changed relations
    after it. The tile reads of D-1 need only its tile index, which lasts until `compact`.
  - **A merged (23:30):** `tools/stream/world_tier2.py` (the cover in one 50 m grid, vectorised; rectangles split at
    cells and merged per cell in parallel; the engine's cities, boundary and parts files; read-only `NodeFile`;
    `old_rows` from the seed files) and `tests/test_world_tier2.py` (13; the Europe day test is opt-in,
    `WORLD_TIER2_EUROPE=1`, about 11 min). On diff 5175 for europe-west with boxes uncapped, all 103,785 of tier 2's own
    cells lie inside its rectangles. **Planet day 5172:** 3.93M nodes, 690k ways, 37k relations changed; 10.0M cells
    marked; **52,128 rectangles, 217,299 km2 per date** (median 0.19 km2, 99th percentile 50 km2); about 12 min for the
    cover and the files. Outputs in `.scratch/world-tier2/5172/`.
    **The open problem for step 3: big closed ways and multipolygons.** Tier 2 marks a changed closed way's or
    multipolygon's whole box; on a planet day the largest box was 2.7M km2, and a 25 km2 cap (outline only above it)
    loses 69% of tier 2's cells on the Europe day. Proposed rule (Claude): read from the engine's area quests which
    polygons each one consults as a container (buildings for house numbers, malls for levels, and so on); a changed
    big polygon that no area quest reads as a container needs only its outline. That is exact by construction, not a
    cap. Not built; the next thing to build in step 3, with the relations' member ways through `tilestore ways`.
  - **E merged (23:55): the big-polygon rule** (DESIGN.md, "What tier 2 must recount, from the code"). Only buildings
    (AddIsAmenityIndoor), malls and stations (AddLevel, AddLevelThing) and addressed areas (AddHousenumber) read a
    polygon's inside; a changed ring gets its whole box only if it is such a container or its box is at most
    0.25 km2, else its outline and quest points. Found missing: `route=hiking` (the summit quests), addressed
    non-multipolygon relations, street relations' member nodes. And `merge_rects` grew strips across a polygon's
    inside (sum, not union): `merge_rects_overlap` in world_tier2. Europe day: every rule-justified cell of tier 2's
    covered. **Planet day 5172 with the rule: 128,544 rectangles, 101,651 km2 per date** (largest 52.5 km2), about
    9 min; the engine's per-rectangle cost goes up (about 30 min a date), the map data halves (`MERGE_SLACK_M2`).
    Four gaps left: old tags of changed rings, addresses on an outline, containers wider than 100 m, a changed member
    ring of a container multipolygon.
  - **Overnight, two agents (from 00:00):** F, one `tilestore` query for the four gaps (a way's tags, its tagged nodes,
    the relations holding it; the polygons containing a point) wired into the cover; G, `tools/stream/world_day.py`
    (one world day in the store's order) and its rehearsal on the Europe clip, 11-09 seed, days 11-10..11-14 each
    against a whole count (`.scratch/r1/eu/`), running its own engine build; no engine above 8 GB until
    `logs/storecut-filesize.log` says "filesize exit".
  - **Step 1's checks passed (00:41-01:02).** The store caught up to 11-16 (generation 14; 11 days; the 11-15 punch
    took 32 min, slowed by the agents' disk use). `storecheck_cities.py` on 11-16: **all four Europe regions equal row
    for row and city for city, store read against clip** (europe-west 6,845,829 rows, central 17,913,185, east
    4,054,829, msk 6,600,379; 0 different). File size (`.scratch/planet/storecut-test/cut/storecut.json`): f0, 93.6M
    nodes, read in 67 s, peak 20.8 GiB; f19, the widest box (760,744 tiles), 97 s, **peak 39.4 GiB** (long ways copied
    into many tiles): the read is fine for one file at a time, too big beside a 30 GB engine. A world read is about
    2.5 h for 128 files. **The merged engine is installed (e3a4e656):** place sets, `city:<id>` in each set, `e7`
    positions. Found by G: a notes-only engine run is 120 s of loading 63,353 part outlines and 0.2 s of counting;
    loading outlines needs to be faster for a million places.
  - **Agents F and G stopped at 01:15 on the 5-hour usage limit and were resumed at 08:12.** Nothing ran between.
  - **F merged (08:30):** `tilestore context` (`context.rs`): for one generation, ways (tags, refs, places, which refs
    carry `addr:*`, the relations holding them), relations (tags, members, member box), nodes (tags, the closed ways
    they are a vertex of), points (the closed ways and multipolygons whose ring holds them, in the 3x3 tiles around).
    No new index. Exact against the 11-12 clip on 62,968 ways, 15,341 relations, 57,340 nodes, 2,000 vertices and
    4,520 points. `tools/stream/store_context.py` `DayContext` asks it at D-1 before the update and at D after, and
    hands the cover its hooks. Europe day with the store: 0 rule-justified cells outside the rectangles; 55,631 km2
    against 61,200 without. Inside Europe on day 5172 it resolves every one of E's flagged cases. **Left:** a container
    wider than about 7 km around a point is not found (`--around` widens); `route=hiking` relations are not in the
    store, **and that is right: SC ignores every route relation but ferries on download (`ApplicationConstants.
    ignoreRelation`; `tilestore.py` `ignore_relation`, the engine's IgnoreRelation.kt), so the summit quests' relation
    branch never sees a hiking route in the app either; they read hiking paths (ways with `sac_scale`) only. E's
    "`route=hiking` is a gap" is not one: the cover's marking of hiking routes only adds area and can be dropped;
    the planet store's daily run must call `DayContext.before` before its update and `after` before `compact`.
  - **G merged (11:10): the world day runs end to end** (`tools/stream/world_day.py`: `prepare` before the store's
    update, `finish` after it and before `compact`; `world_europe_r1.py` the rehearsal driver; `tests/test_world_day.py`;
    engine: a rectangle city's place index clipped to the city, which fixed an out-of-memory at 28,703 rectangles;
    111 engine tests pass; installed). DESIGN.md, "The world day, rehearsed on the Europe clip".
    **Rehearsal on the Europe clip (16 files, 57 cells, 50.3M rows):** day 0 exact (0 of 36.8M groups, 0 of 631,304
    place counts). Days 11-10..11-13 against whole counts: at the default setting 15, 45, 66, 83 groups differ; the
    32 cities' own counts 1, 3, 7, 7 of 5,306 differ, each by 1 (Praha AddMaxHeight by 2). The rest is the 0.5 and 2
    settings (settled matches and area quests not dated there) and the clip's edge (the store keeps edge ways the
    clip drops), not the stream. 20-23 min a day here. **11-14 is pending:** its run was killed at a 2-hour limit
    before writing; restarted detached, it waits until 14:16 and writes `days/2026-11-14/check.json` in the worktree
    `.claude/worktrees/agent-abc2aa4490dae9ca7/.scratch/r1/eu/` (keep that worktree until it lands).
    **What still blocks the planet, in order:** (1) every engine run loads its place outlines (120 s of a notes run
    is loading, 0.2 s counting): a resident engine with places loaded, or note quests as rows; (2) hidden flags over
    every row in Python (170 s for 50M rows): by note position, or files in parallel; (3) two cover gaps, a relation's
    quest point when a member way changed (AddRoofShape on building multipolygons) and roads crossing a rectangle by
    their segments (AddMaxHeight under a changed bridge): add the elements whose geometry meets the marked cells, from
    the store; (4) 128,544 planet rectangles per date: group per plan file and measure; (5) the 0.5 and 2 settings:
    **decided by the owner (2026-11-17, afternoon): the world publishes the default resurvey setting only.** No engine
    work for the 0.5 and 2 dates; the world's counts and checks gate on the default setting; the cities' own
    snapshots keep all three settings as today.
  - **Three agents from 11:15 on blockers 1-3:** P1 cheap place-outline loading in the engine (binary cache or a
    resident engine), P2 hidden flags at planet size, P3 the two cover gaps. Blocker 4 (rectangle grouping) follows
    P3; blocker 5 is decided (default setting only).
  - **All three hit the usage limit at about 11:40 and were resumed at 12:02.**
  - **P2 merged (12:20): blocker 2 gone.** `notes_day.notes_table` (the clip parsed once in parallel, cached beside
    it), `open_keys`, `hidden_files` (a file opened only if a changed note falls in its box or it got rows that day;
    rows found by binary search; changed flags written in place; files in parallel). The rehearsal's 50.3M rows: 150 s
    to 3.6 s, byte-equal to the old path on all 16 files. Planet projection about 2 min with 8 workers. Not rerun:
    `notes_check.py`'s engine checks (the rule is unchanged and the new path matches it byte for byte).
  - **P1 merged (14:50): blocker 1 gone.** Engine `partcache` writes a world's part outlines into one file
    (`W/parts.cache`, stamped with the world's `places.json`); `--parts-cache` reads them into the same polygons.
    `world_cells.py partcache --out W` builds it; world_day, world_state.apply, notes_day.note_quests and
    world_cells count use it when current, and fall back to GeoJSON with a line on stderr when stale. Exact: 16 notes
    and 16 tier-1 runs of the rehearsal, Bremen's 628,119 rows with places; 112 engine tests pass on main,
    SnapshotReproductionTest included; installed. f0's parts 34 s to 1.8 s; notes for 16 files 233 s to 86 s, tier 1
    200 s to 79 s (warm). Planet: about a minute of loading plus about 8 min of JVM starts per pass. The cache is
    2.6 GB for Europe; the planet's is estimated at 10-15 GB. **Rebuild it whenever a world's places change.**
  - **Rehearsal day 11-14 checked (15:01):** 8 of 5,307 city counts differ; about 110 groups at the default setting
    (the same kinds as 11-10..11-13); all cells 30,013,907 against 30,012,738, the clip's edge included. So the
    default-setting residue grows about 20 groups a day before P3's fix. Keep G's worktree until P3 has rerun the days
    on copies of its state.
  - **P3 merged (17:30): blocker 3 gone.** `tilestore context` answers a relation's member ways, every way a node is a
    vertex of, and the ways with a tag crossing given segments; `store_context.py` and `world_tier2.py` mark relations
    holding a changed way, untouched ways whose node moved (both days), and one box from a road's quest point to its
    crossing with a changed bridge (or the reverse); `world_day.py` now calls F's store context (G's runner never did);
    quest points use the line's own latitude. 56 Python tests pass. **Rehearsal rerun (11-10..11-13), default setting:
    3, 4, 9, 9 groups differ (G: 15, 45, 66, 83); the 32 cities' counts 1, 1, 4, 4 of 5,306. It no longer grows.** Of
    11-13's 9: 5 are the rehearsal's `clip_keep` dropping relations changed by tags alone (not on the planet; keep the
    diff's relations the D-1 store holds if the rehearsal is rerun), 1 is the known AddHousenumber order effect, 3 not
    traced (relation 13409862 AddRoofShape and AddBuildingLevels; Moscow road 684910576 AddMaxHeight: inside a
    rectangle, the store holds the data, both recounts lack a quest the whole count has; next, an engine run on that
    day's read, `days/<D>/t2/new.osm.pbf` in P3's worktree). Planet day 5172's cover with the store's answers
    (Europe only): 128,796 rectangles, 102,475 km2. P3's rehearsal data is in
    `.claude/worktrees/agent-a9b152efd4c2e1246/.scratch/r1/eu/` (keep it for the three traces).
  - **Cleanup (18:10):** G's worktree (62.7 GB of rehearsal copies) removed, after first unlinking three junctions it
    held into main's `.scratch` (`overture`, `planet`, `world-places`) so the removal could not follow them; main's
    folders checked intact (128 world files). **Agents' worktrees can hold junctions into main's data: unlink them
    before `git worktree remove`.** C: 216 GB free. P3's worktree (28.6 GB, no links) stays for the three traces.
  - **Blocker 4, tier 2 per plan file (18:00-, Claude):** `world_day.rect_groups`/`rect_rows` (committed 9519f4d2):
    the rectangle cities split per plan file (cut further past `WORLD_T2_GROUP_KM2`), each group read from the store
    on its own, `WORLD_T2_WORKERS` engines at a time, ingested in group order. **Exact** on the rehearsal's 11-13
    (generation 4): 16 groups = one run, 5,668,905 rows, 0 different (`.scratch/rectgroups/exact.py`). Planet sizing
    (`size.py`, 5172-rule): 127 files, padded map data 289,864 km2 (2.85x the rectangles' area), f116 (north Norway,
    10,286 rectangles) 28,507 km2, median file 1,603. **Planet parts cache built:** `.scratch/planet/world-places/
    parts.cache`, 1,069,679 outlines, 5.8 GB, 870 s. **Measuring:** `.scratch/rectgroups/measure.py f116` (log
    `.scratch/rectgroups/planet.log`, results `planet/results.json`), from the planet store's generation 15 under a
    HOLD. **End to end (23:05): exact.** `.scratch/rectgroups/e2e.py`: the rehearsal's day 11-10 through `world_day.run`
    with grouping (16 groups, 4 workers, both reads) from P3's 11-09 seed, against P3's ungrouped 11-10: every state
    row equal (0 different), 628,364 of 628,364 counts per place and quest equal (log `logs/e2e-groups.log`, result
    `.scratch/r1/eu/e2e-check.json`). **Blocker 4 is done.** **Measured (18:44; one date, 5172's rule cover read from
    generation 15):** all 127 groups, one date, 4 engines at a time: 1,220 s wall time,
    reads 643 s (8.0 GB of map data), peak heap 6.7 GB, every group OK at 8 GB. **About 40 min of tier 2 a planet
    day** (DESIGN.md, "Tier 2 per plan file, measured on the planet"). Set `WORLD_T2_WORKERS=4` for planet days.
  - **Checked before the re-cut (19:00-19:10; the advisor's three):** the pinned `tilestore-recut1101.exe` (main's
    release build, b9f682fc) cut Germany through a dense node file equal to `store-rs-germany` (`gsmoke-recut.sh`,
    storecmp equal); its history reader at 2026-10-01 on Berlin's history equals osmium `time-filter` (9,305,598
    objects, 0 different); the script's flags are 11-16's. The Europe clip of 11-01 is pruned (a clip cannot go
    back), so the oracle is cut from the history file (below); the Europe clip is about 1.7 GB, so its history cut
    is a few GB.
  - **Step 2's history file (owner, 18:20): add a download to osm-extracts** (`fetch planet-history` cannot start
    without a file; the newest weekly dump is `history-261109.osm.pbf`, about 155 GB). Then delete the store, cut at
    11-01T00Z. Disk: 216 GB free now; the store is 292 GB, `.scratch/planet-day` 115 GB.
    **Built and running (18:35):** osm-extracts `fetch planet-history --download [YYMMDD]` (bd2137e: resumable
    from `planet/history-YYMMDD.osm.pbf.download`, MD5 against the published one, meta written; no diffs). Started
    hidden (pid 42016), log `logs/history-download.log` (a progress line every 10 min): `history-261109.osm.pbf`,
    153.3 GiB from the AWS mirror at about 25 MB/s; restarted at 19:19 on c5f399c (a cut-short body resumes; a
    minutely header's sequence is not taken for a daily one), log `logs/history-download2.log`, so it lands about
    20:05. **If it dies, run the same command again: it resumes.** The weekly planet task (kk-SCOpenQuests-planet,
    the only caller of `fetch planet-history` and `recut`) is **disabled**, so nothing scheduled touches the file. **Keep the file until the Europe polygon at 11-01T00Z is cut from it** (the seed's row-for-row oracle;
    no Europe clip of 11-01 exists, the oldest kept is 11-02). Not with osm-extracts `recut` (it would add an older
    dated file to the live Europe clip): with this repo's history tools, as `backfill_history.py` cuts regions.
  - **Step 2 under way (20:02-20:19):** download done (0.6 h, MD5 matches; header timestamp 2026-11-09T01:00:03Z,
    no replication feed named, writer planet-dump-ng 1.2.4). **Gate passed** in 739 s: at 11-01T00Z 10,974,021,977
    nodes, 1,228,807,341 ways, 15,045,483 relations, `notIncreasing` 0 (850 backwards timestamps in the whole file);
    the old file at 11-02 had 10,975,350,797 and 1,229,012,042. kk-SCOpenQuests-planetstore disabled; **the 11-17 store
    and its node file deleted at 20:19; `scut` at 11-01 running since 20:19** (476 GB free at its start).
  - **The store is at 11-01 (22:17):** `scut` 6,402 s (to 22:06), 32,109,393 tiles (11-02's cut: 32,110,824), pack
    232.59 GiB, 268 GB on disk, peak working set 66.5 GiB; node file `loc build` 686 s, 10,974,021,977 nodes (equal
    to the gate's count), 0 ids not increasing, holds 2026-11-01T00:00:00Z. 91 GB free. HOLD kept, the store task
    disabled (both until step 4). The oracle (Docker osmium over the history file) is running from 22:17; with the
    cut's memory peak over, engine runs beside it are fine (the e2e grouping check runs now).
  - **The 11-01 store checked against the oracle (23:13-23:20): it holds.** The oracle (`oracle-1101/europe-2026-11-01
    .osm.pbf`, 1.75 GB; its Europe history cut in 50 min, 7.9 GB) is made like a recut clip. `loc check`: 127,686,642
    nodes, 0 differ. `subcmp` at 2 km: 13,964 of 14,001 interior tiles the same (32 differ, 5 store-only); at 0.5 km
    58 not the same. These are exactly 11-16's numbers, and `why3.py` explains all 58 by the same four ways the clip lacks
    (153021227, 172152780, 1091714367, 1117929203), with none left. The engine refuses a file without a replication
    timestamp (`--today` or not), so `europe-2026-11-01.stamped.osm.pbf` is the oracle with osm-extracts' headers
    (`osmium cat --output-header`, sequence 5163).
  - **Step 3, the seed at 11-01, prepared (23:15).** `.scratch/planet/setup1101.py` made `.scratch/planet/world-1101`
    (the 11-08 world's plan, places, parts cache, each file's cities, bbox, parts and cells; **its `cities.json` points
    into `world-places`' cells, so `world-places` must stay**). Notes at 11-01 come from today's dump: the engine
    keeps the notes open at its clock from each note's whole history (`Notes.kt`, `created > asOf` skipped); notes
    hidden by moderators since 11-01 are not in it. `storecheck_cities.py --clip` (7190f4bd) holds a store against an
    oracle with the clock given to both runs. **Chain: `.scratch/planet/seed1101.sh`** (log `logs/seed1101.log`, start
    line in its header): storecheck against the stamped oracle (the seed goes on only if every region is EQUAL); then,
    **with `loccheck.ok` and storecheck equal, it deletes `history-261109.osm.pbf` and the oracle's Europe history**
    (the cut, about 75-80 GB, and the state, about 48 GB, do not fit beside them); storecut at 11-01, notes, count
    `--state` (canary f47, then two engines at 30 GB, a failed file at 40 GB), the cut deleted, `world_state seed`,
    `counts --clock 2026-11-01`, `report --archive 2026-11-01`. **The report is not the gate:** the published 11-01
    snapshots are v64.0 and the seed counts v64.1. The like-for-like gate, to run after: the world's `osm-<city>`
    counts against storecheck's `clip` snapshots for the 32 cities (`.scratch/storecheck/1101/<region>/clip`).
    **Canary passed (23:17-23:26):** f47 store read 23 s (0.52 GiB), notes clipped from `planet-notes-261117` (129
    clips), count `--state` 69 s at 30 GB: clock 2026-11-01T00:00:00Z, 13,422 outlines from the parts cache (0 parsed),
    `.places` written, area dates in every cell (f47c1: 160 candidates, 160 dated; the 11-08 world's log has none),
    18,602,511 rows (the 11-08 world's f47: 18,633,926). **`seed1101.sh` running since 23:27.**
    **Storecheck against the oracle (23:27-23:37): all four Europe regions EQUAL**, city for city and row for row
    (`.scratch/storecheck/1101.log`; the cities' clip snapshots under `.scratch/storecheck/1101/<region>/clip` are the
    seed's gate later). Then `history-261109.osm.pbf` and the oracle's Europe history were deleted (222 GB free); the
    oracle clip itself (1.75 GB, both copies) stays. storecut started 23:37.
  - **Step 3, the seed at 11-01: built (23:27-03:49; `logs/seed1101.log`).** storecut 128 files 23:37-00:23; notes
    00:23-00:27; count `--state` 8,564 s, two engines at 30 GB (it waited for memory near the end, one engine at a
    time); cut deleted; `world_state seed`: **2,009,244,544 rows, 1,078,189 place sets, 1,020,138 places** (3,239 s);
    counts at 11-01: 27,680,263 (place, quest) pairs (294 s); report 1,016,874 of 1,069,532 places numbered. 110 GB
    free at the end. **Report against the published 11-01 snapshots (context, not the gate):** 147 cities, median
    |diff| 0.017%, 90th percentile 0.11%, worst Fredericton +0.79% (Canada's and Germany's snapshots are as of
    21:21Z, and v64.0 against v64.1).
  - **The seed's like-for-like gate (09:40, `.scratch/planet/gate1101.py`, `world-1101/gate1101.json`):** the world's
    `osm-<city>` counts against the engine on the 11-01 oracle for the 32 European cities, default-setting measures.
    **The seed's `world_state counts` has no note quests** (the day's `counts_at` adds them; the seed path never
    did). Without them: 21 of 32 cities equal in every quest and measure; the other 11 differ by 1-4 in one to three
    quests (AddHousenumber in 8, Athens' AddMaxSpeed/AddRoadSmoothness/AddRoadWidth +1 each, Bratislava AddCycleway
    +4 and AddBarrierOnRoad -1, Helsinki AddMaxHeight +2, Kobenhavn AddCrossing -1); in all 19 open quests of
    19,235,901 (0.0001%), far inside the 0.1% bar. Not traced: cells against a whole city (the world counts each city
    as cells; the clip run counts it whole). **With the note quests (09:45-09:55):** `.scratch/planet/notes1101.py` ran `world_day.counts_at` on
    the seed (578 s, 128 notes-only engine runs; `W/counts/2026-11-01/`, the counts a world day writes): note quests
    equal in all 32 cities; open quests 19,239,755 in the world against 19,239,746 on the clip (+9); 21 of 32 cities
    equal in every quest and measure, the same 11 small differences as above. **Step 3 is done: the seed at 11-01 is
    `.scratch/planet/world-1101` (counts per place in `counts/2026-11-01/`).** Next, step 4: a planet driver for the
    world day (`world_day.prepare` before the store's update, `finish` after it, inside `planet_store_day.py`'s run;
    `WORLD_T2_WORKERS=4`), its first day diff 5164 (11-01 to 11-02, in `.scratch/planet/diffs-keep`) checked against
    `europe-2026-11-02` (pinned) as storecheck does; the store's HOLD and the disabled task stay until it exists.
    Worth tracing before the loop runs a month: the 11 cell-against-city differences (one or two cities, e.g.
    Bratislava's AddCycleway +4).
  - **Step 4, the world-day loop: built (11-18, 10:00-11:20; 0c8e8d63), day 11-02 running since 11:21** (`--max-days 1`,
    detached; `logs/planet-store.log`, stdout in `logs/planet-store.out`). `planet_store_day.py` now moves the world
    (`.scratch/planet/world-1101`) with the store; there is no flag to move the store alone. Per day D: the world's
    `world.bin` files hard-linked into `.scratch/planet-day/world-days/<D>/before/` (0 s; every world write replaces
    a file, and `notes_day._hidden_file` now copies a linked file before setting flags), `prepare`, the prepared day
    saved as `day.pkl` and read back (the update takes D-1's way pairs: `prepare` cannot run twice), `update`,
    `finish`, **the gate** (`tools/stream/world_gate.py`: the 32 cities' `osm-<city>` counts against the engine on
    `europe-D` with the same quests and the world's own notes dump, clipped once into `W/gate-notes/`; bar 0.1% in
    total and per city), then `loc advance`, `loc check`, subcmp/why, `compact`, `punch`, D's clip unpinned, the
    day's work deleted (`day.json`, `gate.json` kept in `W/days/<D>/`). Every Europe clip past the world's clock is
    pinned on sight. **Resume:** store at D, node file at D-1: the world put back from `before/` and `finish` rerun
    from `day.pkl`, or on from the gate if `finished` is there. A failed gate stops; to accept a day by hand, set
    `"ok": true` in its `gate/gate.json` and remove STOPPED. Also in 0c8e8d63: tier 2's delta compares groups by
    fingerprint (34M rows in 6 s; the per-row Python dict would have been minutes and GBs on a planet day), and
    tier 1's and the note quests' 128 engine runs go `WORLD_T2_WORKERS` (4) at a time, ingested in file order.
    **Day 11-02 so far:** prepare 525 s (diff read 89, old ways 90, rows 94, store context 215; `day.pkl` 665 MB),
    update 620 s (11:30-11:40): **the store is at 11-02, generation 1; no way back.** `finish` read the day back
    and waits out the daily run's window (to 14:15). If the run dies from here, rerun the same command: it resumes.
    **Stuck 14:21-15:41 in `store_context.crossing_box`** (every changed road against every bridge in Python: 115,667
    roads x 8,260 bridges on 11-02); stopped by hand, fixed with a box prefilter (981d284a: hooks 11 s, 0 of 2,000
    sampled roads differ). The day's cover then took 107 s (12,656,909 cells; 548,092 extra lines, 64,099 container
    boxes from the store context). **Resumed 15:53** by the same command: the resume path put back 0 files (the stop
    came before tier 1) and reran `finish` from `day.pkl`. Tier 1 16:00-16:18 (517,095 rows dropped, 775,989 added);
    tier 2 16:18-18:08: 181,341 rectangles (181,886 km2), 128 groups, 8.4 GB map data a date, engines 1 h 40 min,
    recount rows 49.0M / 49.2M, the delta 10 min (its "added, the state had it" 240,481 of 289,723 is the
    rehearsal's ratio too). **Disk:** C: fell to 31 GB free during the day (the D-1 links hold about 56 GB until
    the day ends); the seed's dumps `files/*/state.bin*` (56 GB) were deleted at the owner's word (18:15): 83 GB free.
    Counts are now written compressed (8bd4e23b; 11-02's is still 2.2 GB raw).
    **The gate for 11-02 passed (18:23):** 21 of 32 cities equal in every quest and measure, open 19,243,558 against
    19,243,549 on the clip (+9), worst city 0.0016%: **the same 11 cities with the same differences as the seed**, so
    the first streamed planet day added nothing of its own. `finish` 8,703 s (tier 2 engines 4,742, tier 2 reads
    1,251, tier 1 812, delta 589, counts and note quests 503, engine files 304, store context 415, notes 118, cover
    70); `loc check` 0 of 127,715,680 nodes differ. A day is about 3 hours end to end, plus the daily window's wait
    (11:55-14:15) when it falls inside one. `punch` after the first day took over 20 min (one thread over the 250 GB
    pack). **RUNNING now carries the pid** and a run refuses to start beside a live one: the scheduled task kills a run
    after 6 h, so a catch-up is started by hand and the task can stay enabled beside it.
    **The first punch after the cut was slow again (18:25-19:48):** hash before 233 GB, then 15,654 dead ranges
    (3.70 GiB) to zero at about 0.5 s a call, the same rate as 11-16's first punch, although no tile-store command maps a
    pack now (the 11-17 daily punch took 1.7 s). Stopped by hand after about 9,700 ranges (STOPPED was mine and
    removed). **`punch` now runs only when the store's disk has under 100 GiB free** (521838d9); about 6,000 ranges,
    roughly 1.5 GiB, are left for a later punch. Cause not understood: a first punch on a freshly cut pack.
    **The catch-up runs since 19:48** (`--max-days 20`, by hand, pid in RUNNING): 11-02's store checks again
    (without the punch), then 11-03 to 11-18, about 3 h a day, so into 11-20 or 11-21; 11-18 cuts the 261118 notes
    dump into the world first. **`kk-SCOpenQuests-planetstore` re-enabled by the owner (11-18 evening)**, next run
    11-19 14:45; it steps aside while a live run holds RUNNING and takes over once the catch-up ends.
    **11-02 done 20:49:** subcmp 13,964 same, 32 differ, 5 only planet, all 37 explained by the usual four ways; the
    disk was at 84 GiB (D-1's links still held) so the punch ran after all and finished the rest: 5,991 ranges in
    2,990 s, every live tile the same, +13 GiB. C: 165 GB free after the day. 11-03 started 20:49.
    **11-03's gate passed (01:28):** the same 11 cities, the same differences, +9 of 19,248,190. `finish` 15,032 s:
    tier 2 had 352,597 rectangles (357,771 km2, twice 11-02's; 142 boxes over the 5,000 km2 cap drawn by outline),
    its engines 9,693 s, recount rows 62.5M / 62.8M. **Days run 3 to 5 h**, so the catch-up to 11-18 ends about
    11-21 or 11-22. Tier 2's engines are the cost to cut after release 1 (4 workers already use every core).
    **The daily punch is slow too (11-19, 01:31-03:31):** about 16,600 ranges in 2 h at 2-4 calls a second (the 100 GiB
    test ran while D-1's links still held 56 GB, so it fired every day). Stopped by hand (STOPPED mine, removed);
    **the punch is now decided after the day's work is deleted, under 60 GiB free** (c9ceb761): 11-03 closed at 03:38
    with 158 GiB free, punch skipped. The 0.5 s a call is not only a first-punch effect; open, for after release 1
    (`DESIGN.md`, "Why the punch was slow": a mapping of pack-0000 was the cause then; check whether `subcmp.py` or
    `why.py`, which read the store in Python just before, map it). Dead ranges pile up until a punch runs.
    11-04 started 03:38; **its gate passed (08:16)**, the same 11 cities, +9 of 19,252,865; `finish` 14,930 s (tier 2
    engines 10,287). Gates so far: 11-01 (seed), 11-02, 11-03, 11-04, each +9 with the same differences.
    **11-05's gate passed (16:37) with a first new difference:** 20 of 32 equal, +10; Zagreb AddHousenumber +1 (a way:
    17,958 against 17,957). Inside the bar; to trace if such rows pile up (the rehearsal left AddHousenumber rows of
    the same kind, DESIGN "The one tier-2 row left, traced"). `finish` 27,945 s, of which about 2 h 20 min the daily
    window's pause and tier 2's engines 22,986 s (one group alone 2,616 s). **11-06 passed (21:50)**, unchanged: 20 of
    32, +10 (Zagreb's +1 stays, no new one); `finish` 16,461 s. **11-07 passed (02:58 on 11-20)**, unchanged: 20 of
    32, +10 (clip 19,261,639, world 19,261,649), the same 12 cities and quests differing, no new one; `finish`
    16,392 s (tier 2's engines 11,429 s). **11-08 passed (06:54)**, unchanged: 20 of 32, +10 (clip 19,264,474,
    world 19,264,484), the same 12 cities and quests; `finish` 12,132 s (tier 2's engines 7,205 s). **11-09 passed (11:59)**, unchanged:
    20 of 32, +10 (clip 19,265,954, world 19,265,964), the same 12 cities and quests; `finish` 16,145 s (tier 2's
    engines 10,816 s; the log was silent 09:59-11:54 through them). **11-10 passed (19:01)**, unchanged: 20 of 32,
    +10 (clip 19,270,040, world 19,270,050), the same 12 cities and quests; `finish` 16,099 s (tier 2's engines
    10,878 s), but the day took 7 h wall clock (12:05-19:08), the slowest yet. 11-11 started 19:08.
    **11-11 passed (23:28)**: 20 of 32, +14 (clip 19,273,494, world 19,273,508): the same 15 rows plus one new,
    Sofia MarkCompletedHighwayConstruction +4 (87 against 91), gone again the next day; `finish` about 14,500 s
    (tier 2's engines 9,110 s). **11-12 passed (03:50 on 11-21)**: 20 of 32, +11 (clip 19,277,776, world
    19,277,787), the 15 rows of 11-10 with London AddHousenumber −3 now −2; tier 2's engines 7,365 s. **11-13 passed
    (10:41)**, unchanged from 11-12: 20 of 32, +11 (clip 19,282,742, world 19,282,753); tier 2's engines 16,426 s,
    the day 03:56-10:52. 11-14 started 10:52 (pid 60100 alive, 142 GiB free, punch skipped every day). Five days
    left to 11-18, at 4-7 h a day: caught up about 11-22 evening.
    **The daily city run failed again on 11-20 at 12:15**: `osm_extracts.py fetch ontario` got HTTP 404 from
    Geofabrik. Two days missed (the newest Canadian snapshot is 11-17, Europe's 11-18). Not touched.
    **The scheduled task at 14:45 on 11-19 exited 1 with no output:** the catch-up started by hand writes to the same
    `logs/planet-store.out`, and the task's `cmd /c ... >> planet-store.out` cannot open it while that run holds it, so
    the task never reached Python (it stepped aside, but not through the RUNNING guard). Harmless; once the catch-up
    ends the task runs normally. **Start future runs by hand with their own output file.**
    **The daily city run failed on 11-19 at 12:20** (`logs/scheduler.log`): `osm_extracts.py fetch quebec` hit a read
    timeout from Geofabrik, so no city snapshot that day. Not touched; the next run (11-20 13:15) should catch up.
    **The gate on the seed (11:15-11:21):** `world_gate.py` on the 11-01 oracle reproduces `gate1101`: 21 of 32
    equal, +9 of 19,239,746, worst city 0.0016% (`world-1101/gate-test/`). The recut's stale HOLD was removed at launch.
    **Notes past the world's dump (11-18, 11:40):** when D passes the clips' `until` (261117: 11-17T05:37Z, so first
    at 11-18), the driver cuts the newest dump into every plan file (`world_day.refresh_notes`, one `clip_notes`
    pass over the files' `bbox.poly`), rebuilds `notes-all.jsonl`, drops `gate-notes/`, and keeps the old union clip
    as `notes-prev.jsonl` for that day's D-1 side of the hidden flags (`hidden_files(prev_table=)`: a note the newer
    dump lacks still counts as open at D-1, so its rows are unhidden at D); removed when the day is done. No newer
    dump yet: "done for now", not a stop. **Also not yet:** the task `kk-SCOpenQuests-planetstore`
    stays disabled until 11-02 passes; `files/*/state.bin*` (56 GB, the seed's dumps) is the disk reserve, to delete
    once the store has moved past 11-01 (it cannot go back, so they can only reseed a world no store matches).
  - **Step 2's script: `.scratch/planet-cut/recut1101.sh`, running since 19:22** (log `logs/recut1101.log`; start line in its header, **one quoted `-c "..."` argument: `-ArgumentList '-c','...'` starts a bash that does nothing**;
    every step skips what is done). It waits until `history-261109.osm.pbf` and its meta exist (MD5 matched), **then a gate:
    `tilestore at` over the whole file at 11-01T00Z (about 30 min) must give `notIncreasing` 0 and nodes and ways within
    0.2% of the old file's at 11-02, or it stops with nothing deleted** (`recut1101.gate.log`); then it writes HOLD, waits out RUNNING, disables kk-SCOpenQuests-planetstore, **deletes `.scratch/planet-cut/store` (11-17,
    generation 15) and `.scratch/planet-day/planet.loc`**, runs `scut --at 2026-11-01T00:00:00Z --day 2026-11-01
    --nodes` (the flags of 11-16's cut, binary pinned as `tilestore-recut1101.exe`), deletes the cut's node file,
    then `loc build --at` the same instant. **Between the delete and "scut done" there is no store.** A stop at the
    disk floor (exit 101) leaves `store/work` and `cut-1101.nodes`: delete both, rerun. 11-16's cut: 6,136 s, peak
    working set 70 GiB, about 287 GiB of disk at the peak: **no engines or large writes beside it.** **Then the 11-01
    oracle, automated:** the Europe clip made from the history file as osm-extracts makes a clip on a recut (Docker
    osmium: `extract --with-history -s complete_ways` to `europe/ring.geojson`, `time-filter`, `extract -s smart` to
    the polygon) into `.scratch/planet-cut/oracle-1101/`, then `loc check` and `subcmp --gp 0` at 2 and 0.5 km
    against the new store. Expected timeline: gate about 20:35, delete about 20:40, cut to about 22:30, node file
    about 22:50, oracle hours after (one osmium pass over 153 GB through Docker's mount). **No engines or large
    writes on C: until `logs/recut1101.log` says "recut1101 ended".** After it: one rehearsal day through `finish`
    (grouping has not run end to end; ready: `.scratch/rectgroups/e2e.py setup`, `day`, `check`: P3's 11-09 seed
    rebuilt in main's `.scratch/r1/eu/`, day 11-10 at 4 workers, every row and count against P3's ungrouped 11-10;
    G's whole-count oracle went with G's worktree), then the seed at 11-01 (step 3), checked against the oracle and every
    region's published 11-01 snapshots; the store's first day (diff 5164, hard-linked in
    `.scratch/planet/diffs-keep`) checked by the loop against `europe-2026-11-02`. `europe-2026-11-17` pinned.
  - **Line endings on disk (23:10, skill kk-line-endings):** the repo already says LF (`.gitattributes`, `.vscode`,
    CLAUDE.md); `rewrite.py --apply` rewrote the 5,452 tracked files still CRLF in main's checkout (only
    `engine/gradlew.bat` stays CRLF, by its rule); 207 Python tests pass. `cloud_publish.py check` compares local
    `docs/` bytes with the site: a file last deployed as CRLF reads as different until the next publish uploads it.
