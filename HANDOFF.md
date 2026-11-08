# Handoff: StreetComplete open-quest statistics per city

## Goal
Build a public website that graphs **open StreetComplete quests per city over time, broken down by quest type**. As far as we know, nothing like it exists. jmizv's sc-quest-stats on Codeberg is a static, single-city Markdown snapshot. Pilot city: **Toronto**.

## What the site should answer
- How many quests of each type are open in city X right now?
- How has that changed over time? Which types are being solved, which are piling up?
- How do cities compare, normalized so size doesn't dominate?
- Where in the city is a given quest type concentrated? (stretch goal: map/heatmap)

## High-level goals
1. **Reuse StreetComplete's own quest definitions.** Don't hand-write Overpass queries. Most quest types declare an element filter string in their Kotlin source (`streetcomplete/StreetComplete`, `quests/**`). Extract and parse those so the tool stays in sync with app releases. Pin the app version used for each data run.
2. **Be honest about coverage.** Some quests aren't pure tag filters: resurvey intervals based on `check_date` age, country-specific enablement, geometry or nearby-feature checks. Classify each quest type as *supported*, *approximated* or *unsupported*, and show that classification on the site.
3. **Daily snapshot pipeline.** Pull a regional extract (Geofabrik Ontario to start), evaluate the filters, count per city boundary (`admin_level=8` or equivalent) per quest type, and append to a time-series store. The pipeline must be idempotent and cheap enough to run on a schedule.
4. **Normalize.** Store raw counts plus denominators (km of road, element counts) so cities can be compared fairly.
5. **Separate the "aging" signal from the "mapping" signal.** Resurvey quests reopen without any edit. Track them separately so the graphs don't mislead.
6. **Simple static frontend.** Charts per city and per quest type, with a city selector and a quest-type filter. Static hosting is preferred: generate JSON and serve from GitHub Pages or similar.
7. **Designed to scale out.** Adding a city or region should be configuration, not code.

## Non-goals (for now)
- Counting *solved* quests from changesets (possible later via the `StreetComplete:quest_type` changeset tag)
- Per-user stats or leaderboards
- Real-time updates

## Suggested first milestone
Toronto only, about 10 common quest types whose filters are simple, a few weeks of daily snapshots, and one chart page. Then extend to the full quest list and more Ontario cities.

## Context
- Owner is an experienced OSM contributor with existing Toronto/Ontario OSM tooling in sibling folders (e.g. ../toronto-streets-layer, ../toronto-addresses-layer, ../toronto-buildings-3d, ../osm-mayflies). Reuse conventions (Python + .venv, README/DESIGN/PRIOR-ART docs) and boundary data where it makes sense.
- Open questions for the owner: preferred stack (Python/osmium vs PostGIS vs Java), hosting, and whether to coordinate with jmizv or the StreetComplete developers early.

## Corrections (2026-10-11)
- "Nothing like it exists" is too strong: **starsep/StreetCompleteStats** publishes solved/all per quest per
  Polish city daily (25 quests, bounding boxes, no history on the site). See PRIOR-ART.md.
- jmizv's queries are not tied to one city, and its QUESTS.md has a "Pending" (open) column.
- Toronto is **admin_level 6** (relation 324211), not 8. Configure cities by relation id.

## Status and next steps (2026-10-13)

Milestone 1 is done and the site is live at https://skfd.github.io/sc-open-quests/. It covers every
Canadian municipality over 50,000 people (111 cities in nine provinces) and Germany's city-states, and all
quest types of SC v64.0 that the app offers there, monthly from 2017-01 and daily since 2026-10.
`kk-SCOpenQuests` runs daily at 13:15. Design and known gaps are in DESIGN.md.

**Repinned to SC v64.0 on 2026-10-21** (DESIGN.md, "Repin to StreetComplete v64.0"; the routine is
REPIN.md). 193 quest types, all counted and oracle-checked (Guelph and Bremerhaven). Merged into main
the same evening, after the Canada work below; the newest extract of every region was recounted with
v64.0 at once, and the overnight job recounts the rest. From then on the scheduled update's last step
opens a GitHub issue "Repin to StreetComplete vX.Y" when the app moves on.

**Canada joined on 2026-10-21** (DESIGN.md, "Regions: the rest of Canada"): 63 cities, every
municipality over 50,000 in the 2021 census that was not yet counted, in eight new regions (Quebec,
British Columbia, Alberta, Saskatchewan, Manitoba, New Brunswick, Nova Scotia, Newfoundland and
Labrador, one Geofabrik extract each) plus the five Ontario ones the farmland list lacked. Their monthly
history is counted overnight by `.scratch/canada-backfill.sh` (started 21:05 on 2026-10-21; its output
went to a hidden console, not to `logs/canada-backfill.log`, so read progress from
`data/backfill/<region>/snapshots/`, oldest region Quebec first, Ontario's and Germany's recounts in
`data/backfill/<region>/recount/`; a rerun writes the log: `bash .scratch/canada-backfill.sh >
logs/canada-backfill.log 2>&1 &`), which
also recounts Ontario's and Germany's published snapshots with v64.0, merges, rebuilds the history and
commits "data 2017-01-01 to 2026-10-01: monthly history of the Canadian cities outside Ontario; ..."
locally; the next scheduled run pushes it. It runs about a day (a Quebec month about 2 min, an Ontario
recount about 5 min, 117 months each) and pauses around the 13:15 slot. Check that commit exists and
that Montreal's and Vancouver's lines reach back to 2017; if the log ends in an error, rerun the script
(every step skips what is done). The territories are not counted: Whitehorse (28k), Yellowknife (20k)
and Iqaluit (7k) are under the bar, and Nunavut's extract alone is 1.4 GB.

**Germany's city-states joined on 2026-10-13** (DESIGN.md, "Regions"): Berlin, Hamburg, Bremen and
Bremerhaven, because Ontario's totals barely move and Germany is where SC is used most. Each region is a
Geofabrik extract (`config/regions.json`); the daily run counts all four regions. Their monthly history
was counted that evening by `.scratch/germany-backfill.sh` (log: `logs/germany-backfill.log`, about 45 s
a Berlin month); it commits "data 2017-01-01 to 2026-10-01: monthly history of Berlin, …" locally and the
next scheduled run pushes it. Check that commit exists and the German lines go down; if the log ends in an
error, rerun the script (every step skips what is done).

Next, in order:
1. **Check the first scheduled runs.** A run on 2026-10-12 00:50 committed and pushed "data 2026-10-11"
   (`logs/scheduler.log`). The 13:15 slot fired on its own on 2026-10-12 (no new extract, exit 0); still
   watch the first one that counts a new extract per city (about 4 minutes).
   **Since notes (2026-10-12), day D is counted only with the notes dump of D+1**, and the S3 mirror
   the dump redirects to lagged it by more than 14 hours (261012 made ~04:30 UTC, still 404 at 19:10
   UTC). At 13:15 (17:15 UTC) that dump is probably not there yet, so data for day D lands on D+2. Watch
   the first runs (`logs/scheduler.log`: "no notes dump reaches ..."); if it is always a day behind, add
   a second, evening slot. A run raises once an extract has waited 3 days.
2. **Custom quests are done.** All 51 (52 since v64.0) are counted and checked exactly against SC (engine/README.md,
   "Custom quests" and "Area quests"; the last three use SC's country metadata per position). Left:
   - the note quest. Done 2026-10-12 (DESIGN.md, "Notes"), with the hiding below.
   The area unit is the whole city since 2026-10-12 (DESIGN.md, "Area unit").
3. **Deeper history: published 2026-10-13** ("data 2017-01-01 to 2026-10-10"). The site has 123
   snapshots per city: the 1st of every month 2017-01 to 2026-10 from the planet history
   (`tools/backfill_history.py`, DESIGN.md "Monthly history"), plus the dailies, all with notes and all 51
   custom quests. The final pass (log: `logs/backfill-final.log`) took about 4.5 minutes a month, not 2,
   and ran 04:00 to 11:02. It also stored the resurvey settings 0.5 and 2, "show all notes" and the z14
   tile grids (`data/grid/`); DESIGN.md, "Resurvey settings…". `data/backfill/` can be pruned of the
   superseded `nonotes/` and `notes-only/` passes and the slice .pbf files.
   The published 2026-10-11 lacks notes, so the chart shows a break there; `run.py` recounts it from its
   stored extract once a notes dump reaches it.
   Toronto's AddHousenumber went public with its two steps: +293k from 2019-01 to 2019-02 and −277k
   from 2026-05 to 2026-06. Neither is a counting error. The 2026 drop is the owner's own Toronto
   address import (confirmed 2026-10-13); the 2019 rise looks like a building import, unconfirmed.
   Worth a note on the site.
4. **Outreach.** Now that there is something to show, contact starsep (StreetCompleteStats), the SC devs and jmizv.
5. **Site, 2026-10-21:** the reader ticks the quests that count towards the totals and pins quests
   to chart them; the "off by default" checkbox is gone; the whole view lives in the query string so a
   link reproduces it across app releases (DESIGN.md, "Selection, pins and the link"). Drive-through
   check: `.scratch/drive.py` is not kept; `tests/fixtures/screenshot.py` takes the query now.
6. **Smaller items:**
   - ~~Model open OSM notes, since the app hides quests at a note's position.~~ Done 2026-10-12.
   - ~~Write down the routine for SC version bumps.~~ Done 2026-10-21: REPIN.md, used for v64.0.
   - ~~Make the site look like StreetComplete; show app releases on the timeline.~~ Done 2026-10-13
     (DESIGN.md, "Site look").
   - Heatmap per quest type (stretch goal).

## Planet coverage (asked 2026-10-24)

The owner asked for planet coverage. The measurements are in DESIGN.md, "Planet coverage: what was
measured". **The owner chose a direction the same evening** (DESIGN.md, "Planet coverage: the owner's
direction"): the site is for players; every place on Earth gets a name, and only places the community
asks for get counted; Wandrer.earth's nested regions are the model, down to neighbourhoods inside a
city; cities keep today's population bar for now. Next is a new session that explores that breakdown,
including whether Wandrer's regions can be the data source. History is monthly since 2017 and the world is
counted weekly from one planet file (DESIGN.md, same section); disk is the owner's, later. Still open:
whether land outside cities counts. Independent of the answer: GitHub Pages' 1 GB cap is about nine
months away at today's size, so the publish format has to change anyway.

**Done by the measuring session (2026-10-24 evening), all independent of how places are named; merged on
main, not pushed (the 13:15 run pushes it):**
the publish format for the Pages cap (newest snapshot per region in `docs/`, the archive outside it, a
small per-quest compare file; done on its branch, DESIGN.md "Publish format: newest snapshot only"); every SC country_metadata file bundled and a missing one an error; a
region's extract separate from its id, so several runs can share one extract; the notes clip in one
pass for many polygons; Unicode-safe city ids; and whether `osmium apply-changes --with-history` can keep
the planet history file current. Not taken: the place breakdown, the city list, any planet download.
For the breakdown session: sub-city counts (neighbourhoods) should sum quest positions inside the
city's run (the z14 grid or finer), not run neighbourhoods as small cities; a smaller map data changes
the area quests' counts (DESIGN.md, "Area unit: the whole city").

**The breakdown session's proposal (2026-10-24, late evening):** DESIGN.md, "Places: naming the world,
counting on request". Wandrer.earth cannot be the source (no API, all rights reserved) but is the model;
names come from Overture Maps `divisions` (ODbL, one world hierarchy, OSM relation per feature); counts
stay on OSM geometry; neighbourhoods are sub-places counted by position inside their city's run;
regions and countries are roll-ups labelled "N of M counted". The owner's answers and the Overture spike's result are in the same section: 113 of
our 115 cities found by relation, 1.08M named places with a polygon worldwide, about 175 MB as a name layer.
Built the same night on three agent branches, merged only on 2026-10-28 (below).

Merged and checked the same night: the publish format (docs/ 333 MB to 20 MB; 1,497 files moved into
`data/archive/`, which is not backed up), the engine (515 country files, no city cap, Ontario recount
identical, SnapshotReproductionTest fixed to take Ontario's own notes clip), shared extracts and the
one-pass notes clip (Bremen and Berlin recounted with the new clip: no quest moves, only `notes.open`).
A rehearsal of `backfill` and `history` skipped all 67 stored extracts and changed no file. Watch the
first 13:15 run after it (`logs/scheduler.log`): its push carries the 1,473 snapshot deletions.
Planet source: the owner chose the history file kept current with weekly diffs and is preparing
about 165 GB of disk (DESIGN.md, "Planet history kept current with diffs"); and the place list, which is
the breakdown session's. Optional: the engine's `-Xmx40g` could be about 20 GB (Ontario runs in 16).

**Archive backup (2026-10-24, night):** `data/archive/` (1,497 files, 306 MB) is copied to
`.backup/archive-2026-10-24/` (gitignored, checksums identical). Same disk, so it guards against a bad
run or a wrong delete, not a dead disk. **Delete it once the first 13:15 run with the new publish format
has gone well** (2026-10-25: `logs/scheduler.log` ends in "update done", the push with the 1,473
snapshot deletions went through, the site still loads every city, and `data/archive/` still holds 1,497+
files): `rm -rf .backup/archive-2026-10-24`. **Deleted by the owner on 2026-10-28**, the conditions met.


**Weekly planet job (2026-10-24, night):** `python run.py weekly` and `"cadence": "weekly"` per region
(DESIGN.md, "Weekly planet job"). No region is weekly yet, so it only runs `osm-extracts fetch
planet-history`. To do at merge: register it with `.\schedule-weekly-add.ps1` (Mondays 07:30) once
osm-extracts has `fetch planet-history`; until then the weekly run logs the failed fetch and stops.
**2026-10-28:** osm-extracts has `fetch planet-history` now (bd9dfb9), and the store holds
`planet/history-261005.osm.pbf` (163 GB). Not registered yet: C: has about 101 GB free and an update
writes a second file of that size beside the first, so the owner's disk comes first.

**Places merged (2026-10-28).** The breakdown session built the name layer, the parts and the site's
place pages on 2026-10-24 on three agent branches and never merged them; nothing in this file said so.
Merged into main as they were, then:
- the name layer rebuilt (`tools/places.py build`, same Overture pull) so the 4,217 counted parts carry
  their `"<city>/<placeId>"` mark; no other field moved. `docs/places/`: 4,202 files, 93 MB raw, 33 MB
  gzip, LF pinned in `.gitattributes`. DESIGN.md asked for "well under 100 MB": it is under, not well.
- two site bugs from building against a fixture: the real index has `"cc": "CA"` where the fixture had
  `"ca"`, so a typed `?in=ca/...` link found nothing; and a stray "null" under a short children list.
- checked: 91 pytest, every engine test (PartsTest, SnapshotReproductionTest, ManyCitiesTest); Bremen
  recounted with `--parts`: snapshot, quests.json and grid identical outside `parts`; `run.py history`
  adds `docs/data/parts/` (81 files) and changes nothing else; in the browser, Canada (3,526 of 12,208
  counted), Germany (806 of 40,520), Toronto's parts, a part page, and Blind River's request link.
- **What the 13:15 run changes:** every newly counted snapshot gets `cities.<id>.parts`. Bremen's
  snapshot goes from 45 KB to 307 KB; across 4,217 parts roughly 7 MB more raw JSON a day in the
  published newest snapshots (git delta-compresses them, so watch `.git` rather than guess).
  Until then a part page says its numbers arrive with the city's next count. Ontario with its 790
  parts was measured at 216 s and 21.9 GB peak heap (208 s, 20.1 GB without; engine/README.md).
- Left: five cities have a part named as the city (Bremen r2088648 holds 3,242 of the city's 3,251
  AddHousenumber; Halifax, Gatineau, Fredericton, Saint John): near-duplicates, worth dropping in
  `add_parts.py` when a part covers nearly all its city. The issue form goes live with the push.

**World building started (2026-10-29 evening).** The owner freed disk: C: has 338 GB free.
- `kk-SCOpenQuests-weekly` is registered, **monthly since 2026-10-30**: first Monday of each month,
  07:30, `logs/weekly.log` (DESIGN.md, "Planet job: monthly while nothing counts from it"). Its first run,
  2026-11-02, has only four diffs but still rewrites the whole file.
  **To do: rename "weekly" to "monthly" (or "planet")** wherever it names this job: the task
  `kk-SCOpenQuests-weekly`, `schedule-weekly-add.ps1` / `-remove.ps1`, `run.py weekly`, `logs/weekly.log`,
  `backfill_history.weekly()`, the README and DESIGN.md. Re-register the task under the new name and
  unregister the old one. Leave the `"cadence": "weekly"` value until it is decided what a planet-counted
  region's cadence means.
  Next, when the owner wants it: daily counts from the planet diff on a small extract, checked a week
  side by side with Geofabrik (same section).
- The docker image `name-ru-repair-osmium` had been pruned in the cleanup; rebuilt from
  `../name-ru-repair/tools/Dockerfile` (osmium 1.18). The planet-history update, `osm-extracts`'
  backfill clip and `add_parts.py` all need it.
- **The planet history is current:** `history-261029.osh.pbf` (158.8 GB, diff 5160,
  2026-10-29T00:00Z), written by `run.py weekly --no-push` in one pass of 24 diffs: 7,281 s, osmium peak
  15.6 GB (the estimate was 23.8). Header checked (`osmium fileinfo`: with history, sequence and
  timestamp). The first attempt failed at 19:14 because Docker Desktop was quit; the rerun reused the
  downloaded diffs. Docker must be running on Monday mornings, or the weekly logs a failed fetch and stops.
- **The second hard link:** the owner chose to retarget name-ru-repair to the store (its
  `tools/ukraine-history.sh` now reads `osm_extracts.py path planet`, and resolves to the new file). The
  store retired its link to `history-261005.osm.pbf`, and `../name-ru-repair/data/planet/` was deleted on
  2026-10-30 at the owner's word. C: has 354 GB free; a weekly update needs about 170 GB.

**Runs since the publish format (checked 2026-10-28):** 10-26 and 10-28 counted, committed and pushed;
the site serves all 115 cities at 2026-10-27, `data/archive/` holds 1,521 files. The backup's
conditions are met. Snapshots come every other day because Geofabrik's extracts did (10-27's run found
every extract unchanged since 10-26 05:44 UTC), not because of the notes dump.

**The world, decided (2026-10-30, early morning):** DESIGN.md, "World: a seeded bar plus requests".
In short: count big cities up front (bar chosen after a European pilot) plus any place with a polygon
on request; the pilot is the European cities with the most StreetComplete changesets in 12 months;
current numbers come from a clip kept up to date by the daily planet diffs, which osm-extracts owns.
Next, in order:
1. **The clip-plus-diffs test**, replayed over 2026-10-05 to 10-29 on Berlin, Hamburg and Bremen
   against the history file's own slices, each day's diff derived from the same file, nothing downloaded
   (the plan is in that DESIGN.md section). Avoid the 13:15
   window, and avoid Monday 2026-11-02 07:30, when the monthly job rewrites the planet file.
   **Started 2026-10-30 04:30**, detached: `.scratch/diff-replay/replay.py` (gitignored), log
   `logs/diff-replay.log`, results in `data/backfill/replay/RESULT.md` and `results.jsonl`, a row per
   region and day. First a planet pass (about an hour), then about 3 to 5 hours of days. A rerun goes
   on where it stopped: `python .scratch/diff-replay/replay.py`. The Bremen pilot (`--pilot`, its
   261005 clip, 2 days) found one trap: `derive-changes` needs `--increment-version`. Without it,
   `apply-changes` keeps deleted objects, and counts drift by 1-2 a day. With it, both days were exact.
   **Result (12:02): it holds.** All 72 region-days counted the same as the fresh cut. One edge case:
   Hamburg's clip lacked 17 nodes of one way for 22 days, and no count moved. The planet pass took
   3.2 h. DESIGN.md, "The test's result". `data/backfill/replay*` (19 GB: every day's clip and cut) can be deleted.
   Docker Desktop was found stopped at 14:06 (not by the test); the monthly job on Monday 2026-11-02
   07:30 needs it running.
2. Now: `fetch planet-diffs` and the current clip in osm-extracts.
3. Rank European cities by StreetComplete changesets (the changeset dump through osm-extracts) and
   show the owner the list.
4. The step from a request to a counted region: place id to relation, country codes, time zone, a
   region per time zone over the shared clip. `add_city.py` cannot do it today.
Housekeeping still open: the weekly-to-monthly rename (above).

**The European pilot: where it stands (2026-11-01, 01:00).** Read DESIGN.md from "World: a seeded bar
plus requests" to the end first. In short:
- **Built and committed, nothing pushed.** osm-extracts (main, up to c9d4081): `fetch changesets`,
  `fetch planet-diffs`, clips (`clip`, `recut`, `fetch <clip>`), a changed polygon waits for the next
  recut, one container name per osmium run, missing edge nodes fetched from the OSM API. sc-open-quests
  main: the ranking tool and `data/rank/`, DESIGN and HANDOFF. Branch **`europe`** (worktree
  `../sc-open-quests-europe`, up to 4766615): the 32 cities in four time-zone regions over the clip
  `europe`, `tools/clip_polygon.py`, per-city `group` in the picker, `backfill_history` reading a clip's
  history cut with one shared slice, the monthly `run.py planet` job (`weekly` its old name) and
  `schedule-planet-*.ps1`, the title "Canada and Europe". 98 tests pass on the branch.
- **The clip:** `~/Code/.osm-data/europe/`, cut from `history-261029` on 2026-10-31 (planet pass
  11,630 s, 9.1 GB peak; 1.67 GB, 127.6M nodes), brought to 11-01 by `fetch europe`. Its history cut
  `europe-history-261029.osh.pbf` (7.9 GB) gives the monthly points.
- **Counted, in the worktree only:** all 32 cities at 2026-10-29 (`data/archive/europe-*` there; main's
  archive was copied in so the site preview has the rest). Istanbul 2.05M open quests, Moscow 1.64M,
  London 3.8M; the totals looked plausible against Berlin's 1.11M.
- **Monthly points so far:** 20 per region, the 1st of every quarter 2017-01 to 2021-10, staged in the
  worktree's `data/backfill/europe-*/snapshots/` (not merged yet). `.scratch/europe-overnight.sh` (log
  `logs/europe-overnight-2.log`) stopped twice at the same place: **the engine fails on `europe-msk` at
  2022-01-01**, in Moscow's area pass right after Minsk's, with a bare "error: Failed requirement."
  (it was SC's own tag-length check; found and fixed, item 0 below). 2017-2021 counted, and so did the 10-29 clip. A
  monthly slice is the whole 20 km ring of the history cut, 214M nodes, against the clip's 127M. The
  slice is kept for reproducing it: `data/backfill/msk-repro/europe-2022-01-01.osm.pbf` in the worktree
  (a hard link, 2.5 GB), with the command in `logs/europe-overnight-2.log`.
- **Ran until 2026-11-02 00:34:** `.scratch/europe-months.sh` (log `logs/europe-months.log`,
  started 2026-11-01 18:03) counted the months of the three other regions; now `europe-months-4.sh`
  (item 0 below) counts all four, quarterly first, then every
  month: about 23 min a month (one slice of 3.5 min, central 15 min), so the quarterly ones by about
  02:00 and the rest about 30 h later. Rerun the script to go on; it skips what is counted.
- **Site preview:** `run.py history` in the worktree (its docs/data left uncommitted: main's daily
  data commits would conflict at the merge), `python -m http.server 8791 --directory
  ../sc-open-quests-europe` (8765 is another project's), then `/docs/?city=london-gb`. Screenshots:
  `.scratch/europe-preview/` (`shoot.py`). No page errors; München sits under Germany.

**2026-11-02 afternoon to 11-03 morning (a session after the merge):**
- **The months job died again at 12:02 on 11-02**, europe-msk 2017-12-01, Moscow's area pass: "Polylines
  must each contain at least two elements". SC's `ElementGeometryCreator` checks a way's size *before*
  it drops repeated positions, so a way whose nodes all share one position gets a polyline of one point,
  and `intersectsWith` (AddMaxHeight's bridge check) fails on it. Upstream master still has it. Patch
  `onepoint` (engine README, `sync-sc.ps1`, OnePointTest): `intersectsWith` answers false; only counts
  that used to fail change. On `europe` 3742af2, cherry-picked to main (every engine test passes there,
  SnapshotReproductionTest included; 99 pytest). The job was restarted the same
  way at 12:51 (old log kept as `logs/europe-months-4-until-1202.log`); Moscow 2017-12 counted in 116 s,
  between its neighbours. At 11-03 08:35 it was at 2024-11 for all four: done about 21:00 on 11-03
  (its own copy of the old quiet window pauses it across the 12:15 run).
- **The daily run failed on 11-02 at 13:22** on the first Europe clip filled from the API: `osmium
  merge` leaves `sorting=Type_then_ID` out of the header, and the engine refuses such a file. Fixed in
  osm-extracts 0a45f19 (merge passes the header); that day's clip was checked ordered and its header
  rewritten with `osmium cat` (meta and latest.json carry the new sha256 and a `note`). The task was
  started again by hand: "data 2026-11-02" pushed at 14:29, 147 cities; check-release opened issue #1
  (v64.1). A normal day's Europe counts take about 35 min (europe-central 10-20 min, while the months
  job runs), so a run is up to two hours.
- **Daylight time:** the task's trigger is 17:15 UTC (12:15 EST now, 13:15 in summer). The quiet window
  in `backfill_history.QUIET` was local 12:55-13:50, so it no longer covered the run; it is now UTC
  16:55-19:15. `schedule-add.ps1` gives the trigger in UTC and allows 4 hours (the task was
  re-registered on 11-03: PT4H). Every other kk- task with a `-05:00` offset moved an hour too; no
  collisions.
- **Near-duplicate parts done:** `add_parts.py` drops a part covering 90% or more of its city (step 5).
  That is Bremen r2088648 (97%) and Saint John's r19758481 and r19872688 (100%). Halifax's (1%),
  Gatineau's (42%) and Fredericton's (71%) same-named parts are former cities and stay; lower
  `MAX_COVER` to drop Fredericton. `places.py build` also marked the 32 European cities as counted:
  the Europe merge had not rebuilt the name layer.

**"Only quests the app had then" (2026-11-03, late evening):** a switch on the totals chart that counts each
quest from the release that first offered it, so the line steps up where quests were added, and lists the
five largest arrivals. No recount and no engine change: `docs/data/quest-releases.json` from
`tools/sc_first_release.py` (DESIGN.md, same name; REPIN.md, step 5). Real old versions were measured and
turned down: the custom quests hold 41-80% of the counts, and each old engine is a repin. Step heights are
today's rules; quests SC dropped with no successor (ten names) are not in the counts, so a step is an
arrival, never a removal.
Checked in a headless browser on the published data, no page errors. Next if the heights look wrong: count
a few big filter quests with their old filter at their arrival month. The SC clone for the tool is in
`~/AppData/Local/Temp/sc-history-probe/`; the docstring has the line to make it again.

**City picker (2026-11-06):** the dropdown is now a button and a search sheet (DESIGN.md, "The city
picker"; `aka` in DATA-FORMAT.md). The first visit shows Guelph at the owner's word. A city's
English name is `name`, the local one an `aka` (`add_city.py` uses `name:en`); re-adding a city drops a
hand-written `aka` and `group`. Places shows English first, Cyrillic romanized; other scripts with no English name stay local. Compare's country filter
is put off.

**Coverage map (2026-11-06):** a Map tab draws every counted city's boundary over OSM's tiles (DESIGN.md,
"The coverage map"; `docs/data/coverage.json` in DATA-FORMAT.md). `run.py history` writes the file, so
new cities appear by themselves.

**Next, in order:**
0. ~~Find the `europe-msk` failure.~~ **Found and fixed 2026-11-01 evening** (engine 8d8f220 on main,
   cherry-picked to `europe` as 4ab7b15; engine/README.md, patch `codepoints`). A Moscow shop's
   `description` (node 7370179285, 2021-11-13 to 2023-10-10, just outside the city polygon, so only the
   area pass built it) is 255 code points, but 257 UTF-16 units with its emoji, and v64.0's `Element`
   requires `length <= 255`. SC fixed exactly this in 8fe4c925 (#7341), **released in v64.1 on
   2026-11-01**; the patch backports it until the repin. OSM also holds values over 255 code points
   (node 5616691292 in Poland, 271, outside every city): both passes now leave such a tag out, logged
   ("tag '...' is over 255 code points, left out"), instead of stopping. A bare `require()` now prints
   its stack trace. Checked on a Moscow cut of the kept slice: the pre-fix engine fails there, the fixed
   one counts it; every engine test passes, the snapshot reproduction unchanged.
   The months job rebuilds the worktree's engine before it counts, so `europe-months.sh` has run the
   fixed engine since 20:37. **Restarted with all four regions at the owner's word, 2026-11-02 00:36**:
   `.scratch/europe-months-4.sh` (hidden, log `logs/europe-months-4.log`, `.err`); `europe-months.sh` is
   stopped. Its first count was the one that had failed: europe-msk 2022-01-01 in 135 s (Istanbul
   1.29M, Moscow 1.39M, Minsk 346k open, each within 1% of 2021-10). Quarterly first (msk's 20 quarters
   cut alone, about 2 h), then every month for all four, about 30 h. To go on after a stop, start it
   again the same way: `Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe'
   -ArgumentList '/c/Users/kk/Code/sc-open-quests/.scratch/europe-months-4.sh' -RedirectStandardOutput
   logs\europe-months-4.log -RedirectStandardError logs\europe-months-4.err` (it skips what is
   counted and reuses a slice already cut; stop it by its process tree, not while it is slicing). The
   repro slice and the scratch cuts are deleted.
1. ~~The merge.~~ **Merged and published 2026-11-02 ~12:00 at the owner's word ("just publish it")**,
   before the months were done: merge 57fbf1b (one conflict, the engine README's wording; main's kept),
   data a0c40cd: 147 cities, the Europe ones quarterly since 2017-01 plus the months counted by then
   (west, central and east monthly to about 2020-10). Checked: 98 pytest, `run.py history` (231 files),
   and Moscow, London, Istanbul, Toronto and München in a headless browser, no page errors. From the
   next 13:15 run on, main counts the Europe regions daily (`fetch europe` is in its `download`; Docker
   must run). **Done 2026-11-06:** `.\schedule-planet-add.ps1` ran without elevation: the task is
   `kk-SCOpenQuests-planet`, next 2026-12-07, and `run.py weekly` is gone.
2. ~~The rest of the monthly points.~~ **Done 2026-11-03.** `logs/europe-months-4.log` ended in "months
   done" at 19:18, no FAILED (the last months took about 45 min each, europe-central 25). All 118 months
   2017-01 to 2026-10 are in for the four regions, merged and pushed as "data: every month from 2017-01
   to 2026-10 for the 32 European cities" (300305fe); 99 pytest; each city has 122 points on the live
   site, the largest month-to-month move 23% (Zagreb 2018-02). Worktree `../sc-open-quests-europe` and
   branch `europe` are removed (only 36 old notes clips and the three parts dropped on purpose were not
   on main).
3. ~~Monday 2026-11-02 07:30.~~ Done: `history-261102.osh.pbf` written in 10,432 s (osmium 7.8 GB),
   261029 retired; the months slice the clip's own history cut and are unaffected.
   Docker Desktop must be running (it was found quit twice), and so must it for every clip fetch.
   After the merge, the next monthly run re-cuts the clip from the newest file by itself.
4. **Watch:** ~~the first daily `fetch europe` with the API fill~~ (11-02: 3,040 -> 0 missing, 3,035 nodes
   in 4 s, merge 76 s; its header is the fix above);
   the re-cut's memory (4.3 GB of the 4.5 GB budget for this 1.67 GB clip); the clip grows with every
   city added (`add_city.py`, `tools/clip_polygon.py europe`, `osm_extracts.py clip europe --polygon
   config/europe.geojson`; it is cut at the next recut).
5. ~~Repin to StreetComplete v64.1.~~ **Done and published 2026-11-03 at the owner's word**: merged
   (b414bc21), each region's newest extract recounted with v64.1 (50 min, `logs/repin-v64.1-count.log`),
   history, icons, pushed; issue #1 closed. **The owner chose no recount:** older snapshots stay on v64.0,
   so the series break at the newest snapshot of each region (Canada and Germany 11-02, Europe 11-03).
   Totals move 0.05% (Ontario) to 0.42% (Lisboa); AddAcceptsCards alone rises 6 to 15%, and it and
   AddAcceptsCash are off by default on the site. DESIGN, "Repin to StreetComplete v64.1", has the
   changes and the checks. The oracle is exact on Guelph (33,311) and Bremerhaven (20,413), for all 52
   custom quests. After the count, 105 pytest and 59 engine tests pass, SnapshotReproductionTest
   included; TorontoRegressionTest skips, as its extract is pruned. Four cities load in a headless
   browser with no page errors. Worktree and branch are removed. `.scratch/oracle-v64.1/` (213 MB of
   previews) can go. Watch the 12:15 run: it is the first scheduled one on v64.1.
6. **Later:** the seeded bar for other countries, chosen from what these 32 cost (DESIGN.md); the step
   from a request on the site to a counted region.
   What GitHub can hold while that grows: DESIGN.md, "Hosting headroom: measured" (about 350 more cities
   as things stand; near 1,000 the daily data leaves git history).
7. **Asked 2026-11-06:** counting the whole planet, not cities (DESIGN.md, "The whole
   world: measured and proposed"). The owner's answers are there: cells within 0.1%, Overture boundaries, this machine only, a weekly world in about 24 hours. The cell test passed: every city within 0.1% (DESIGN.md, "The cell test: passed").
   What to buy for daily runs, and when: HARDWARE.md.
8. **Canada and Germany onto a clip (2026-11-06, the owner's yes):** a week side by side, to 11-14, then the
   switch. DESIGN.md, "Canada and Germany onto a clip"; read `.scratch/side-by-side/report.csv` then.
9. **Engine, next (2026-11-07, handed off by the owner):** ~~kerbs found once per map data for AddKerbHeight and
   AddTactilePavingKerb~~ **built 2026-11-07** (c2648077, DESIGN.md "Kerbs once per map data: built"): same counts,
   verifyFast passed on Berlin and London, 9% less CPU on europe-west, but no wall-clock gain on one engine; a city's
   area pass lasts as long as its longest task (London: AddHousenumber, one 62 s run). ~~A profile of
   CheckExistence~~ **done 2026-11-07** (DESIGN.md, "CheckExistence profiled"): not the feature lookup, but untagged
   nodes slipping past the fast reject; a one-line fix, same counts, Istanbul's CheckExistence 36.5 s to 6.9 s, the
   europe-msk pass 132 s to 117 s. 69 engine tests pass after it, SnapshotReproductionTest included (TorontoRegressionTest
   skips, its extract pruned). ~~AddLevel and AddLevelThing~~ **done 2026-11-07, late evening** (b637a40b, 9614f8bd;
   DESIGN.md, "The level quests: a grid per mall, and one ordered queue"): twins with a shared grid of level points,
   and a city's area runs from one ordered queue. Same counts, verifyFast passed on Berlin and europe-msk, 71 engine
   tests pass; Moscow's area pass 56-67 s to 24-27 s, the europe-msk pass 129-139 s to 98-102 s, London unchanged.
   Not pushed; the 12:15 run pushes it (and runs the new engine first: watch its log). Next: AddHousenumber for
   London's wall time (start it first in the queue, a cheap test), then AddChargingStationSocket.
   After that, the Germany world prototype (DESIGN.md, "The whole world: measured and proposed").
