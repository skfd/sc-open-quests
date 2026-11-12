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
Housekeeping: the weekly-to-monthly rename is done (2026-11-06, `run.py planet`, `kk-SCOpenQuests-planet`).

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
   Pushed by the 11-08 run, which ran the new engine without trouble (europe-msk pass 86 s, Moscow 23.7 s).
   ~~AddHousenumber~~ **done 2026-11-08** (DESIGN.md, "AddHousenumber: one removeAll, not one per area"): 77% of
   its time was one `removeAll` per address area; one at the end instead. Same counts and grid on europe-west,
   London's area pass 67.9 s to 32.8 s, the europe-west pass 124 s to 96 s. AddChargingStationSocket was looked at
   in the same profile: a plain scan, not a floor, nothing to fix in it. verifyFast on London passed late on 11-08
   (all twins equal their ports, 8 map data runs).
   ~~Profile the whole area pass~~ **done 2026-11-08, late evening** (DESIGN.md, "The whole area pass profiled"; new
   opt-in `-Dopenquests.taskTrace`, no count changes). London's run phase is 26.7 s against about 15-18 s if perfectly
   spread (12 cores, 24 threads): 14 s CPU-bound, then a tail of three single runs (AddHousenumber, AddMaxHeight, AddLevelThing) that
   started late. 8 kerb runs hold threads idle for about 8 s waiting for the shared search. 30% of area CPU is the
   fast reject saying no. ~~(1) AddMaxHeight, (2) the queue~~ **built 2026-11-08, late** (DESIGN.md, "AddMaxHeight
   and the queue: built"): same counts on europe-west and europe-msk, 71 engine tests pass; run phase London 26.7 s
   to 24.0, Moscow 20.7 to 18.1, Minsk 4.6 to 3.7. Not pushed until the 12:15 run. The floor is now the long
   runs themselves (AddHousenumber, AddLevelThing, AddMaxHeight, at half a core each under load). ~~(3) Candidates
   by key~~ **built 2026-11-08, late** (DESIGN.md, "Candidates by key: built"): run CPU London 241 s to 162, Moscow
   161 to 121, same counts (six Europe cities, Bremen, grid byte for byte, verifyFast, a new KeyIndexTest, 73 tests). Not pushed
   until the 12:15 run, which is its first daily use. Next, if more is wanted: a JFR run of the new engine; the
   hand-ported custom quests' `isApplicableTo` scans; or a faster AddHousenumber or AddLevelThing.
   After that, the Germany world prototype (DESIGN.md, "The whole world: measured and proposed").
10. **Germany world prototype: done 2026-11-09, night** (DESIGN.md, "Germany as cells: the world prototype").
   `tools/world_cells.py`; Germany as 34 node-sized cells in 4 files, counted in 1,007 s with two engines; every
   counted German city within 0.002% of its whole-city count; 39,446 Overture places with a number. It found
   the summit quests' all-against-all, now a fast twin (same counts). Next, the owner's call: country rules and
   time zone by position, per-file notes clips, then a larger country or a continent stage.
11. **Country rules and time zone by position: started 2026-11-09 08:40** (owner: "continue"). Plan: (a) a city
   without `countryCodes` is gated by position, SC's own `isInAny(position, enabledInCountries)`, resolved per
   (city, quest) from its bbox first; typed `countryCodes` mean what they do today; (b) a `zone` patch on SC's
   ktx date helpers so each city's matches run in its own time zone, not one per JVM; (c) world_cells gives a
   cell the zone at its centre (timezonefinder); (d) a notes clip per file. Check: the Europe clip
   (`~/Code/.osm-data/europe/`, 4 zones, about 25 countries) as cells against the 32 cities counted whole on the
   same file and notes clip, in `.scratch/world-eu/`. No engine run 11:50-14:15 (the daily run).
   **Done 2026-11-09 09:40** (DESIGN.md, "Country rules and time zone by position: built, checked on Europe"):
   engine 92cc9ab0, world_cells 0af8f5c1. The Europe clip as 16 cells: every one of the 32 cities within 0.004%
   of its whole-city count; Bratislava's +4 AddCycleway is the border gate doing what the app does; the zone
   per cell showed nothing at a 00:00Z asOf. `.scratch/world-eu/` can be deleted. Next is the owner's: a larger
   country or a continent stage.
12. **Counting from the day's diff (asked 2026-11-09, late evening):** measured, nothing built (DESIGN.md,
   "Counting from the day's diff: one day measured"). On europe-west, 11-08 to 11-09, 1,299 of 4.6M matches
   flipped; 73.5% on an element in the diff, 26.1% by ageing, four by a note, one by a neighbour within 20 m, none unexplained. A step that still scans the
   files gains under 2 times (the scans are 48 s of an 85 s pass), so the gain needs an indexed store.
   Next is the owner's: the same comparison over the stored week and all four Europe regions, then a prototype.
   `.scratch/diff-flips/` (900 MB) is the ground truth for item 13's replay: keep it until then.
13. **The stream (2026-11-09, near midnight; the owner: "an efficient way to reach the daily world
   processing. this is one of strategic ideas. there can be others"):** DESIGN.md, "The stream: probed, and
   the plan". Minute diffs and the changeset feed are live; no public before/after source, so the state is
   ours. 153 quests are decided from the element alone: 70% of matches, 72% of flips. **Next: step 1 of that
   plan**, the replay of 11-08's minute files through those quests for europe-west against the measured day
   (new engine command "evaluate these elements"; the match dumps in `.scratch/diff-flips/` are its ground
   truth, keep them). Not started. No engine run 11:50-14:15 or at 15:10. Real-time updates and solved quests
   from changesets were non-goals above; the owner lifted them for this test.
14. **The stream, step 1 done (2026-11-10, 00:15; the owner: "do it now"):** DESIGN.md, "The stream, step 1".
   11-08's 1,415 minute files replayed for europe-west through the 153 element-only quests: 606 net flips,
   exactly the measured ones on touched elements, no element's final state off; 660 events from 113
   changesets; 63 of 69 StreetComplete changesets show their quest closing (the six traced: no quest left
   open after its answer). No engine
   change: versions as a synthetic PBF through `count --dump-matches`. `.scratch/stream-replay/` holds it.
   Tier 2 is item 16.
15. **Faster cells (2026-11-10, 00:40 to 02:40; the owner: "lets do what you suggest"):** DESIGN.md, "Where a
   cell run's time goes: one Germany file measured". One Germany file traced and profiled alone: the quest runs
   are 27% of the CPU, the collector about 29%, the main pass 23%; places cost nothing measurable. **Built, same
   counts:** twins for CheckExistence and AddChargingStationSocket (`FastScans.kt`) and a grid key that spreads
   (`gridKey`); the file about 410 s to 333 s alone. **Found: a cell's box sizes SC's `LatLonRaster`,** and a
   stretched cell made two arrays of 5.7 GB; a sparse world cell would not fit at all. **Next:** that section's
   list, item 1 first (the planner must not make giant boxes), then the file's records as arrays. The first
   reading of the logs (charging stations top every cell) was wrong and is corrected there.
   `.scratch/cells-fast/` (212 MB with two engine copies) and `.scratch/world-de/` are needed to repeat any of it.
16. **The stream, tier 2 done as a daily test (2026-11-10, night):** DESIGN.md, "The stream, tier 2". The 40
   area quests recounted only on the ground diff 5171 touched (90 rectangles, 12 km2 of London's 1,595, 1.1% of
   the tier-2 matches): the patch counts' own flips applied to the old state give the full count of 11-09
   exactly, at rings of 100 m, 300 m and 1 km; all 350 flips an edit caused are inside a rectangle; the other
   8 are aged. Replacing the state by a patch count was off by one match at 100 m and at 1 km (two
   differences between a patch and the whole city, not traced). Engine: opt-in
   `-Dopenquests.areaPaddingM` (default 1 km). `.scratch/tier2/` (58 MB; `inputs.pickle` saves the 20-minute
   read of the diff and clips). No radius settled, nothing faster yet: the engine still scans the file.
   **Next: due dates (step 3), then the store and one planet day's cost (step 5);** the stored week if a
   radius is wanted. Keep `.scratch/diff-flips/` until then. 79 engine tests pass with the ring setting
   (TorontoRegressionTest skips).
17. **CPU time in `engine/measure.ps1` (2026-11-10, the owner's yes):** the summary line now gives the java
   process's CPU time, read after exit, next to wall time; Bremen 11-01: 28.6 s wall, 198.6 s CPU. Compare runs
   by CPU on a busy machine. It also follows only its own java child now, not any engine on the machine.
   Not done: CPU time per phase inside the engine (only the area task trace has it), interleaved A/B runs.
17. **The stream, step 3 done (2026-11-10, night):** DESIGN.md, "The stream, step 3". The 11-08 clip with the
   clock at 11-09 opens exactly the 342 quests the full counts show opening on untouched elements (339 aged, 3
   by notes, which the notes clip replays with the clock) and closes the one note close; only the neighbour
   flip is left, and tier 2 has it. The clock never closes a quest; about 970,000 quests wait for their date in
   europe-west, 140 to 360 come due a day. No engine change; `.scratch/due/` (3 GB of dumps, can be deleted).
   So every flip of the measured day is explained by one of three parts. **Next: step 5, the store and one
   planet day's cost.** Nothing built towards it. The table of due dates itself is not built either.
18. **The stream, step 5 done (2026-11-10, 03:50; the owner: "continue building"):** DESIGN.md, "The stream,
   step 5". A node location store for the whole planet was built (pyosmium `dense_file_array`, 107 GiB, 35
   minutes from the history file, checked against the 11-08 and 11-09 Europe clips on 2.5M nodes each), and
   11-08's 1,415 minute files went through tier 1 for the world on it: **about seven minutes on one thread
   and twenty seconds of engine for a planet day; 350,162 events (240,991 opened, 109,171 closed)**;
   europe-west gives exactly step 1's 660 events; 98.2% of the world's 7,228 StreetComplete tier-1
   changesets show their quest closing. The planet has 10,988,329,357 live nodes (HARDWARE.md). The state
   is sized from real dumps, not built: 6.2 bytes a match, about 12 GB for the world. The two lookups tier 2
   needs are estimates only (about 300 GB with the node store, an Overpass instance's size).
   Engine: opt-in `-Dopenquests.areaPass=false` (README); the test suite passes with it.
   `.scratch/store/` holds the scripts, logs, `RESULT.txt` and `events-world.tsv` (540 MB; can be deleted).
   **`planet.loc` is deleted**; `bash .scratch/store/planet.sh` rebuilds it in 40 minutes (107 GiB on C:,
   and the planet job of 2026-12-07 needs about 170 GB free, so delete it again). The script names
   `history-261102.osh.pbf` and day diffs 5165 to 5170 (`store.py`, `DAY_DIFFS`): once the planet job
   has retired that file or the store has pruned those diffs, it needs the new file and the sequences
   from that file's date to the day replayed. Deletions in day diffs carry a place; `store.py` empties
   them (that code ran by hand on this store, not yet inside `diffs`).
   **Next is the owner's:** both ways forward wait for the first count of the whole world (it seeds the
   stream's state and is its oracle), and that waits for item 15's list, item 1 first (no giant boxes; a
   cell must also not span every longitude, found here). Open strategic question: tier 2's store, built
   here or an Overpass instance.
19. **The whole planet, made ready (2026-11-10; the owner: "are we ready to do it now?"):** DESIGN.md, "The whole
   planet, made ready". Not as things stood; now: cells at most 10 degrees a side, the engine refuses a box
   over 500M raster squares by name, edges kept on the globe, `kd` and `nodegrid` at planet size, the cut in
   two stages, `count --delete-cut --dump-ids --only` and the daily window. Cutting a box down to its data was
   tried and dropped: SC's point-in-polygon quirk makes counts follow where the box starts. Rehearsed on
   Germany re-planned: every city equal to the 11-09 cells, 893 s. **The date is 11-08T00Z**, so the count is
   checked twice: the stream's 316,806 touched elements (`--dump-ids`) and Europe's 32 snapshots of that instant
   (`report --archive 2026-11-08`). The chain: `.scratch/planet/chain.sh`, log `logs/planet-count.log`, about
   30 hours; a rerun goes on where it stopped (the command is in the script). It deletes the planet slice
   after the cut; files are kept until both checks pass (`--delete-cut` comes back then). Nothing of it may be
   on C: by the planet job of 2026-12-07.
   **Started 2026-11-10 09:51 with `STOP_AFTER=plan`** (slice, grid, plan; hidden, log `logs/planet-count.log`),
   while the new paths are rehearsed on the 11-08 Europe clip (`.scratch/planet/rehearse/`). Once the plan is
   out: the grid's node total should be about 10,985.7M (step 5's 10,988,329,357 less the 3,025,623 nodes
   made on 11-08 plus the 425,947 deleted), and the chain is started again without `STOP_AFTER`.
   **Rehearsal passed (10:25):** streamed grid identical, two-stage cut accepted, 32 European cities within
   0.004% of their 11-08 counts, oracle 1 exact (676 of 676; and no tier-1 match the stream lacks). So a
   watcher (`.scratch/planet/watch.ps1`) starts **`.scratch/planet/chain2.sh`** (the same chain, plus a gate on
   the grid's node total, within 1.5M) when the first stops after the plan: log `logs/planet-count-2.log`.
   Reruns use chain2.sh. Expected: plan about 14:30 today (the grid waits out the daily window), the cut 9 to 12
   hours, so the canary after midnight, the count about 6.5 hours, done about 07:00-11:00 on 11-11; then
   `REPORT.md` and `oracle.log` in `.scratch/planet/world/`. A failed file is retried alone at 44 GB, and the
   checks run either way. **While it runs: no engine rebuild (`installDist`) and no edit to chain2.sh** (bash
   reads a script as it goes); stop it by its process tree first.
   This run gives the world's totals and both checks, not the stream's seed state (only listed elements are
   dumped). A state dump later is a recount of the kept cut (about 100 GB in `.scratch/planet/world/cut/`), not
   a new slice and cut, so keep the cut while that is wanted; it must be gone before the planet job of 12-07.
   **Disk:** the cut needs the planet's size plus 40 GB free beside the planet, or it stops ("cut: N GB free, M
   needed"). At the owner's word (2026-11-10, 10:40) `data/backfill/replay`, `.scratch/due/`,
   `.scratch/world-eu/` and `.scratch/oracle-v64.1/` were deleted (27 GB), so a planet up to about 105 GB
   passes. If it still stops, free more and rerun chain2.sh.
   **Stage 1 done (checked 15:00):** the slice took 8,027 s (planet-261108.osm.pbf, 99.8 GB, ending 12:05);
   `nodegrid` 521 s, **10,985,729,437 nodes, 244 off the 10,985,729,681 worked out from step 5's store**, so the
   slice is the planet at 11-08T00Z. The plan: 16 regions, 128 files (at most 115M nodes), 2,244 cells, 346 of
   them with no nodes, the largest 9.40 by 10.00 degrees, 308 zones; 6.4% of nodes in a zone whose offset differs
   from their cell's. The watcher started chain2.sh at 14:24; notes clipped from planet-notes-261110 (129 clips,
   602 s); the cut's first planet pass (regions r0-r7) started 14:35 with 166 GB free. `smart` writes nothing
   until its last pass over the input, so the region files stay at 0 bytes for a long while.
20. **New hosting: the owner's answers (2026-11-10, noon).** Nothing built yet; waiting on the owner's token.
   - **The whole site moves to Cloudflare** at `https://street-complete-statistics.comentality.com`, not only
     the data (this replaces DESIGN.md's "site stays on Pages, `DATA` points at R2"). Planned shape: a Worker
     serves the page (static assets) and `data/` + `places/` from an R2 bucket bound to it, same origin, no
     CORS; the daily run uploads only changed files instead of committing them. `docs/` today: 4,836 files,
     133 MB, none over 20 MB.
   - **Access:** one Cloudflare API token in a file outside the repo (not in chat); wrangler installed by Claude
     creates the bucket, the Worker, the custom domain and the job's R2 S3 key.
   - **Cutover:** Claude may switch the live site once the copy checks out (every file equal, four cities load
     with no page errors); the old Pages URL then redirects to the new address, query string kept, and the Pages
     copy stays a week as a fallback.
   - **Access in place (2026-11-10, 12:15, set up in the owner's Chrome):** comentality.com was already an
     active Cloudflare zone (id 0f367c49d7fd0b33de52c752a13a2b68), so nic.ua needs nothing. User API token
     "sc-open-quests deploy" (no expiry; template "Edit Cloudflare Workers" limited to the one account, plus
     DNS Edit and Zone Read on comentality.com only) in `~/.config/sc-open-quests/cloudflare.env`
     (`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`), outside the repo; `set -a; . that file` to use it.
     R2 bucket `sc-open-quests` (ENAM) created by API and a test object `healthcheck.txt` written and read
     back. The R2 page asked for "Add R2 subscription" once and later showed the bucket with $0 billing, so
     nothing was clicked.
   - **Built and live, 2026-11-10 afternoon** (DESIGN.md, "Hosting on Cloudflare"; `cloudflare/README.md`):
     the Worker `sc-open-quests` serves the bucket at the new address (merged 856c5496, not yet pushed, so
     the 12:15 run on 11-11 pushes it). All 4,836 files compare equal over HTTPS; four cities load headless
     with no errors. `run.py update` and `planet` now sync to R2 after the git push (`=== cloud ===` in
     `logs/scheduler.log`; a failure is logged "cloud publish FAILED" and doesn't stop the run). Today's
     data went up by hand from main: 176 copied, 4 deleted, 12 s.
   - **The flip, not yet done:** branch `pages-redirect` (local only, worktree `../sc-open-quests-redirect`)
     holds a JS redirect that keeps path and query. `.scratch/cloudflare/flip.sh` checks that a day's
     scheduled run synced by itself and that `--check` passes, then pushes that branch, points Pages at it,
     sets the repo homepage and waits for the redirect. The one-off task `kk-SCOpenQuests-flip` (11-11
     14:00) was refused to Claude by the auto-mode classifier; the owner registers it, or runs the script
     by hand after a run with a cloud step. Revert: `gh api -X PUT repos/skfd/sc-open-quests/pages -f
     "source[branch]=main" -f "source[path]=/docs"`.
   - **Requests:** a first city view is 71 Worker requests (53 of them icons) against Workers Free's 100,000 a
     day; icons and images now cache a day in the browser (2e059b56), so a returning reader costs about 10.
     Compare, Places and Map load with no errors (15-16 requests each). If traffic nears the cap: Workers
     Paid, or the page and icons as static assets (the owner's call). `flip.sh` was tested dry on a
     synthetic log (passes; refuses a failed or missing cloud step) and syncs once more before its check.
   - **Cost review (2026-11-10, 13:00; nothing built, the owner decides):** the bill is $0 and can't
     grow as built: Workers Free (the plan as recorded above, not read from the API) never bills,
     egress is free, and the Worker is the only reader of R2,
     so its 100,000 requests a day hold R2 reads to 3M a month against 10M free. The one limit is that
     daily cap (resets 00:00 UTC; past it readers get error 1027; Workers Paid is $5 a month for 10M).
     Measured today from Cloudflare's analytics: 25,255 Worker requests, all ours (one `--check` is
     4,836, 5% of a day, so it stays out of the daily run); R2 30,787 reads, 4,958 writes, 1,270 lists;
     `docs/` is 128 MB (places 95, data 32, icons 0.6) against 10 GB free. `sc-open-quests` is the
     account's only Worker. Real demand isn't known (Pages counts no visitors; the repo had 12 views in
     14 days); the zone's Web Analytics will show it after the flip.
     Levers, in order: (1) page, icons and img as Workers static assets (193 files, 0.7 MB; asset
     requests are free and unlimited, 20,000 files and 25 MiB each on Free), taking a first city view
     from 71 Worker requests to about 15; it is a second publish path (`wrangler deploy` whenever
     `app.js` or icons change, or page and data drift apart), so an icon sprite kept in R2 is the
     one-path alternative (about 19 a view, needs `app.js` changes). All of `docs/` as assets fits
     today (4,836 files; places has held at 4,202 since 10-31 and grows only as places are added)
     and would need no Worker or R2, with a 20,000-file cap. Any Worker change waits for the flip,
     which was tested against this Worker. (2) `app.js` fetches every data file with
     `cache: "no-cache"` (there since the first site, 7e6516f6), so `max-age=300` never applies and
     each one revalidates through the Worker; dropping it saves only fetches repeated within five
     minutes. Not levers:
     storage, R2 operations, compression, and edge caching (a Worker runs before the cache; Workers
     Cache hits still count as requests). Dated snapshots aren't safe as `immutable`: a rerun rewrote
     2026-11-02.
   - **The goal is a traffic spike (the owner, 2026-11-10, 13:30): the site is in stealth with no
     readers and should survive being posted.** That supersedes the ranking above: the cap is the
     risk, about 1,400 first city views a UTC day (100,000 / 71), then error 1027 until midnight UTC
     (what a custom-domain visitor sees then is not verified). Static assets for page and icons only
     raises it to several thousand (an estimate: a first Toronto view made 5 `data/` requests, more
     with a snapshot and parts); only two things remove it:
     - **All of `docs/` as static assets on the same Worker, tried and not live.**
       `cloudflare/assets-trial/wrangler.jsonc` is the live Worker plus an `assets` block
       (`../../docs`, `auto-trailing-slash`, `not_found_handling: none`); a path with a matching
       file never runs the Worker, anything else falls through to the R2 script as today. Locally
       (`wrangler dev`, launch config `assets-trial`, port 8791): all 4,836 files byte-equal, Toronto
       loads with no console errors, a missing file is a real 404, `/index.html` redirects to `/`,
       ETag gives 304, JSON goes out Brotli. Deployed once as `sc-open-quests-assets-trial` with no
       route and no workers.dev, then deleted: first upload 42 s, an unchanged redeploy 20 s.
       Differences from today: every file is `max-age=0, must-revalidate` (icons lose their day in
       the browser unless a `docs/_headers` file says otherwise; revalidations are free), JSON's
       type has no charset. **A path with no file still runs the Worker** (and reads R2), so misses
       count against the cap: a Toronto view made none, but `index.html` declares no icon and
       `docs/` has no `favicon.ico`, so each new browser asks once and misses; give the page an icon
       before the switch. Stray paths and bots count too. Whether assets keep being served once the
       cap is spent is not verified. Limits: 20,000 files and 25 MiB each on Free; `docs/` is 4,836 and grows
       about 2 files a city. Not verified: that production asset requests leave the invocation
       count flat (Cloudflare's docs say "free and unlimited"; a full `--check` after the switch
       proves it), and that the Task Scheduler job finds node. The switch itself: the `assets`
       block into `cloudflare/wrangler.jsonc`, `wrangler deploy` in the daily run behind
       `check_source`, after the flip (flip.sh was tested against today's Worker).
     - **Workers Paid, no build:** $5 a month, 10M requests included (about 140,000 first city
       views), then $0.30 a million; R2 reads past 10M a month $0.36 a million. Together about
       $4.70 per 100,000 first views past the included amounts.
     The owner chooses; nothing live was changed.
   - **The owner chose static assets (2026-11-10, 14:00). Built on branch `assets-switch` (worktree
     `../sc-open-quests-assets`, 7325595e), not merged, not live; it goes live after the flip.**
     It is stricter than the trial: `cloudflare/wrangler.jsonc` has no script at all, so a path
     that matches no file is an empty 404 and nothing can count against the cap (the trial's R2
     fallback ran the Worker on every miss). `wrangler.r2.jsonc` is today's Worker, kept as the
     way back. `tools/cloud_publish.py` syncs R2 first (the guard), then runs `wrangler deploy`;
     `docs/_headers` keeps icons a day; `index.html` declares an icon. Locally on `wrangler dev`:
     4,836 files byte-equal, misses 404, icons `max-age=86400`, Toronto loads with no errors;
     `cloud_publish.py --dry-run` passes; 128 Python tests pass. node is on the system PATH
     (`C:\Program Files\nodejs`), so the scheduled job finds it.
     **Do not merge before the flip:** flip.sh runs `cloud_publish.py` itself, so a merge would
     make the flip deploy the new shape. **To go live, after the flip:** merge `assets-switch` into
     main, `python tools/cloud_publish.py`, then `python tools/cloud_publish.py --check`; the proof
     that asset requests are free is the Worker's invocation count staying flat over that check
     (4,836 requests). Way back: `npx wrangler deploy --config wrangler.r2.jsonc` in `cloudflare/`.
     Then remove the worktree and point `.claude/launch.json`'s `assets-switch` entry at
     `cloudflare/wrangler.jsonc`.
   - **Is the published layout still shaped by GitHub Pages? Audited 2026-11-10 (three read-only
     agents; figures are theirs, gzip not Brotli, except where marked checked).** No rethink of the
     shape: precomputed static JSON with no server is what the new host serves free and what
     survives a spike; anything computed per request brings the cap back. What is open again:
     - **Decided because of a GitHub limit:** (1) only the newest snapshot per region is published,
       the other 2,145 (489 MB) sit in `data/archive/`, unpublished and the one copy, not backed
       up; with them the per-neighbourhood series. Bytes are no longer the limit, files are: +2,145
       at once and 16 a day against 20,000. (2) The name layer was cut to stay near 100 MB:
       polygons only, no OSM id, wikidata or population in the record. (3) A site-wide place search
       index (29 MB) was declined, so search downloads every shard of a country (Russia 14.6 MB,
       5.3 MB gzip). (4) Publishing is a git commit of `docs/data`: the reason for "about 350 more
       cities"; it also is the daily record, and the daily run's push is what carries code commits.
       (5) Place requests need a GitHub account. (6) `cache: "no-cache"` on every data fetch and
       unversioned `app.js`/`style.css`. Planned for a limit and not needed now: thinning daily
       points to monthly, sharding `data/history/`.
     - **Not leftovers, keep:** `compare/<quest>.json`, places sharded by region, byte-stable
       output, static JSON.
     - **What a first visit downloads:** 15 same-origin requests, 1.4 MB raw, about 210-230 KB
       gzip, then up to 180 lazy icons. `cities.json` is 125 KB gzip of that, and 59 KB of it is
       `trendAll`, which nothing in `app.js` reads (checked: zero references; written at
       run.py:662); without both trend arrays it is 8.6 KB. A counted city's place or part page
       fetches its whole region snapshot (Ontario 258 KB gzip; 22 of 53 Ontario cities have no
       parts and show nothing from it). `places/index.json` is 129 KB gzip to follow one link.
       Region shards carry bbox columns nothing reads (34.5 to 20 MB gzip over all shards).
     - **Outside our hosting, hit by a spike too:** uPlot and Leaflet from jsdelivr, goatcounter,
       and map tiles from tile.openstreetmap.org.
     - **Pipeline facts:** nothing reads `docs/` back from git history; a failed push skips the
       cloud publish (run.py:890-892); git commits `docs/data` only while the sync uploads all of
       `docs/`; main is 11 commits ahead of origin until the next daily run pushes.
     - **Where it stopped (the owner, 2026-11-10, afternoon: "will work in that direction
       later"):** the session ended here. Open, in order: (a) after the flip, the owner's word to
       merge `assets-switch` and go live (steps above); (b) trim the first-visit download, starting
       with `cities.json`; before dropping `trendAll` ask the owner whether it is kept for
       something not built (tests/test_history.py and the fixtures mention it, the page doesn't);
       (c) check the limits of jsdelivr, goatcounter and tile.openstreetmap.org for a spike;
       (d) a request path that needs no GitHub account; (e) a second R2 bucket as the archive's
       backup, never the site's bucket, which the daily sync prunes to `docs/`.
   - **Before a spike, done 2026-11-10 afternoon (the owner: "spike-proof the page", "back up the
     archive", drop `trendAll`):** DESIGN.md, "Before a spike: what a first visit asks of whom". On
     main, not pushed (the 12:15 run on 11-11 pushes and syncs it; `cloud_publish.py --dry-run` says
     16 files to copy, none to delete):
     - (b) `cities.json` is 8 KB gzip, from 124: `trendAll` dropped, each city's `trend` moved to
       `data/trends.json`, which Compare loads when it first opens.
     - uPlot and Leaflet are served from `docs/vendor/` (byte-equal to jsdelivr's, hashes in its
       README); the page asks no CDN. Headless on the real data: Toronto, Compare, Map, no errors.
     - (c) limits looked up: jsdelivr and GoatCounter are no risk; tile.openstreetmap.org has no
       number and may block heavy use without notice, which would cost the Map tab its ground only.
       **The owner chose to stay on OSM tiles.**
     - (e) `tools/archive_backup.py`: `data/archive/` is copied to the private bucket
       `sc-open-quests-archive` (2,161 files, checked equal), replaced versions kept under
       `replaced/<date>/`; the daily and planet runs do it last (`[backup]` lines in
       `logs/scheduler.log`; "archive backup FAILED" doesn't stop a run). Watch its first scheduled
       run on 11-11.
     - **Unverified until the 12:15 run of 11-11:** the new page has only been served locally (a hand
       sync to the live bucket was refused to Claude as a production deploy). After that run: the
       `=== cloud ===` step says "copied 16" or so; `python .scratch/spike/check.py
       https://street-complete-statistics.comentality.com` shows no errors and no external host but
       `gc.zgo.at` and the tile host; and `curl -sI
       https://skfd.github.io/sc-open-quests/vendor/uplot-1.6.31/uPlot.iife.min.js` is 200 (before
       the flip turns Pages into a redirect). flip.sh's own `--check` then covers all 4,849 files.
     - `data/grid/` (2,145 files) is in the backup bucket too, under `grid/`, at the owner's word;
       `data/notes/` is not (the clips can be cut again from the dumps).
     - `assets-switch` has main merged in (77fdbd8a, 131 tests pass) plus a year's cache for
       `/vendor/*` in `docs/_headers`, so going live after the flip is still a clean merge.
     - (d) is put off: the owner asked whether requests are still needed once the whole planet is
       counted. Mostly not (every place with a polygon gets a number); what is left is monthly
       history for a place and places with no polygon. Nothing built.
     - Still open of that list: (a) the flip, then the owner's word to merge `assets-switch`.
       Further trims not taken: `places/index.json` (129 KB gzip to follow one link), a part page
       fetching its whole region snapshot, bbox columns in the region shards.
   - **Later, after a week:** take the daily data out of git history (the reason for the move);
     README's site link; the token was shown once in a session transcript, so the owner may roll it
     (Cloudflare: My Profile, API Tokens, Roll; then replace the value in the token file).

## Idea: a phone widget for daily progress (owner, 2026-11-10)

Not planned and nothing built. The owner's idea: a home-screen widget showing the graph of one quest, or of
a city or neighbourhood, so an active StreetComplete player sees the day's progress at a glance.

What the data gives it today, and what it lacks:

- **City and quest series exist**: `docs/data/history/<cityId>.json` has every quest's `open` per date.
  It is too big for a widget (Toronto 177 KB; `cities.json` 314 KB), so a widget wants its own small
  file per city, something like the last 30 days of `open` and of a few quests.
- **Neighbourhood counts exist but aren't published as a series**: the archived daily snapshots carry
  `parts` since 2026-10-28 (Toronto: 218 parts, 10 days so far), and the site shows the newest only. A
  per-part series file is a new output of `run.py history`, no recount needed for the days since then.
- **Freshness is the weak point for "daily"**: one count a day from an extract, published around 13:00
  local, and on 11-10 Toronto's newest date was 11-08 (11-04 is missing). A player would see
  yesterday's or older edits, never today's.
- **It measures the place, not the player**: the count moves with everyone's edits and with aging
  (`agedOnly`), and per-user stats are a non-goal. A widget of "my solves today" would be a different
  source (changesets with `StreetComplete:quest_type`).
- **Request budget**: every widget refresh is a Worker request against the 100,000 a day, for data that
  changes once a day, so the widget's file must be cacheable for hours (unlike `app.js`'s `no-cache`
  fetches). Any Worker change waits for the flip.

Open, for the owner when it comes up: the platform (a native Android or iOS widget, or just a small JSON
or image address that generic widget apps such as KWGT or Scriptable can show, which needs no app of
ours); and which view comes first (city total, one quest, or a neighbourhood).

## Idea: share previews for links (owner, 2026-11-10)

Not planned and nothing built. The site has only a `<title>` and a `description`; no `og:`/`twitter:`
tags and no image, so a shared link shows a bare title. The owner pictures people posting their
neighbourhood's link. A design, ignoring how it gets built, with a mockup in `design/og-card-mockup.svg`
(and `.png`; numbers invented):

- **One card per place, 1200x630**: the place's name and its city; one big number (open quests); a
  change chip for 30 days, green when it falls; a 90-day stacked sparkline, to map (indigo) under to
  resurvey (orange), so aging is not read as neglect; the place's own outline with dots where the quests
  are (locals know their shape); the three biggest quest types; "as of <date>" in the band, because
  networks cache a preview for days.
- **The words do half the work**: og:title "1,284 open StreetComplete quests in Agincourt North,
  Toronto"; description with the change and the top three types; og:image:alt says the same.
- **Tone follows the trend**: falling, a cheer; rising mostly by aging, "+120, mostly resurveys coming
  due"; under a few dozen, "almost done: 14 left". Invite, never shame.
- **Other views** get a variant of the same frame: one quest in a place (its icon big), compare (top
  five places by quests per km²), the map (the outline, larger).
- **Survives a thumbnail**: name and number sit in the left half, so a square crop (WhatsApp, Slack)
  keeps them; SC's indigo band reads on light and dark feeds.

Owner's answers (2026-11-10): **English only** for now. **The card shows current numbers**: a plain
link is undated, and its card is whatever was newest when the network fetched it (networks cache for days,
which the "as of" date in the band makes honest). **Tentative, if cheap**: a button that copies a link
pinned to the data date, whose card stays fixed ("Agincourt North on 8 Nov"); it needs a new query key,
since `at` and `on` are taken. Otherwise no share button: networks read the preview from the link's own
tags, so a pasted address is enough.
Constraint for whoever builds it: crawlers fetch the page without running `app.js`, so each place needs
its own static page or a Worker that rewrites the head; the state is in the query, which crawlers see.

### Share previews: proposed architecture (2026-11-10, evening; nothing built)

- **Static pages at path URLs, no Worker.** Crawlers ignore `app.js`, and static assets ignore the query,
  so each previewable view gets its own folder: `/<cityId>/` and `/<cityId>/<slug>/` (147 cities, 4,214
  parts). The slug is frozen in `config/parts` when a part is added (the 12-hex GERS id stays the key; a
  rename must not break a posted link). `app.js` reads the path and writes it for city and part views, so
  the address bar is the share link; old `?city=`/`?place=` links still open. The rest of the state stays
  in the query. Rejected: a Worker rewriting the head, because it brings back the request cap the
  assets switch removed.
- **Generator, a new `run.py` step after history and before the cloud publish:** per place,
  `docs/<cityId>[/<slug>]/index.html` = `index.html` with the head replaced (title, description, `og:*`,
  `twitter:card` summary_large_image, canonical, `<base href="/">` so relative paths survive the depth)
  and `docs/cards/...png`. `og:image` carries `?v=<asOfDate>` so networks refetch it when the data
  moves. Gitignored: the cloud sync uploads them, git never sees them. Byte-stable like the rest.
- **Rendering:** an SVG template filled in Python, made into a PNG by resvg (`resvg_py` wheel). Measured
  on the mockup: 0.30 s and 61 KB per card, with system fonts loaded each call; 4,361 cards is about
  22 min on one core. Not measured: a bundled font file and a process pool, which should cut it a lot.
- **What the data supports:** cities, everything in the mockup (history with `agedOnly`, per-quest counts,
  the outline, the z14 grid as dots). Parts: per-quest counts only, no aged split (one-colour
  sparkline), a series only since 10-28 in `data/archive` (11-04 missing; the chip says "since 28 Oct"
  until 30 days exist), and z14 tiles (2.2 x 1.6 km) are too coarse for dots inside a neighbourhood:
  the panel becomes a locator, the city's outline with the part filled.
- **Budget:** 4,836 + 2 x 4,361 = about 13,560 of the 20,000 asset files, which competes with publishing
  the archive (2,145 + 16 a day). Every PNG changes daily (the date), about 265 MB uploaded a day.
- **Dated-link button: parked.** It needs a page and an image per place per day, so it needs a script on
  its own route. Rendering takes about 300 ms against Workers Free's 10 ms CPU limit.
- **Phases:** (1) per-place pages with text tags plus one site-wide image: no renderer, half the files.
  (2) per-place PNGs. Sequencing: `cloudflare/` stays untouched until the flip and the `assets-switch`
  merge; the generator can be built and checked on `wrangler dev` before that.

## Countries in the place index: decided, not built (owner, 2026-11-10, evening)

The owner asked whether the regional division is controversial. It was Overture's default view as
shipped (Western Sahara wholly Moroccan, no Palestine, stateless places dropped). Decided: countries
come from SC's own `boundaries.ser`, every country it names at a place (Crimea under both UA and RU),
the top level named as SC names countries (the platform's CLDR names, in the browser `Intl.DisplayNames`), except that `PS` is named "Palestine" (CLDR's short form); borders are always SC's; a disputed place (SC names two countries, or SC and Overture disagree) goes under every one of them, inside its Overture region each time; names are OSM's `name` tag; English names only from sources (Overture `en`, then Wikidata), no home-made romanisation; places SC files under no country are left out; never flags; a note says the site files places where StreetComplete
applies a country's rules and takes no position on borders. DESIGN.md, "Countries in the place index:
StreetComplete's, not ours", has the probe results and the build steps. Next: build it, measuring first
how many places move.
- **Owner's answers (2026-11-10, late evening):** per-place images, yes (rendering is local, serving
  static assets is free); **regenerated monthly**, on the 1st with the monthly history point, and the
  page's text tags on the same day so title and picture never disagree (both say "as of 1 Nov").
  **Readable addresses** (`/toronto/agincourt-north/`, slug frozen). The file budget against the archive
  was explained; packing the archive per region and month (16 files a month, not a day) would let both fit.
- **Next session (the owner, 2026-11-10):** neighbourhood statistics. Settle there how the archive is
  published (bundled per region and month or otherwise), since neighbourhood series, the neighbourhood
  cards' trend line and the widget all read it; then the share previews follow.

## Neighbourhood statistics: what exists, and the questions put (2026-11-10, evening; nothing built)

- **The data:** 4,214 parts in 81 cities (no parts in the four `europe-*` regions). The archive carries
  per-part, per-quest `open` at resurvey x1 since 2026-10-28 (10 dated snapshots by 11-08; 11-04
  missing). No aged split, no area, zero counts left out. A part page today shows only the newest
  count per quest. Toronto over 10-28..11-08: median part total 8,746, median change 9, largest 1,353.
- **The archive need not be published for this.** The card generator is a local `run.py` step and can
  read `data/archive/` directly; the widget wants its own small cacheable file. Only the page needs
  bytes over the wire, so the decision is which derived series file to publish, not how to publish
  the archive.
- **Measured shapes (Toronto, 10 days):** one part's per-quest series 4.2 KB raw, 1.0 KB gzip; all of
  Toronto's parts in one file 932 KB raw, 101 KB gzip (about 10 KB gzip more each day); totals only
  (no per-quest split) 4.9 KB gzip, but then the trend ignores the quest ticks that `partTotal` applies to
  the table. Files against the 20,000 cap, with previews at about 13,560: per-part files +4,214
  (about 17,800); per-city files +81; region-month bundles of the raw archive +16 a month. The real
  format must tell 0 apart from "not counted" (a missing day, a part added later).
- **Aged split for parts:** cheap in the engine (the mask is at hand where `countParts` is called; a
  second array next to `partOpen`). Backfilling it to 10-28 needs those days' extracts, and the
  store keeps 14 days: 10-27 and 10-28 are still in `~/Code/.osm-data/<region>/` on 11-10 and go
  at the next fetch or two unless pinned (`pins.json`).
- **Longer history:** the regions' `.osh` history files (monthly points since 2017 for cities) could
  give parts monthly points too. That is a recount of the monthly snapshots with parts on, not measured.
- Questions put to the owner: what a part page adds first; how far back the series goes; whether
  the trend follows the quest ticks; whether the raw archive is published at all.
- **Owner, 2026-11-10 late evening: "assume design for final product where we have full world data".**
  The design is in DESIGN.md, "Place statistics for the whole world: the final product". In short: one
  page for every level; place data on an R2 public bucket on its own subdomain; three cacheable
  requests per page. That replaces the per-part-files idea above. Its open questions are the
  owner's: R2 or static assets, the per-km² divisor, freshness.

## Overnight work, 2026-11-10 into 11-11 (the owner is away; "work all night, one task after another")

Order, one at a time, mindful of the 5-hour usage windows and of the 13:15 scheduled run (the first
with a cloud step, which gates the flip): (1) the aged split per part in the engine, then its backfill
from 10-27; (2) countries from SC's `boundaries.ser`, measured read-only first, built on a worktree
branch and not merged before the flip; (3) the R2 cache test, on a separate test bucket and subdomain
only; (4) the flip itself is the owner's: register `kk-SCOpenQuests-flip` or run
`.scratch/cloudflare/flip.sh` by hand after the 13:15 run (the classifier refused the task to Claude).

- **Pinned (owner, 23:50):** every region's 10-27 and 10-28 extracts (`pins.json` in the 12 regions that
  have parts; about 12 GB), reason "sc-open-quests: backfill of the aged split per part". Unpin with
  `python .scratch/pin-aged-backfill.py --unpin` once the backfill is in the archive.
- **Aged split per part: built (6c24f5e9).** The engine writes `cities.<id>.partsAged` beside `parts`, the
  same shape, `agedOnly` per part and quest (DATA-FORMAT.md, "Places and parts"); `parts` is unchanged, so
  the site and `world_cells.py` read it as before. 80 engine and 115 Python tests pass; the installed
  engine is rebuilt, so the 12:15 run counts with it and compiles nothing.
- **Its backfill, running (`.scratch/aged-backfill.py`, report in `.scratch/aged-backfill/report.jsonl`,
  touched archive files copied first to `.scratch/aged-backfill/backup/`).** Each archived day from 10-27
  is recounted from its own extract into scratch; the day is grafted (the archive keeps its header and
  takes the recount's `cities`) only if the cities equal the archived ones once `partsAged` is dropped.
  The 10-27 days gain `parts` too. Found on the way: **a recount with today's engine does not reproduce
  a v64.0 day** (10-28 Ontario: only AddOpeningHours differs, all of it in `agedOnly`, Toronto +76),
  because the v64.1 repin (3e626b74) changed the engine's own port of that custom quest, which the
  quests file does not version. So the v64.1 days (11-02 on) go through today's engine (log
  `logs/aged-backfill-64.1.log`), and the v64.0 days through the pre-repin engine with the patch
  cherry-picked, built in the throwaway worktree `../sc-open-quests-oldengine` (detached at c0aed812,
  uncommitted): `python .scratch/aged-backfill.py --sc 64.0 --engine
  ../sc-open-quests-oldengine/engine/build/install/sc-open-quests-engine`. The script starts no engine
  run after 10:30, so the 12:15 run finds `pipeline.lock` free.
- **Countries from SC's boundaries: built on branch `countries` (worktree `../sc-open-quests-countries`, rebased on main 03:00, head e6e2c4ab;
  c1a480d3), not merged.** Engine `regionids`, `places.py` filing by SC's countries, the site naming
  countries from CLDR with the borders note; tests pass, checked headless. DESIGN.md on that branch,
  "Countries in the place index: built", has the measurement (6,846 of 1,082,287 places filed
  differently; Crimea, the dependencies, Palestine, Western Sahara as decided) and **one decision for the
  owner: border noise**, about 150 regions shown under a neighbour with a few places where SC's simplified
  boundaries cross the line, some of which read as positions (Kinmen and Matsu under China, Gibraltar
  under Spain). Recommended: ignore a neighbour SC names only near the line (a radius test), and report
  the islands upstream. Merge only after the flip and the owner's answer.
- **R2 cache test: blocked at the DNS step, for the owner.** Test bucket `sc-open-quests-cachetest` made;
  the classifier refused attaching `sc-r2-cachetest.comentality.com` (DNS change). Run the one command in
  `.scratch/r2-cachetest/run.py`'s docstring, then the script. Found meanwhile (Cloudflare's docs, DESIGN.md
  "The R2 cache premise"): JSON is not cached by default, so the place-data subdomain needs a Cache Rule.
- **The aged backfill is done (02:25).** Every archived day with parts, 10-27 to 11-08 in the 12 regions
  (132 days), now carries `partsAged`; the 10-27 days gained `parts` too, so part history starts 10-27.
  124 days matched their recount exactly (the 72 v64.1 days through today's engine, 52 v64.0 days through
  the pre-repin one). 8 (Bremen and New Brunswick, 10-28 to 11-01) differed only by the parts the registry
  dropped on 11-03; `.scratch/aged-backfill/graft_registry.py` added `partsAged` there and kept those parts
  without it (DATA-FORMAT.md). Backups of every touched file: `.scratch/aged-backfill/backup/`; check:
  `python .scratch/aged-backfill/verify.py`. Extracts unpinned, the old-engine worktree removed. Nothing
  publishes `partsAged` yet beyond the newest snapshot; the part series file is the place-page work.
- **Checks before the 12:15 run (03:00):** `run.py history` over the grafted archive into a temp dir works
  (440 files; Toronto's series to 11-08); all 216,133 `partsAged` values are within the part's open and the
  city's `agedOnly`; the installed engine is current; `pipeline.lock` is free; the tree is clean except an
  untracked `hs_err_pid65112.log`, a JVM out-of-memory crash from 23:42 that predates this work (not ours).
  The 12:15 run pushes main's unpushed commits (7), the engine change among them. `countries` exists only on
  this disk. The empty test bucket `sc-open-quests-cachetest` stays on the account until the cache test.
  On the branch, a fix found in the last check: a country no Overture division heads opened nothing; it now
  opens by its code (`?place=ps`).
- **Waiting on the owner:** (1) the flip, after the 12:15 run: `bash .scratch/cloudflare/flip.sh >>
  logs/flip.log 2>&1` in Git Bash, then the `assets-switch` merge as above; (2) the DNS step of the R2 cache
  test; (3) the border-noise decision on the countries branch, then its merge.

### 2026-11-11, 10:25: the owner is away for a few days: "do it all yourself"

- **Border noise: decided and built** on `countries` (63994729): a point SC files only elsewhere while
  filing ground within 3 km under the place's own country keeps its own country only; ~150 noise entries
  go. Matsu stays under China because SC's own data says `CN-FJ, CN` there; an upstream report is
  drafted in `.scratch/countries/upstream-matsu.md`, not posted (it would go out in the owner's name).
- **R2 cache test: still blocked.** The classifier refused the DNS step again after the owner's go-ahead;
  it stays the owner's one command (`.scratch/r2-cachetest/run.py`).
- **Plan after the 12:15 run (Claude, woken at 12:50):** check the run logged `=== cloud ===` and
  `update done`; run `.scratch/cloudflare/flip.sh`; if it flips, merge `assets-switch`, `python
  tools/cloud_publish.py`, `--check`, and confirm the Worker's invocations stayed flat over the check; then
  merge `countries`, publish, check, push. Stop at the first failure and record it here.
- **After the run (15:52):** the 12:15 run died in its first minute on a Geofabrik read timeout
  (`osm_extracts.py fetch ontario`); Geofabrik answered again by 15:15 and the task was restarted by hand
  (`Start-ScheduledTask kk-SCOpenQuests`). That run counted the new extracts (Ontario 11-10, Europe 11-11; Toronto's snapshot carries `partsAged`), committed, pushed, and
  its cloud step synced (328 copied, 16 deleted). `cloud_publish.py --check`: 4,849 files equal.
  **The flip was refused to Claude by the auto-mode classifier ("Production Deploy")**, so the plan stops
  there: the `assets-switch` merge (a `wrangler deploy`) follows the flip, and the `countries` merge waits
  for both. The flip's gate is met for today; the owner runs, in Git Bash, any time before tomorrow's run:
  `bash .scratch/cloudflare/flip.sh >> logs/flip.log 2>&1` (it reads today's scheduler.log lines).
- **Evening, 21:03–21:15 (owner: "do it yourself, you have my permission"):**
  - **Flipped (21:05).** `flip.sh` passed its checks and switched Pages: skfd.github.io/sc-open-quests now
    redirects to street-complete-statistics.comentality.com (`logs/flip.log`).
  - **`assets-switch` merged and deployed (02:07 UTC), and it broke the home page.** Every file serves equal
    (4,848 of 4,849), a missing path is a real 404, but **`/` and `/index.html` both answer 307 `Location: /`**
    at the edge (`cfOrigin;dur=0`), a loop, also with a query. `wrangler dev` with the same config serves `/`
    fine, so it is something on the live side; a zone URL-rewrite rule (`/` → `/index.html`) would explain
    exactly this, but the token cannot read rulesets, so that is unconfirmed.
  - **The rollback was refused to Claude ("Production Deploy").** The owner was notified. To restore, in Git
    Bash: `cd cloudflare && set -a && . ~/.config/sc-open-quests/cloudflare.env && set +a && npx wrangler
    deploy --config wrangler.r2.jsonc` (the earlier R2 Worker; it served `/` fine).
  - **The merge is reverted on main (8824b9e2)**, so the 12:15 run syncs R2 only and does not redeploy the
    broken shape. Before trying static assets again: look in the dashboard (Rules > Transform Rules / URL
    Rewrite, Redirect Rules) for a rule on `/`; or set `"html_handling": "none"` and add a `_redirects`-free
    test on a separate hostname first.
  - **Not done, on purpose:** the `countries` merge waits until the site is healthy.
