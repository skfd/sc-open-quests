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

### Widget: decided (owner, 2026-11-11, evening), its own repo `~/Code/sc-open-quests-widget`

- **A native Android app on Google Play**, "Open Quests for StreetComplete", package
  `com.comentality.openquests` (permanent after the first upload). No Play developer account yet: a
  personal account made now must run a closed test with 12 testers for 14 days before production, so
  plan that before release.
- **Place only**: the big number is the place's open quests from this site's data, "as of <date>". The
  live "my answers today" line (the public OSM API returns `StreetComplete:quest_type` on changesets,
  checked) was offered and declined; the per-user non-goal stands.
- **First view: a city, optionally one quest type**, read from the live `data/history/<cityId>.json`
  (Toronto 36 KB brotli on the wire, ETag, `max-age=300`, checked 11-11). No pipeline change needed for
  v1. Neighbourhoods wait for a per-part series file; the small cacheable widget file waits for the R2
  data subdomain.
- **Defaults stated, not objected to**: Kotlin + Glance, graph drawn on the device (theme and size
  follow the widget), refresh once or twice a day after the ~13:00 publish with conditional requests,
  daily tail only with a missing day drawn as a gap, sizes 2x1 (number + 4-week chip), 4x2 (+ stacked
  map/resurvey sparkline), 4x3 (+ top three quests), tap opens the place on the site, tone follows the
  trend (as the share-card idea).
- **Load on this site**: every refresh is a Worker request against the 100,000 a day until the R2 data
  subdomain exists; two a day per widget is fine for thousands of installs, not for a hit.

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
- **Fixed, 21:53 (owner: "this is not a production deployment, we are in stealth mode"):** the R2 Worker
  redeployed from main's `wrangler.jsonc` (version 26629d07); `/` serves again; R2 synced back to main's
  `docs/` (the merged `index.html` and a stray `_headers` object replaced). Old address checked headless:
  skfd.github.io/sc-open-quests/?city=toronto lands on the new site with its query.
- **`countries` merged into main and published (22:00):** 361 files copied, 23 deleted; `--check` 4,937 equal;
  Palestine, Western Sahara, the Canaries, Ceuta & Melilla, US > Puerto Rico and Palestine > Gaza Strip open on
  the live site with no console errors. The installed engine is rebuilt (`regionids`). Worktree removed.
- **Still open:** (1) static assets: why `/` looped on the live domain (look for a zone rule on `/`), then
  retry on `assets-switch` (worktree `../sc-open-quests-assets`, kept); until then the R2 Worker and its
  100,000-requests-a-day cap stay; (2) the R2 cache test's DNS step; (3) the Matsu report upstream, drafted
  in `.scratch/countries/upstream-matsu.md`; (4) Wikidata English labels and OSM `name` tags for places.
- **Static-assets loop, one more probe (22:10):** the same assets config deployed as a separate Worker
  `sc-open-quests-assets-test` could not be reached, since the account has no workers.dev subdomain (an
  account setting, left alone); deleted. So zone rule versus assets behaviour is still undecided. The R2
  cache test's DNS step was refused again (DNS changes are refused whatever the context).
- **SC #7374 follow-up (22:30):** the country wiki-link issue was fixed upstream (eb447a03, the name is now
  URL-encoded) and closed; matkoniecz and westnordost created 5 redirects and invited us to add the rest.
  24 titles were still missing: 20 have a page under another name, 4 have none (BQ, BV, IO, SH).
  Creating them from Claude's Chrome (logged in on the wiki) was refused by the classifier. **The owner's
  step:** paste `.scratch/wiki-redirects/create-redirects.js` into the browser console on any
  wiki.openstreetmap.org page (createonly, never overwrites), then post `.scratch/wiki-redirects/reply-7374.md`
  on the issue if wanted. Judgment calls in it: AX → Sv:Finland (mirrors "Åland"), TF → a French-titled page,
  SJ → Svalbard only. The wiki's "Saint-Pierre and Miquelon" redirected to Saint Vincent and the Grenadines
  (since 2021); the owner chose to fix it, and the script does (only if the page still holds that text).
  The reply (three tables) asks the maintainers whether to write stubs for BQ, BV, IO, SH.
- **Static-assets loop: found (22:30).** A zone rule, not the assets: comentality.com's Transform Rule
  "Serve index.html for folder paths" (`ends_with(http.request.uri.path, "/")` -> path + `index.html`,
  added 2026-10-28 for the blog on OSS, `../comentality.com/docs/cloudflare-move.md`) is zone-wide.
  `wrangler tail` on the live R2 Worker shows `/` arriving as `/index.html` and `/vendor/` as
  `/vendor/index.html`. With `html_handling: auto-trailing-slash` the assets answer `/index.html` with
  307 to `/`, which the rule rewrites again: the loop. Fix on our side: `html_handling: "none"` (the
  edge only ever asks for `/index.html`); the owner's alternative is narrowing the rule to the blog's
  hosts in the dashboard (Rules > Transform Rules > URL Rewrite).
- **Static assets live (22:40), the site no longer has a request cap.** `html_handling: "none"` plus
  `docs/_redirects` (`/ /index.html 200`), so `/` works with or without the zone rule (checked both on
  `wrangler dev`); folders such as `/vendor/` are a 404, as they were. Main had the revert reverted,
  then a9bb452e; deployed by `tools/cloud_publish.py` (version e2336314, 348 files uploaded). Live: `/`,
  `/?city=toronto`, `HEAD /`, `/index.html` all 200; a missing path and `/_redirects` 404;
  `cloud_publish.py --check` 4,938 of 4,938 equal, and it now fetches `/` too; `.scratch/spike/check.py`
  no page errors on Toronto, Compare, Map and London; skfd.github.io/sc-open-quests/?city=toronto lands
  on the new site with its query. **The Worker's invocations stayed flat** over the check and the
  headless runs (03:00 UTC hour: 8 before, 8 after about 5,100 requests), so asset requests are free.
  Merged into main (2a05c008), worktree and branch removed, `.claude/launch.json` now runs
  `cloudflare/wrangler.jsonc`. Way back: `npx wrangler deploy --config wrangler.r2.jsonc` in
  `cloudflare/`. The 12:15 run deploys this shape from now on; watch `=== cloud ===` for "site deployed".
  The zone rule can stay; narrowing it to the blog's hosts is optional and the owner's.
- **The world count never ran (found 22:55 on 11-11).** `logs/planet-count-2.log` ends at 2026-11-10
  23:42: the cut finished (128 files, 32,827 s, 87 GB kept in `.scratch/planet/world/cut/`), the planet
  slice was deleted, and the canary `f21` failed in 18 s: the JVM could not commit 9 GB ("The paging file
  is too small", `.scratch/planet/world/files/f21/log.txt`). The untracked `hs_err_pid65112.log` written
  off above as "not ours" is this crash. Not a heap limit: the machine's commit limit is 104 GB (88 RAM +
  16 pagefile) and about 70 GB is committed with no process showing it (top process 4 GB), so only about
  34 GB is left for engines, against the chain's 40 GB canary and 2 x 30 GB count. A rerun of chain2.sh
  goes on from the canary (cut and notes are done).
- **World count restarted (23:02), fitted to memory (owner: "be adaptable to memory").** `world_cells.py
  count` (f780c44c) now starts an engine only when Windows can commit its heap plus 4 GiB
  (`commit_free_gb`, GetPerformanceInfo); each engine commits its heap up front (`-Xms` = `-Xmx`) so the
  next reading counts it; up to `--engines` at once, so one engine while the hidden 70 GB is held, two
  when it is not; a file refused memory is queued again (5 times at most); with none of ours running and
  no room for 2 h, the rest fail. Crash files go to the file's folder. `.scratch/planet/chain3.sh`
  (hidden, log `logs/planet-count-3.log`): canary f21 at 30 GB, then every file at 30 GB, a failed file
  once more alone at 40 GB, then `report` and `oracle`. Rerun: the Start-Process line in its header. It
  waits out the 12:15 run by itself. Expect about 13 h on one engine, less if memory frees up.
  **Not on the site, by design:** this run writes `.scratch/planet/world/REPORT.md` and `oracle.log`
  (the world's totals and two checks against the cities and the stream); publishing world numbers is
  DESIGN.md, "Place statistics for the whole world: the final product", not built.
- **World count stalled overnight at 19 of 128 files; restarted 15:09 on 11-12.** One engine at 30 GB did
  f0–f17 and f21 at about 3 min each, until midnight. Then something outside the count took about 6 GB, so
  commit headroom stayed at 28–29 GiB until at least 04:00, below the 34 an engine needs. After 2 h with
  none running, all 109 left failed, and so did the 40 GB pass. `report` then crashed on the first file
  with no snapshot (StopIteration), and no REPORT.md was written; chain3's closing "report and oracle
  written" line is printed either way. At 15:08 headroom was 37 GiB, so chain3.sh was started again
  (old log kept as `logs/planet-count-3a.log`). It waits out the side-by-side window until 15:40, then
  about 5.5 h if memory holds. If it stalls again the same way, the 2 h give-up is what to change.
- **SC #7374 wiki edits done (2026-11-12, 05:54 UTC, owner's go-ahead):** the 20 redirects were created as Skfd
  (revisions 3114184–3114203) and "Saint-Pierre and Miquelon" now points to Saint-Pierre-et-Miquelon (3114204).
  Checked: 25 of the 29 titles redirect, and only BQ, BV, IO and SH are missing. The reply (now in past tense) sits
  filled in the issue's comment box in Chrome for the owner to post. Next, once the maintainers answer:
  stubs for the four, or not.
- **World count: 122 of 128 done (checked 22:20 on 11-12); the last 6 are a North Pole bug, not memory.**
  f96, f108, f109, f116, f119 and f127 (the files whose cells reach latitude 90) all die with "Latitude
  90.0000168 ... is not a valid position". Traced with the new `-Dopenquests.trace=1` (set in JAVA_OPTS):
  `LatLonRaster.<init>` called from `FastAddIsAmenityIndoor.getApplicableElements` (FastAddIsAmenityIndoor.kt:60)
  builds its raster on a box padded past the pole. Next: clamp that box to [-90, 90] (as AreaPass.kt:127
  already does), rebuild, rerun chain3.sh (done files are skipped), then `report` and `oracle`. Not fixed yet.
- **World count done (23:08 on 11-12): all 128 files, 2,244 cells, 10,986M nodes.** The pole bug is fixed
  (826ac314: `rasterBox` holds the house number and amenity rasters 0.001 degree short of latitude 90; sc/
  untouched; PoleRasterTest). The six pole files ran alone at 26 GB (only 31.6 GiB could be committed),
  80–115 s each, log `logs/planet-count-4.log`. Results in `.scratch/planet/world/`:
  - REPORT.md: every open quest in the cells 1,716,132,183; app default 577,700,606. All 146 counted
    cities against their published 11-08 counts: most exactly equal, the worst Regina −0.42% (−378), Oshawa
    −0.25%, Grande Prairie −0.22%. Their counts are from 21:21Z, a later state than the planet's.
  - oracle.log (the cells against the stream, tier-1): 362,709 matches in both; 569 only in the stream, 566 of
    them at an open note; 0 only in the cells; **3 unexplained** (2 AddPathSmoothness near 43.22,−2.02, 1
    CheckShopExistence near 45.58,9.26).
  The 87 GB cut (`.scratch/planet/world/cut/`) is still kept: chain3 deletes it only after both checks pass,
  and that call is the owner's. Still not on the site, by design (DESIGN.md, "Place statistics for the whole world").
- **World cut deleted (23:15 on 11-12, owner's go-ahead):** the 128 `.osm.pbf` files in
  `.scratch/planet/world/cut/` (87 GB) are gone, as `count --delete-cut` would have done; the extract configs
  and `cut.done` stay. The counted files, REPORT.md and oracle.log are untouched. Recounting the world now
  needs a new planet slice and cut.
- **World place index: started 11-12, 23:30 (owner: "World place index" before pages and R2).** Today's
  world run counted only the 147 cities' outlines as parts; REPORT.md says "Places with a number: 0 of 0".
  Measured so far, nothing built:
  - `data/overture/world/` (2026-10-21.0, the name layer's) has every place's bbox but **no outlines**. The
    outlines are 4.6 GB on Overture's S3 (division_area geometry, 8 files; parquet footers read).
  - **Countable places** (own OSM source r/w, an area; the owner's rule): 1,069,532. Localities 553,827,
    neighbourhoods 322,896, microhoods 89,205, macrohoods 46,301, counties 31,606, localadmin 21,502,
    regions 3,923, countries 219, dependencies 53. localadmin and dependency are new to world_cells.
  - **Against the 2,244 cells of the 11-08 run** (`.scratch/world-places/rehearse.py`, bbox only):
    1,141,472 part entries; the worst file is f97 with 49,840, the worst cell f97c2 with 16,891.
    16 places have a bbox wider than 180° (Russia, the US, Fiji, Kiribati, NZ, Antarctica and some of
    their regions/counties), and 859 have no country or a placeholder one.
  - **Plan (advisor-checked):** (1) pull the outlines once into a local parquet, staying on 2026-10-21.0 so
    ids join the name layer. (2) Build the world's places.json and geo/ without `places()`'s single query:
    pick each division's area from the local no-geometry file, stream geometry per country, and shard geo/
    by id prefix. Make plan's part pick a bucketed lookup, not 2,244 x 1M comparisons. (3) Check: the world
    output filtered to DE equals `.scratch/world-de/places.json`; every id is in the name layer; and a small
    end-to-end count from a store extract shows places with numbers, with the osm-<city> check still
    holding. Also check the single-`country` assumptions (places.json, plan.json, city_parts, report) and
    the wide-bbox places in Polygon.contains. (4) Only then a new planet slice, cut and count, in a **new**
    `--out` (never `.scratch/planet/world`: its done.json files would skip every file). That run is its own
    step with the owner: about 9 h cut plus about 7 h count, on memory that stalled twice.
- **World place index built and tested (11-13, 00:50); the planet run with places is next, the owner's step.**
  - `.scratch/world-places/world/places.json` (395 MB) and `geo/<2 digits>/<id>.geojson`: 1,069,532 places,
    built in 26 min from `data/overture/world/division_area_outlines.parquet` (`overture_pull.py 2026-10-21.0
    --outlines`, 3 min). Commits 2dc9cb4d and the report fix after it.
  - **Checks:** (1) the world's DE subset, and DE through the new code, equal `.scratch/world-de` exactly:
    40,520 places, every field, every outline. (2) Id join (`.scratch/world-places/idjoin.py`): all but 12 are
    in the name layer; the 12 are XR/XT/no-country places (Spratly reefs and the like) that the name layer
    leaves out, so they would be counted but have no page. (3) **Latvia end to end** (`.scratch/world-places/lv.sh`,
    the 10-27 extract, the world's places.json as parts): Riga's whole-city count, its cells and its Overture
    place are all 82,390 (exact); 3,183 places have a number; Latvija 2,068,870 (default 873,590). The same
    file cut into 14 cells and into 2 gives the same number for every place but 4, which differ by the same 2
    quests (AddMaxHeight, AddOneway, in Dobele). The cells' own totals differ by the same 2 (2,104,970 and
    2,104,972), so the places only inherit the known cell effect, well inside 0.1%
    (`.scratch/world-places/invariance.py`). 27k part entries and 8.68M outline points fit under -Xmx8g; the
    planet's heaviest file loads 9.43M points (f47; f97 has the most places, 49,091; `points.py`), so the
    places add about what Latvia carried to a 30 GB engine. (4) **The antimeridian** (`antimeridian.py`):
    none of the 16 wide places has a point off the globe or an edge longer than 180 degrees, no place has
    xmin > xmax, and points either side of 180 land right (Uelen and Anadyr in Russia; Nome, Adak and Attu
    in the US; Taveuni in Fiji; Tokyo and the open Pacific in none).
  - **For the planet run** (owner's go-ahead and timing; nothing started): a new out dir (for example
    `.scratch/planet/world-places/`), the world's places.json copied in, then plan (same nodegrid and `--cities`
    as chain2), a new planet slice and cut (about 9 h), notes, count (about 7 h at 30 GB, longer if part
    polygons slow the big files), report. Keep `.scratch/world-places/world/geo/`: places.json points there. A
    wide place's box spans every longitude, so it is tested in every cell of its latitudes: correct, slower.
    Make the canary the file with the most outline points (f47), not the one with the most cells.
- **Planet count with places: running since 11-13, 01:55 (owner: "continue").** `.scratch/planet/chain4.sh`
  (hidden; log `logs/planet-places.log`; rerun with the Start-Process line in its header, every step skips
  what is done). Out dir `.scratch/planet/world-places/`. It uses the 11-08 slice again (same history file
  and diffs 5165–5170), the 11-08 node grid and chain2's plan arguments, with the world's places.json added.
  Its plan was checked to give exactly the 11-08 run's 128 files and 2,244 cells, so the cities (archive
  11-08) and the oracle compare like for like. Then: slice (about 2.2 h), notes, cut (about 9 h; the slice
  is deleted after), the canary f47 at 30 GB, every file at 30 GB on one or two engines as memory allows,
  with a 10 h give-up (`count --give-up-h`, new), and a failed file retried alone at 40 GB. Then report and
  oracle. Expect the count from about 13:30 and the end in the evening, longer if memory dips.
  The cut stays after the count, for the owner to delete once the checks pass.
- **(Done; superseded by "Where the stream stands" below.) The stream: its state, being prepared (11-13, from 12:40; owner: "prepare whatever streaming prototype would
  need to progress"; the full count is the reference for data and for speed).** DESIGN.md, "The stream: its
  state". On main (merged from branch `stream`, worktree `../sc-open-quests-stream`, kept while the
  test below runs from it): engine `--dump-state` (every match plus the date each waiting quest opens; built in
  the worktree only: **main's engine is not rebuilt while chain4 runs**), `world_cells.py count --state`,
  `tools/stream/stream.py` (state, day diffs, check), `tools/stream/proto/` (the first scripts, out of
  `.scratch`). **Running:** `tools/stream/europe-test.sh` (hidden, log `logs/stream-europe.log`), which waits
  for chain4's oracle line, then counts the Europe clips 11-08..11-13 for europe-west and streams diffs
  5171-5175 against them; checks in `.scratch/stream/europe-west/check-*.txt`. It first holds days 08 and 09
  against the old engine's dumps in `.scratch/diff-flips/` (`stream.py tsv`): the proof that `--dump-state`
  changes nothing else, needed before main's engine is rebuilt. Restarted 13:12 with a safe wait (the
  chain's oracle line, or its log still for an hour) and an exit line, "stream europe ended (code)". Europe clips 11-08..11-13 pinned.
- **Planet count with places done (11-13, 16:34).** `.scratch/planet/world-places/`: REPORT.md (every open
  quest 1,716,132,183, app default 577,700,606, as 11-12's run; places with a number 1,016,910 of 1,069,532)
  and oracle.log (the same 3 unexplained as 11-12). Count 07:38-16:33, 4.4 h of it engine. The cut (87 GB)
  is kept: the world seed reads it; deleting it is the owner's call, and it must go before 12-07.
- **The Europe test passed (11-13, 16:35-17:04; chain4 ended 16:34, oracle written).** DESIGN.md, "The Europe
  test: the result". `--dump-state` equals the old engine's dumps exactly (days 08, 09) and costs no visible
  time; **main's engine rebuilt with it (`installDist`, 17:06)**. Tier 1 streamed five days exact for nodes
  and ways, ageing included; only 1-3 relations differ. Tier 2 (kept from the seed) drifts about 700 a day,
  97% on touched elements. A day costs 3-4 min, two thirds of it Python reading the planet diff. The worktree
  `../sc-open-quests-stream` and branch `stream` are removed; `europe-test.sh` runs from main (reruns skip
  what is done; delete `check-*.txt` to rerun the stream part). The Europe clips stay pinned while tier 2 is
  built against them.
- **The stream, evening of 11-13 (DESIGN.md, "Every row checked..." and "Tier 2 in `apply`").** `check` now holds
  every tier-1 row; `--dump-state` dates the 0.5 and 2 settings (main's engine rebuilt, snapshots unchanged
  with the option off, pass about 12% slower; the 0.5/2 drift is gone). Tier 2 is in `apply --tier2-clip`
  (`tools/stream/tier2.py`, `europe-t2.sh`): five days, tier 2 differences 130 against 3,580 without it, tier
  1 exact on four days, 5-7 min a day. Left: area quests' dates (about 20 a day here, skipped for the first
  seed), the splice bringing in recount disagreements (36 AddHousenumber on 11-12; two Dublin boundary ways
  on 11-13, not traced: try the delta form), and a store answering "the map data of these boxes at day D"
  (`tier2.map_data`). Stream state dirs: `.scratch/stream/europe-west/` (tier 1, rerun with dates; first run
  in `run1/`) and `t2/` (tier 2; first run in `t2/run1/`).
  **Next, in order:** the delta form and the Dublin ways; then the
  world seed, `world_cells.py count --state` over chain4's kept cut (`.scratch/planet/world-places/cut/`,
  87 GB; 4.4 h of engine as chain4's count, up to 9 h on the clock; an estimated 50 GB of state), started early on a day
  the owner is away so it ends before midnight; then a world state store
  (sorted on disk plus an overlay) and the node store again (`planet.loc`, 107 GiB). Disk: 262 GB free; the cut
  (87 GB) goes after the seed; the planet job of 12-07 needs about 170 GB. A world reference beyond 11-08 needs
  a second planet count at a later instant: the owner's call.
- **Where the stream stands (11-13, 19:45): nothing running; the owner decides the next machine step.**
  Read DESIGN.md "The stream: its state (2026-11-13)" from the top: it holds the method and every result.
  - **Built, on main, 13 commits not pushed (push asked, not answered):** engine `--dump-state` with dates for
    all three resurvey settings (main's engine rebuilt; option off leaves snapshots identical); `world_cells.py
    count --state`; `tools/stream/stream.py` (`nodes`, `ways`, `count`, `seed`, `apply [--tier2-clip]`, `check`,
    `tsv`); `tools/stream/tier2.py`; `tools/stream/europe-test.sh` (tier 1) and `europe-t2.sh` (tier 2), both
    rerunnable (each skips what is done; delete a state dir's `check-*.txt`, `state.json` and `rows.npy` to
    replay it). Repo check (`python -m unittest`) passes; 86 engine tests pass.
  - **Europe, five days (11-09..11-13, europe-west), against a whole count each day:** tier 1 exact in every
    field on four days; tier 2 with the recount 130 wrong of 1.39M after five days (3,580 without). 5-7 min a
    day, of which the engine 23-36 s and reading the planet diff in Python 2-2.5 min.
  - **Known gaps, in the order to take them:** (1) the splice brings the recount's own disagreements in: 36
    AddHousenumber on 11-12, and on 11-13 ways 71455532 and 168339841 on Dublin's boundary, which the recount
    counts and the whole count has no row for (the engine's point test says inside; cause not traced). Try the
    delta form (apply the recount's own day-to-day flips; DESIGN "The stream, tier 2" found it exact). (2) Area
    quests have no dates (about 20 a day here): skipped for the first world seed, by decision. (3) `tier2.map_data`
    returns the whole day clip; a world needs a store answering "map data of these boxes at day D". That
    store, not the engine, decides whether the stream beats the full count (the engine's area runs were 1-8 s
    a day against about 25 s for these cities whole).
  - **Owner's calls:** when to run the world seed (`world_cells.py count --state` over
    `.scratch/planet/world-places/cut/`: about 5 h of engine with the new dates, up to 9-10 h on the clock;
    state about 25% bigger than first estimated, so about 60 GB), best started early on a day the owner is
    away so it ends before midnight; then deleting that cut (87 GB), which must happen before the 12-07 planet
    job (about 170 GB needed; 242 GB free now). A world reference past 11-08 needs a second planet count.
  - **Housekeeping:** Europe clips 11-08..11-13 stay pinned in `~/Code/.osm-data/europe/pins.json` while tier 2
    is worked on; unpin when done. `.scratch/stream/` is 13 GB (the way store 3.7 GB and node index 2 GB in
    `europe-west/t2/`, the node index again in `europe-west/`). `hs_err_pid65112.log` deleted (11-13, 19:55).
- **The owner's answers (11-13, 19:55):**
  - **World seed: hold.** Not scheduled. Work on the stream's code gaps first (the delta form, the Dublin ways,
    the 36 AddHousenumber), then ask again when to start it (a morning, a day the owner is away).
  - **The cut (`.scratch/planet/world-places/cut/`, 87 GB): delete once the seed is checked**, i.e. as soon as
    the seed's rows agree with the 11-08 count; no further ask needed. Still must be gone before 12-07.
  - **Second world reference: from the 12-07 planet.** Count the world from the monthly job's download, stream
    11-08 -> 12-07, and check against it. No dedicated earlier run.
  - **Push: yes**, the 14 commits pushed.
- **Tier 2 in the delta form: built and run (11-13, 20:05-20:46).** DESIGN.md, "Tier 2 in the delta form" and its
  result. `stream.py apply --tier2-old-clip`, `tier2.delta`, `tools/stream/europe-t2d.sh` (state
  `.scratch/stream/europe-west/t2d/`, 6.6 GB; log `logs/stream-t2d.log`), `tests/test_stream_delta.py`. Five days:
  **tier 1 exact on all five** (the splice had 11 wrong on 11-13); tier 2 differences 99 on 11-13 against the
  splice's 130, all but one of them area quests ageing; about 40 s a day more. The Dublin ways are traced: their
  centres lie 3-4 mm from Dublin's boundary, and the dump's 1 cm rounding puts them inside where the engine said
  outside; the delta keeps them out (a full fix, the engine given the real outline, is not built).
  **Gaps left:** area quests' dates (the first world seed goes without them, by decision); the store answering
  "map data of these boxes at D and D-1". The world seed has no code blocker now: ask the owner when.
- **World seed running since 11-13, 21:29 (owner: "this project can disregard nightly quiet hours. keep working ...
  try to work autonomous").** `.scratch/planet/chain5.sh` (hidden; log `logs/planet-seed.log`; rerun with the
  Start-Process line in its header, every step skips what is done): `world_cells.py count --state` over
  `.scratch/planet/world-places/cut/`, canary f47 at 30 GB, then every file on one or two engines as memory allows,
  a failed file once more at 40 GB; then `.scratch/planet/seedcheck.py` (each file's out-state snapshot equal to
  its count's, every state.bin whole records) and, only if that passes, the cut deleted, as the owner decided.
  Expect about 5 h of engine, more on the clock if memory dips. Meanwhile: area-quest dates, in a worktree (main's
  engine is not rebuilt while the seed runs from it).
- **Area quests' dates: built, tested, waiting for the seed to run on Europe (11-13, 22:00).** DESIGN.md, "Area
  quests' dates". Engine commit 0aac5d3d (`AREA_DUE_DAYS` 64, `AreaPass.dateCandidates`, `AreaDatesTest` passes);
  **not installed yet**, because the world seed runs from `engine/build/install`. `tools/stream/europe-area.sh` is
  running hidden (log `logs/stream-area.log`): it waits for chain5's "seed chain ended", then installs the engine,
  runs every engine test, recounts Europe 11-08 with dates into `.scratch/stream/europe-west/area/`, writes
  `area/areacheck.txt`, and streams the five days in `t2a/`. Expected about 03:30 plus an hour. The world seed
  itself has no area dates (its cut is deleted when its check passes, as decided); the 12-07 reseed will have them.
  The seed check (`seedcheck.py`) now also holds each file's open, unhidden state rows per quest against its
  snapshot (exact on f47 apart from the note quests, which are no rows).

- **World seed done (11-14, 03:01): 128 files, 2,011,107,291 state rows, 48.3 GB; the seed check passed with 0
  problems, and the 11-08 cut was deleted (271 GB free).** 19,807 s on the clock, one engine at a time almost
  throughout (5 GiB free beside one). The seed lives in `.scratch/planet/world-places/files/fNN/state.bin`
  (with `state.bin.json` sidecars, `state-done.json` and the `out-state/` snapshots); the cut folder keeps only its `extract-*.json` configs. No area
  dates in it (as decided). `europe-area.sh` has started on its steps (engine installed 03:04).
- **Area quests' dates validated on europe-west (11-14, 03:51); tier 2 has 1 difference in 1.39M after five
  days.** DESIGN.md, "Area quests' dates", the result. Engine installed on main, every engine test passes. The
  11-08 recount dated all 1,462 candidates (0 undated), its dump otherwise identical to the old one; of 108 area
  quests opening on untouched ground over 11-09..11-13, 100 dated on the day, 0 wrong, 8 opened by neighbours
  (undatable), no spurious dates. Streamed from it in the delta form (`.scratch/stream/europe-west/t2a/`): tier 1
  exact, tier 2 0/0 on three days and 1/0 on 11-12 and 11-13 (t2d without dates: 1/98), the one being a recount
  disagreement (w1577774915 AddHousenumber). **The stream's known gaps are now: recount-versus-whole
  disagreements (AddHousenumber on 11-12, the Dublin boundary ways), and the world store** ("map data of these
  boxes at D and D-1", plus a state store for 2.01 billion rows that do not fit in memory).
- **The world seed's files, measured for a state store (11-14, 04:08; `.scratch/planet/seedkeys.py`, log beside
  it).** 128 files, 2,011,107,291 rows (48.3 GB), **1,061,205,063 distinct elements** (116.9M nodes, 942.7M ways,
  1.7M relations); **only 95 keys lie in more than one file** (112 extra copies), so the files partition the world
  by element almost exactly, each element routed by its position to its file's `rect` (plan.json). Rows inside a
  file are not sorted by key (written per engine thread): sorting a file of 18.6M rows takes about 16 s; reading
  and sorting all 128 took 900 s. Files run from 31,775 to 16.8M elements (median 8.7M).
- **Checks after the area-date run (11-14, 04:20):**
  - **The horizon rolls inside the rectangles, seen:** the t2a recounts print "area dates" lines at both clocks
    (`t2a/work/t2/engine.log`, `.../old/engine.log`; e.g. dublin-0 110 and 104 candidates, all dated), so a
    touched element's date is recomputed by the delta form, not left from the seed.
  - **The 12-07 reseed will date area quests:** `world_cells.py count` runs the engine with its default area
    unit, `CITY` (Main.kt), each cell being one "city" (`files/fNN/cities.json`); dating is on in that unit. Its
    cost is not measured on a world cell (a cell's area run is 1-11 s; europe-west's 1,462 candidates took 5 s;
    the world, about 300 times the rows, is guessed at under half an hour over all 128 files).
  - **Old stream runs freed:** `t2/`, `t2d/` and `run1/` keep only their checks and logs (16 GB freed); their
    scripts (`europe-t2.sh`, `europe-t2d.sh`) cannot resume them now (no `ways.npz`, `touched.npy`). `t2a/` is the
    only tier-2 state left, at 11-13, with the only way store.
  - **Diffs kept for the world stream:** the 12-07 planet job applies the day diffs to the history file and
    deletes them, and retires `history-261102.osh.pbf`. The diffs from 5165 are hard-linked into
    `.scratch/planet/diffs-keep/` (no disk until the store's copies go); **run
    `powershell -File .scratch\planet\keep-diffs.ps1` again before 2026-12-07 07:30** to link the newer ones.
    The history file is not linked (170 GB would stay held through the job, which needs about 170 GB free).
- **The world state store, started (11-14, 04:40).** DESIGN.md, "The world state store". `tools/stream/world_state.py
  sort .scratch/planet/world-places` (test `tests/test_world_state.py`) sorts every seed file in place by (key,
  quest, kind), saves each file's sorted key list (`files/fNN/state-keys.npy`, about 8.5 GB in all), and writes
  `world-state.json` (each file's rect, rows, key range) and `world-state-shared.npy` (the keys in two files).
  Ran 04:17-04:31 (log `logs/world-state-sort.log`); safe to rerun (a sorted file is skipped).
- **For the owner (evening of 11-14), to ask as a wizard:**
  1. **The node store for a world day (`planet.loc`, 107 GiB).** Tier 1 for the world needs it. It is built from
     `history-261102.osh.pbf`, which the 12-07 planet job retires, and it would leave about 165 GB free where that
     job needs about 170 GB. Either build it now and stream the 11-08 seed through the next weeks (deleting it
     before 12-07, then building it again from the new file), or wait and build it once from the 12-07 file,
     streaming from the 12-07 seed (the 11-08 seed then only a rehearsal).
  2. **Tier 2's store for the world** ("map data of these boxes at D and D-1"; estimated about 300 GB, more than
     the disk has beside the 12-07 job): built here, an Overpass instance, or later.
  3. **Push:** about 15 commits since the last push.
- **World state store sorted (11-14, 04:31):** 832 s, every row kept, 95 shared keys; finding a day's touched keys
  in all 128 files takes about 30 s (DESIGN.md, "Sorted"). The store is ready for tier 1 of a world day, which now
  waits on the node store (owner's question 1).
- **The last tier-2 row traced (11-14, 05:00):** `w1577774915 AddHousenumber` is one of about 45 houses mapped on
  11-12 over addressed buildings in London; AddHousenumber hands shared address nodes out in map-data order, which
  may differ between a rectangle and the whole city (and in the app, by what it downloaded). Tested: at a 1,500 m
  ring the recount agrees on all 37 (the 36 and this one) but adds 3 others; so it is mostly how far the map data
  reaches. DESIGN.md, "Tested". The world store must serve the ring the recount needs. DESIGN.md, "The one tier-2 row left, traced". 
- **The sorted seed read back (11-14, 05:10):** `seedcheck.py` again, 0 problems. Every row lies in its file's
  `rect` but 9 (6 keys, on the edge by rounding; `.scratch/planet/seedroute.py`, log beside it); the 95 keys in two
  files are all relations, each file placing its own part's centre. So: route nodes and ways by position, look
  relations up by key in every file.
- **The world's tier 1, built and checked on Europe (11-14, 05:12-06:00).** DESIGN.md, "The world's tier 1 on five
  days". `world_state.py subset/apply/check` and `tools/stream/world-europe.sh`: copies of the world files for
  Lisboa, Dublin and London streamed five days through the world's cells. **Row for row the same as europe-west's
  own tier-1 stream** (only tier 1's known limits left: ways whose nodes moved, untouched relations). The world seed
  itself equals europe-west's 11-08 count on all 5,405,119 shared tier-1 rows. Files now take a day by merge, not a
  sort (31 s to 1 s a file); a rerun with the merge is running (log `logs/world-europe-2.log`, the first run kept in
  `.scratch/planet/world-test-sort/`). **What a world day lacks now:** the world's node locations (`planet.loc`,
  owner's question 1) and tier 2 (question 2).
- **Merge rerun done (11-14, 06:30):** the same rows as the first run on all four files; a world file's update is now
  4.0 s (DESIGN.md, "Rerun with the merge"), so a world day's file step is at most about 8.5 min. The first run's
  copy (`world-test-sort/`) is deleted; `.scratch/planet/world-test/` holds the merge run at 11-13 (2 GB copies plus
  the 2 GB node index). **Nothing runs now.** The next machine steps wait on the owner's three questions above.
- **The owner's answers (11-14, 06:35):** node store: **build it now** (from `history-261102`, stream the world
  from the 11-08 seed through the coming weeks, delete it before 12-07 07:30, then build again from the 12-07 file);
  tier 2's world store: **design it, build later** (measure a store's size on Europe; the world runs tier 1 only
  until the disk allows); push: **yes**.
- **The world's stream, started (11-14, 12:22).** `.scratch/store/planet.sh` is building `planet.loc` (log
  `logs/planet-loc.log`, about 40 min, 107 GiB), and `tools/stream/world-days.sh` (hidden, log
  `logs/world-days.log`) waits for it, then makes `.scratch/planet/world-stream/` of hard links to the seed's files
  (replaced whole on change, so `world-places/files/` keeps the 11-08 seed; the stream's own rows cost about 48 GB
  once every file has changed), and applies every kept diff from 5171 on, tier 1, with the node store kept current
  in place (`stream.DenseLocations`; `planet.loc.state` holds its instant). Days 11-09..11-13 are checked against
  europe-west's whole counts on the files they reach. Rerun to catch up on later diffs (run `keep-diffs.ps1` first;
  the script does). **Disk:** about 290 GB free before; `planet.loc` 107 GiB plus the stream's rows 48 GB leave
  about 130 GB, so **`planet.loc` must be deleted before the 12-07 planet job (07:30)**, which needs about 170 GB.
- **Disk (11-14, 14:05):** the owner cleared space (343 GB free now, with `planet.loc` and the world stream's rows)
  and plans 100 GB more in about a month. `planet.loc` no longer has to go before 12-07 for room (343 - 170 still
  leaves it), though it must be rebuilt from the 12-07 history file anyway. The tier-2 world store (DESIGN.md, "Tier
  2 for the world") fits now; next are its two measurements on europe-west: (a) the cover without a way index, (c) a
  z14 tile store's size and a day's read and update.
- **The world's stream is at 11-14 (14:08).** DESIGN.md, "The world's first day" and "Caught up to 11-14". Six
  planet days, 8-14 min each, tier 1 only; Europe checks show only tier 1's known limits (ways whose nodes moved,
  untouched relations). The state grows by about 0.3M rows a day: **hold it against the 12-07 count**. To take
  later days: rerun `tools/stream/world-days.sh` (hidden, its Start-Process line), which links new diffs and applies
  what is not applied; not scheduled (a daily task would be standing config: ask the owner). Disk: the stream's own
  rows about 48 GB beside the seed's.
- **Tier 2 without the way index: the same result (11-14, 14:50).** DESIGN.md, "Measurement (a)". On europe-west's
  five days the area quests are identical to t2a's; a few tier-1 rows of untouched ways keep a position up to 1.2 m
  old. The world's tier 2 then needs no 280 GB way index, only the relations' member ways and the map data store.
  **Next: measurement (c)**, a z14 tile store of the europe-west clip (size against the clip, cut time, a day's
  update and read, the recount on its data equal to the clip's).
- **Measurement (c), the tile store, started (11-14, 17:00).** First the tile rule alone, before any store
  (`tools/stream/tiles.py`): `geom` reads a clip's node locations, way refs and relation members into numpy
  (`.scratch/tiles/geom-12/`, `geom-13/`); `extract` writes what the z14 tiles under the rectangles and the 300 m ring
  would hold (nodes in the tiles; ways whose segments cross them, complete; relations with a member there, and
  their member ways whole as a separate "relation store"); `recount` and `compare` hold it against the t2n
  recount of 11-13 and 11-12, frozen in `.scratch/tiles/ref/` (cities, cells, both `state.bin`). The engine picks
  an area's ways by a node in the padded box and orders map data by id hash (AreaPass.kt), so equal rows are
  expected. Then the store's layout from the tile population (pack files with an index, not a file per tile).
- **The tile rule holds (11-14, 17:25).** The 103 rectangles of t2n's 11-13 (dublin-0 12x7 km, the rest small): 331
  z14 tiles under them and the 300 m ring; the extract (8.76M objects, 105 MiB, against the 1.75 GB clip) recounted
  **row for row equal** to the recount on the whole clip, 1,116,244 rows, 0 different; on 11-12 (D-1) the same,
  1,114,046 rows. The engine took 22 s on the extract against 35 s on the clip. Leaving the relation store's member
  ways out (7% fewer nodes) changed nothing on this day either; it stays in, for the multipolygons that reach far.
  Prototype timings: `geom` 8 s for node places (C++), 342 s for way refs (Python); `attrs` 930 s (Python, mostly
  ways' tags). Next: the store cut from 11-12, its size and tile population, and the same check through it.
- **The store, cut and read (11-14, 17:45).** DESIGN.md, "Measurement (c)". Europe-west 11-12: 59,026 tiles, 1.86 GiB
  (clip 1.63 GiB) plus a 218 MiB relation store; read back for t2n's rectangles, the recount is 0 different (D-1).
  The day's update (`tilestore.py update`: the reached tiles rebuilt from their old payloads and the diff, into a new
  generation; no way index, a moved node's ways found in its old home tile) equals a fresh cut on a small clip
  (`tests/test_tilestore_update.py`). Running now (`.scratch/tiles/`, logs `logs/tiles-*.log`): the fresh cut of 11-13
  (`store13/`) and the update of `store/` by diff 5175; then compare them and recount D through the store.
- **Measurement (c) done (11-14, 19:05).** DESIGN.md, "Measurement (c)". The tile store reproduces the clip's tier-2
  recount exactly on one day: D through the updated store 1,116,244 rows and D-1 through generation 0 1,114,046 rows,
  0 different each; the updated store equals a fresh 11-13 cut on every tile not touching the clip polygon's edge.
  One bug found and fixed on the way (a relation held in a tile only by an untagged label node). Size: 1.27x the PBF in
  all (about 108 GB for the planet), plus a way-tiles index that should shrink. **A day rewrites 23% of the bytes in
  4.4% of the tiles** (2,591 of 59,026, the dense city-centre ones; the clip is 32 European city boxes, all urban),
  so D-1 costs about 0.46 GB a day here; smaller tiles where data is dense would cut it. Speed is the Python
  prototype's (update about 9 min a day, read 34-45 s of which 31-41 s writing the PBF); a world store needs compiled
  code. Rerun: `tools/stream/tilecheck/` (`chain-z.sh`, `day12.sh`).
- **For the owner (evening of 11-14), to ask as a wizard:** what next for tier 2 of the world: (a) measure smaller
  tiles for dense ground first (z15/z16 split; a Python rerun of the cut and the update, about an hour); (b) build the
  store for real in Kotlin beside the engine, cut from the 12-07 planet; (c) leave tier 2 and keep the world on tier 1
  until the disk grows. And: push the commits since the last push.
- **The owner's answers (11-14, 19:10):** next for tier 2: **measure smaller tiles first** (z15/z16, then an
  adaptive split from the two); **push: yes**.
- **Smaller tiles, running (11-14, 19:07).** The zoom is a setting now (`OPENQUESTS_TILE_Z`; a store records its own
  and refuses another), the update's region is the clip polygon (`--polygon`), tests pass at z14/15/16.
  `tools/stream/tilecheck/chain-z.sh 15` and `16` (logs `logs/tiles-z15.log`, `tiles-z16.log`) cut, update and check
  stores at z15 and z16; then `chain-z.sh 14 update-only` reruns z14's update with the polygon, and
  `tools/stream/tilecheck/adaptive.py .scratch/tiles .scratch/tiles/ref/cities.json` sets uniform z14/15/16 against an adaptive split (z16 children of
  any z14 tile over 64-512 KB): tiles, bytes, the day's write, the read for the day's rectangles.
- **Smaller tiles measured (11-14, 20:20).** DESIGN.md, "Smaller tiles for the tile store". Exact at z14, z15 and z16
  (D 0 different through each updated store). A day writes 461 MB at z14 (23% of 2.00 GB), 285 MB at z15 (2.66 GB),
  198 MB at z16 (4.06 GB). **An adaptive split (z16 children for z14 tiles over 256 KB) costs +17% size for half the
  write (250 MB); over 128 KB, z15's size with z16's write.** The update's region is now the store's tiles plus the
  polygon's (two region bugs found by the higher zooms, both prototype-only). Stores in `.scratch/tiles/store-z15/`,
  `store-z16/`, `store13-z15/`, `store13-z16/`. The adaptive rows are an estimate from the two uniform stores.
- **A second day: exact (11-14, 21:50).** DESIGN.md, "A second day". The z14 store through 5175 and 5176 equals fresh
  cuts of 11-13 and 11-14 everywhere inside the clip polygon (tiles, relation store, both tile indexes); D of day one
  0 different. Two gaps in the relation index found on the way, fixed, in the small test. Day two wrote 477 MB (24%).
  After two days a day's pack is still half live (packs die slowly: compaction copies live tiles forward).
  `.scratch/tiles/` is now 47 GB (geom-12/13/14 20 GB, stores at z14/15/16 and the fresh cuts, and `ref/`, the frozen
  t2n recount the checks hold against).
- **For the owner, to ask as a wizard:** the store is proved (two days at z14) and the layout measured. Next for tier
  2: (a) build it in Kotlin beside the engine with an adaptive split (z16 children of z14 tiles over 256 KB, a tunable;
  the split is an estimate from two uniform stores, not built), cut from the 12-07 planet; open for that build: the
  way-tiles index (about 19 GB as plain pairs, rewritten whole each day in the prototype) and compaction; (b) leave
  tier 2 for now. And: push the commits since 19:10. If (a), keep `store/`, `store-z16/` and the fresh cuts as the
  build's oracle, and `ref/` always; the geom folders (20 GB) can go.
- **The owner's answers (11-14, 22:05):** push: yes. Tier 2 in Kotlin: "we can consider building it in kotlin, but i
  need to see reasons why this specific stack and not other". Next: the comparison (DESIGN.md, "Tier 2's store: this
  stack against the others").
- **The comparison, written (11-14, 22:20):** DESIGN.md, "Tier 2's store: this stack against the others". Overpass
  with attic (~400 GB) and OSMExpress (~600 GB) are ruled out by disk, GeoDesk by its model (no untagged node ids, no
  daily updates yet), PostGIS by disk and model; osmium on a daily planet (170 GB, an hour or two a day, no new code)
  is the credible fallback; the tile store wins on disk (~124 GB), daily work and is already exact. Kotlin over Python
  (speed), and over C++/Rust (the engine reads the store directly, one toolchain). **Waiting on the owner:** build it
  in Kotlin (first: the cut of one world file, measured), or take the osmium fallback, or wait.
- **The owner asks (11-14): is there a paid Overpass with attic, and what would one cost to run?** Looked up the
  pages: Overspan ($19-139/mo) says attic is "not yet"; Geofabrik (EUR 40-160/mo, own server from EUR 550) and
  Tracestrack say nothing about attic; overpass.ch ($25-199/mo, dedicated from $649) shows "history back to Sep 2012"
  and runs history queries on stock Overpass, but no `[date:]` is named, so ask them. Private.coffee (free, donations)
  has attic but no promises. Own instance: ~0.5 TB growing, cloned from dev.overpass-api.de in about a day; a rented
  64 GB / 2x1 TB NVMe box is roughly EUR 40-80/mo (Hetzner auction, not priced live), or one 2 TB NVMe here (one-off).
  Not decided; the tier 2 question above still waits.
- **The owner leans to buying a drive (11-14): SSD or a spinning disk?** Overpass needs an SSD: its queries and
  minutely updates are random reads, which a spinning disk does at ~100-200 a second against an SSD's tens of
  thousands. A spinning disk fits only files read end to end (planet history, region files, archives). Advice: a
  2 TB NVMe in a USB4 enclosure (enclosure ~$110-120, not priced live), or a second M.2 slot if the laptop has one.
- **The laptop, looked up (11-14):** ThinkPad P14s Gen 6 AMD, type 21RV000PUS. One M.2 2280 slot (PCIe 4.0 x4),
  already holding the 2 TB SK hynix; two USB4/Thunderbolt 4 ports (40 Gbps). So the drive goes external, on USB4.
  CPU and 88 GB are plenty for Overpass. In WSL its database must sit on ext4 (a VHDX on the new drive, or the drive
  mounted with `wsl --mount`), never on `/mnt/<letter>`, which crosses into Windows and is far slower.
- **The shortlist (11-14, CAD, Canada Computers pages read that day; prices are 2-3x 2025's, NAND shortage):** WD
  SN850X (DRAM, TLC) 2 TB $549.99 or 4 TB $1,099.99 (sale; regular $1,519.99), the same $275/TB; Lexar NM790 (no
  DRAM, coolest) 2 TB $449.99 / 4 TB $799.99. Enclosure: StarTech 1USB4-NVME-ENCLOSURE (ASM2464PD, fanless aluminium,
  pad) $121.95 at fleetnetwork.ca; Orico M2V01-C4 $59.99, in store only. ASM2464 enclosures drop out on Linux hosts
  with AMD USB4 (Framework threads) but behave on Windows; here Windows owns the drive and WSL only sees a disk, so
  the Windows case applies. Soak-test a week before trusting it. Against renting (EUR 40-80/mo) the 2 TB kit pays
  back in roughly 8-12 months.
- **The owner asks (11-14): a NAS instead of the enclosure?** Not as storage for an Overpass run on the laptop: every
  random read would pay a network round trip, gigabit caps it near 110 MB/s, and its files over SMB/NFS (from WSL,
  too) risk locking trouble. A NAS that runs Overpass itself (Docker, x86, 16 GB+, an NVMe pool rather than M.2 as
  cache only) works and keeps it off the laptop; a mini PC with two M.2 slots does the same job, usually for less and
  with more CPU. A spinning-disk NAS suits the archives. Not decided.
- **The owner chose (11-14, late): a USB4 SSD on the laptop.** Checked before buying: the attic clone on
  dev.overpass-api.de (2026-11-10, the newest complete one) is **about 708 GB** summed from its listing (455 GB without
  attic, 360 GB without meta), not the 400-500 GB assumed; DESIGN.md's table now says so. 2 TB holds it with room
  (plus the planet history pair, ~1 TB in all); 4 TB only for years of headroom. The download is 708 GB (hours at
  500 Mbit/s, most of a day at 100). Port power: PSREF names the USB-C ports Thunderbolt 4 but gives no output figure;
  Thunderbolt 4 requires 15 W for bus-powered devices, and the SN850X plus bridge is about 10-11 W, so it should hold
  (the Framework dropouts were on 7.5 W ports). Not yet measured. **Open, asked:** does Overpass become tier 2's store
  (instead of the Kotlin tile store), or sit beside it? Setup to settle when the drive comes: ext4 on the drive (a
  distro imported there with `wsl --import`, no admin, or `wsl --mount`, which needs it), a keepalive so WSL doesn't
  stop the service, and how to stop it safely before sleep or unplugging. A rehearsal on a small region (attic on,
  one day of diffs, `[date:]` checked against the 11-13/11-14 cuts) can run before the drive arrives.
- **The owner's decision (11-14, 22:30): "I will buy external ssd to have Overpass locally. The language selection --
  not sure yet, let's discuss in next session."** So tier 2's store for the world is to be an own Overpass instance
  with attic data (D and D-1 by `[date:]`) on an external SSD (attic planet about 400 GB in 2023 terms, growing: buy
  with headroom). The tile store stays as the measured alternative and as the oracle of what a rectangle's map data
  must hold. **For the next session:**
  1. Discuss the language for what reads Overpass and feeds the engine (Kotlin beside the engine, Python beside the
     stream, or other), with the comparison in DESIGN.md, "Tier 2's store: this stack against the others".
  2. Overpass on this Windows machine: Docker or WSL, a clone with `--meta=attic` (check the current version's clone
     support), its updates from the planet's minute or day diffs, the database on the SSD.
  3. The query per rectangle and ring at D and D-1 must give what the tile rule gives: every way with a node in the
     padded box, complete with all its nodes; tagged nodes; kept relations with every member way (DESIGN.md,
     "Measurement (c)", the tile rule). First check: Overpass's answer for t2n's 103 rectangles of 11-13 recounted
     against `.scratch/tiles/ref/state.bin` (0 rows different is the bar, as the tile store met).
  4. Its speed for a world day's rectangles (thousands of queries), and what format reaches the engine.
  Keep `.scratch/tiles/ref/` (the frozen recount) and, until Overpass passes that check, `store/`, `store13/`,
  `store14/`; `geom-12/13/14` (20 GB) and the z15/z16 stores can go.
- **The language for the Overpass reader, put to the owner (11-14, evening).** The seam is one function,
  `tier2.map_data(day, rects) -> Path`: the engine reads only PBF (no XML reader), and needs each element's
  version and timestamp (`out meta`) plus `osmosis_replication_timestamp` in the header (or `--today`).
  Overpass answers XML or JSON, never PBF. DESIGN's "why Kotlin" reasons were about the tile store's cut,
  update and direct read; with Overpass there is no cut or update of ours, so the choice is small and cheap
  to reverse. **Recommended:** Python issues the queries (the rectangles live there; the time is spent waiting
  on Overpass), and the XML becomes PBF with osmium-tool in WSL (C++, fast; sets the header), so the engine
  is unchanged for the first check (t2n's 103 rectangles of 11-13 against `.scratch/tiles/ref/state.bin`, 0
  different). Only if a world day's measurement shows the conversion costing time: a StAX OSM-XML reader in
  the engine (Kotlin, JDK only, no new dependency). A query can union many boxes, so a world day may be one
  query per file and clock (128 x 2), not thousands. Here now: WSL Ubuntu (stopped), Docker Desktop, pyosmium;
  no osmium-tool yet.
- **The owner's answers (11-14, 23:00):** language: **Python plus osmium**. The SSD: **not bought yet; "benchmark
  overpass on this pc before committing"**. (Correction to the line above: osmium-tool 1.18 is here, in the Docker
  image `name-ru-repair-osmium` that `osm_extracts.py` runs.)
- **Overpass benchmark, planned (11-14, 23:10), waiting on the image download's go-ahead.** A history file cannot
  seed attic (the Overpass wiki: unsupported, and an `.osh` fed to `update_database` leaves the db unusable), so:
  Docker `wiktorn/overpass-api` (0.7.62.11, 105 MiB), a named volume; load the europe clip of 11-12 (1.64 GB,
  stamp 2026-11-12T00:00Z) with attic kept, then apply planet day diff 5175 with attic kept, so one db answers
  11-12 and 11-13. The query mirrors `tiles.py select()` on each rectangle's box padded by 300 m: nodes there, ways
  by those nodes and ways crossing, relations with a member node or way there plus all their member ways, every
  way's nodes, `out meta`; XML to PBF by osmium with the stamp in the header; `tiles.py recount` and `compare`
  against `.scratch/tiles/ref/`. Checks in stages, so a difference has one cause: (1) after the load, undated,
  against `ref/old` (11-12); (2) after 5175, undated, against `ref/state.bin` (11-13); (3) `[date:11-12T00:00Z]`
  against `ref/old`, and against (1)'s output. Rehearsed first on one city box. Recorded: load time, db size, the
  time to apply 5175, each rectangle's query time from a cold cache (reads and bytes too, since the SSD's latency is
  what transfers), the union query's. What it cannot show: the external drive's speed, and fourteen years of attic
  (one day here). XML goes to a bind mount, not into Docker's disk (which never shrinks by itself). Docker may take
  46 GB; stop the container before a 30 GB recount.
- **Overpass benchmark: rehearsal passed (11-14, 23:02-23:10; owner: "yes, pull and run").** `tools/stream/overpass/bench.sh
  rehearse` (log `logs/opbench-rehearse.log`, results `.scratch/overpass/rehearse/summary.json`): the 16 Lisboa rectangles on
  a smart extract of the 11-12 clip. **All three stages 0 rows different** inside the boxes (11-12 undated, 11-13 after
  diff 5175, `[date:11-12T00:00Z]`); stage 3's answer differs from stage 1's only in tag order on 28 objects. Load 26 s
  (1.2 GB db); the whole planet's 5175 into it 189 s (db 4.3 GB). A rectangle alone 0.3-0.5 s warm, 0.6-1.0 s cold (about
  1,000 reads, 55 MiB each); dated about 30% slower than undated. Container and volume removed. **Full run started** (all
  103 rectangles, the whole europe clip): `bench.sh full`, log `logs/opbench-full.log`, results `.scratch/overpass/full/`;
  cleanup after: `docker rm -f opbench-full; docker volume rm opbench-full`.
- **The world's resolution, decided (11-14, 23:12; another session, asked as a wizard):** the owner wants the world
  "daily resolution same as we have for city prototypes", and chose **"same as the cities": monthly points from
  2017-01, daily from the 11-08 seed onward**, not daily back to 2017. Not planned or built. Estimates given, none
  measured: by batch about 118 world counts of about 10.5 h each (about 52 days; the 24 h first written here was
  the 11-10 estimate, the 11-13 run measured 10.5 h, DESIGN.md "The stream: its state"); by streaming from a 2017-01 seed about
  3,600 days at 8-14 min, roughly 4 weeks for tier 1 (every day's diff is applied anyway, so the monthly points cost
  the same as daily ones), needing a full count and a node store at 2017-01 and every day diff since; an untested
  shortcut is a month's diffs merged and applied in one step. Tier 2's history waits on Overpass's measured speed
  (attic answers any past date). The only world reference is 11-08, so a stream from 2017 is checked where it
  arrives.
- **Batch engine speed-up, started (11-14, 23:20; owner: "spend some time doing optimizations for current
  implementation of batch engine. think outside of the box too"; a systems-language rewrite is the owner's other
  track, not this one).** Worktree `../sc-open-quests-batch`, branch `batch-speed` (the Overpass session runs main's
  engine build). Test file: Germany f0 of `.scratch/world-de2` (113M nodes, 18 cells), runner and comparer in
  `.scratch/batch-speed/` (`run1.py --engine ../sc-open-quests-batch --tag X [--opts=-D...]`, `same.py A B`: snapshot
  equal in every field but runSeconds and engineCommit, state.bin as sets). **Read off the world count's logs:** 82%
  of the count's wall time is cells one after another (12,465 s of 15,217 s; map data 3,520 s of it). **Measured on
  f0 at 30 GB:** baseline 245 s wall, 2,467 s CPU, of which only 651 s is quest runs: the collector is the limit
  (the file's records keep the heap 70% full). Built, same snapshot: the area pass's nodes as columns instead of
  114M objects, a city's elements picked from int arrays: **202 s, 2,074 s CPU**. Cities' area runs at once
  (`-Dopenquests.areaCities=N`, default 1) give the same snapshot but no gain at 30 GB (6-8 full collections); to
  measure with a larger heap. Built, not yet measured: key indexes and the node index built on all threads before the
  runs (20 runs waited 1.8 s on one thread building them). **Timing runs used all 24 threads at 23:31-23:55, during
  the Overpass full run's load, diff and stages 1-2: its load and diff seconds may be inflated**; none ran during its
  per-rectangle timings. Next: heap and JDK 25 (compact headers), then the cut (osmium through Docker's bind mount
  read the 0.9 GB rehearsal regions at about 27 MB/s a pass: to test against a copy inside the container).
- **Overpass benchmark done (11-15, 00:16; DESIGN.md, "Overpass with attic, benchmarked on this machine").** Full run on
  t2n's 103 rectangles: **0 rows different in all three stages** (11-12 current, 11-13 after diff 5175, 11-12 by
  `[date:]`), so one attic db answers D and D-1 exactly. Load of the 1.64 GB clip 31 min (db 13.7 GB, 8.4x); the planet's
  day diff 409 s; a union query per date 84-206 s (mostly 1.1 GB of XML), conversion 10-16 s; dated 30-50% slower than
  current; small boxes still cost 1-2 s each in selection, so a world day batches rectangles into union queries.
  Follow-up (00:40): the union's 84-206 s was mostly the Windows bind mount; **piped into osmium inside the container a
  date is about 40 s** (selection 30 s); four queries at a time 2.9x faster. A world day **estimated** (not measured) at
  0.5-2.5 h of Overpass at four streams plus 10-50 min of engine per date, reading perhaps a fifth of the planet per date. **Drive to buy: 2 TB** (the attic clone is about 708 GB now, not 400). Not shown: speed with 14 years of attic
  (the public server was too loaded to tell). **Still up:** the volume `opbench-full` (the container removed at 00:45; `bench.sh full` recreates it over the volume) (18.7 GB in Docker's
  VHDX, which does not shrink by itself); remove with `docker rm -f opbench-full; docker volume rm opbench-full`.
  **Next, the owner's:** buy the drive (2 TB NVMe in a USB4 enclosure), then: the clone (`download_clone.sh --meta=attic`,
  about 708 GB) onto ext4 on it, its daily updates, and the reader for a world day (union queries per world file).
- **The owner's answers (11-15, 00:50):** drive: **a 2 TB NVMe on USB4**, to be bought. Test db `opbench-full`: **keep it**
  (for a world-day reader prototype before the drive arrives). Push: **not yet** (19 commits local).
  **Next, when picked up:** the world-day reader against `opbench-full`: union queries piped to PBF inside the container,
  a `<remark>` check, four streams; then, with the drive, the clone onto ext4 and its daily updates.
- **A peer session's review of the bench (11-15, 00:55), folded into DESIGN.md:** the 409 s for diff 5175 is on a clip db,
  not a planet's daily cost; carry reads (not seconds) to the external drive, since Windows may cache the VHDX under
  `drop_caches`; clip edge and midnight (`[date:]` by element timestamp against a cut by sequence) are expected sources
  of differences that are not Overpass's fault (none appeared). Its suggested real-attic test on overpass.private.coffee
  failed: 504s after 109-262 s and no answer to a tiny query in 90 s; stopped after 5 requests.
- **Batch engine speed-up: merged into main (11-15, 02:55 and 03:10; the entry below was written before).**
  `batch-speed` rebased and fast-forwarded twice (the second time AddHousenumber's twin: 79 s to 30 s of its CPU a
  file, f0 now 117 s against 245 s, 2.1 times); main's engine rebuilt; 93 engine tests pass on main,
  SnapshotReproductionTest among them. **The 13:15 daily run now counts with this engine and pushes its data as usual** (its snapshots equal the old
  engine's on Ontario; the pause target and two cells at once are `world_cells.py`'s settings only, the daily runs
  keep their launcher). Not pushed by this session. Since the entry below: `world_cells.py count` runs one engine
  by default (one engine with two cells 243 s for two files, two engines side by side 223 s at 44 GB: the CPU is the
  limit); the cut's 1.85 times holds with cold caches; **cut with `-s complete_ways`, the Germany rehearsal's four
  files count exactly as cut with `smart`** (every field of 46 cells), which makes "cut the history file once, then
  time-filter each file per month" worth its own rehearsal for the 118 world months (estimate: 12 days of machine
  time against 52); quests by key in the main pass was exact and gained nothing, taken out. Dublin and Lisboa's twins
  equal their ports with two cities at once. **Not checked: a world file with a polar or antimeridian cell (the cut
  is gone): run the canary file first on 12-07.** The worktree `../sc-open-quests-batch` and `.scratch/batch-speed/`
  (about 6 GB of runs and the complete_ways cut) can go.
- **Batch engine speed-up: 2.0 times on the test file, built on branch `batch-speed`, not merged (11-15, 02:15).**
  DESIGN.md, "Batch engine speed-up". Germany f0: 245 s to 123 s wall, 2,467 s to 1,912 s CPU; with `--dump-state`
  272 s to 172 s; Ontario's daily-style run 78 s to 54 s. Same snapshot at every step, same state rows, same grid
  files; 87 engine tests pass; Bremen's fast twins equal their ports (Hamburg's check was still running). What was
  built: the area pass's nodes and ways as columns and tags as dictionary numbers (the collector, not the quests,
  was the largest CPU consumer), one node table for both passes, a sparse twin of SC's `LatLonRaster`, indexes built
  on all threads, two cells at once (`-Dopenquests.areaCities=2`, set by `world_cells.py`;
  `WORLD_CELLS_AREA_CITIES`), `-XX:MaxGCPauseMillis=5000` in the launcher. **To merge:** `git rebase main` in the
  worktree, then `git merge --ff-only batch-speed` on main; the next `run.py` rebuilds the engine by itself.
  **The cut:** osmium through Docker's bind mount reads 4.5 times slower than from the container's disk and a
  region pass is 1.85 times slower; the world's 262 min cut should be about 140 min natively. **For the owner:**
  install a native Windows osmium (conda-forge) for the cut and the slice? A cutter in the engine's build (estimated
  30-40 min a planet) and a once-only history cut for the monthly backfill are described in DESIGN, not built.
- **Batch engine speed-up, second round (11-15, midday; owner: "lets continue bulk engine optimisation
  work?").** DESIGN.md, "Batch engine speed-up, second round". Germany f0: **117.4 s to 91.5 s** (CPU 1,874 s to
  1,566 s), f1 110 s to 86.9 s, with `--dump-state` 187.6 s to 129.8 s; 2.7 times since 11-14. **Merged into
  main (fast-forward) and main's engine rebuilt the same afternoon; 96 engine tests pass on main,
  SnapshotReproductionTest among them. Not pushed: the next 12:15 daily run is the first with the cache on and
  pushes these commits; `-Dopenquests.matchCache=false` is the off switch if a count looks wrong.** Two changes, the same
  snapshot after each: (1) the level twins keep only the nodes near a mall (AddLevelThing was what every cell's run
  phase waited for: cells' phase 70 s to 53 s); (2) the main pass settles a quest once per tag signature
  (`MatchCache.kt`, on by default, `-Dopenquests.matchCache=false` for the old way, `=verify` to check every
  element against it): 98% of elements reuse an answer, 2 quests asked an element instead of 120. Ontario's daily
  run shows no gain beyond noise (pass 51.7 s and 51.4 s; its main pass 17.2 s to 13.3 s). Checked: verify mode on f0's 23.8M elements and on Dublin and Lisboa, f0/f1
  snapshots, f0's state rows, Ontario's 11-14 snapshot and grid against what main published, `verifyFast` on Dublin
  and Lisboa, 96 engine tests. **Not checked: a world file with a polar or antimeridian cell (as before: run the
  canary first on 12-07).** A custom port now names the filter it starts from (`CustomQuest.necessary`): **when a
  port is redone at a repin, keep that in step with its `isApplicable`** (REPIN.md, step 4, has the
  `matchCache=verify` run that finds a wrong one). Next for the engine, none built: one read of the ways (7.9% of CPU), AddHousenumber's node set as
  primitives (now a cell's longest run, 7.9 s), the kerb search (5%); nothing single is large any more, and the cut
  (262 min through Docker's bind mount) is the larger part of a world chain. `.scratch/batch-speed/m*` are this
  round's runs; the worktree `../sc-open-quests-batch` (branch `batch-speed`, now equal to main) can go.
- **The owner asks (11-15, early afternoon): is Overpass on an external SSD still right, or optimize the current engine and
  measure more first?** Answered, nothing built. (1) The batch engine sits after either store, so its speed is not
  an alternative to Overpass; the alternative is the tile store. (2) On t2n's 103 rectangles the tile store itself
  reads in 2.2-2.3 s (+1.3 s merge; the rest of its 34-45 s is pyosmium writing a PBF), Overpass selects in 30 s and
  hands over a PBF in about 40 s: **a tile store read by the engine would be roughly ten times faster per date and
  124 GB against 708 GB, as a projection: its Kotlin cut, update, way-tiles index and compaction are unbuilt and the
  planet cut unmeasured.** (3) Speed does not decide it: the world day is set by the cover's area, and Overpass's
  estimate (0.5-2.5 h for both dates) fits a day. Overpass's unknowns (dated queries on 14 years of attic, a planet's
  daily diff, USB4) can only be measured on the real clone, 708 GB, which does not fit in the 340 GB free: **buying
  the drive is the measurement.** Recommended: buy the 2 TB drive as decided; before it, the world-day reader on
  `opbench-full`; on the clone, the go/no-go DESIGN names (one world file's rectangles as one union query, current
  and dated); do not build the Kotlin store before that. If Overpass fails there, the drive still holds the tile
  store or two planets for osmium. The threshold for the go/no-go is not set: the owner's.
- **The owner (11-15, early afternoon): "let's focus in this session on Tile store work. Which language should we choose to
  implement it in".** So the tile store is being worked on after all, beside the Overpass plan (not cancelled; the
  drive is not bought yet). Recommended: **Kotlin, in the engine's build** (DESIGN, "Why Kotlin for the tile store"):
  the engine reads the store directly, so the 30 s PBF write of each read goes; Python stays the oracle and the
  orchestration. First step proposed, not started: the Kotlin cut of the europe clip of 11-12, held payload for
  payload against the Python store, then one world file's cut timed before the planet. Waiting on the owner's yes.
- **The owner (11-15, early afternoon): "I want to consider a rust version. Third tool chain is not a problem for us, since
  agent handles technical side."** Reconsidered with that objection gone. What was left of the case for Kotlin: the
  engine reading the store directly, and one build with shared tests. The first is small: the 30 s PBF write was
  pyosmium's, native code writes that 60-100 MB PBF in a few seconds (projection; osmium's stamp-and-sort of the same
  data took 1.6 s), and a Kotlin reader of the tile format stays possible later. What Rust gains is where Kotlin's
  risk was: the planet cut and its memory (11 billion nodes, the pair indexes), with no heap to size. What Rust
  costs: the tile rule (which relations the app ignores, the 300 m pad) lives a third time beside AreaPass.kt and
  `tiles.py`, kept in step at a repin, held by the oracle check. **Recommended now: Rust for the store (cut, update,
  read to PBF), the engine unchanged, proved by a spike first: the cut of the europe clip of 11-12 held against the
  Python store's decoded payloads, and timed.** Rust is not installed here (no cargo/rustup; Visual Studio 2022 is,
  so a linker should be): installing rustup needs the owner's yes. Nothing built.
- **The tile store's cut in Rust, a spike: exact and about 50 times faster on the clip, 24 threads against Python's
  one (11-15, 13:35-14:10; owner: "Yes,
  install and start").** DESIGN.md, "The tile store in Rust". Rust 1.100 (stable-msvc) installed by
  `winget install Rustlang.Rustup`; cargo is `~/.cargo/bin/cargo` (a shell opened before the install needs
  `export PATH="$HOME/.cargo/bin:$PATH"`). Crate `tilestore/` (`cargo build --release` there, 30 s the first time):
  `target/release/tilestore.exe cut --pbf C:/Users/kk/Code/.osm-data/europe/europe-2026-11-12.osm.pbf --out
  .scratch/tiles/store-rs --day 2026-11-12` reads the clip itself and writes the Python store's layout, generation 0.
  **35.7 s against about 1,920 s** for `tiles.py geom` + `attrs` + `tilestore.py cut`. **Held against
  `.scratch/tiles/store` generation 0 by `tools/stream/tilecheck/storecmp.py`: 59,026 tiles, 438,232 relation blobs
  and both pair indexes, 0 different** (the checker fails as it should on store against store13); the Python `read`
  of the Rust store recounted at 11-12: 1,114,046 rows, 0 different (`.scratch/tiles/s12-rs/`). **Not shown, and the
  reason Rust was preferred:** the planet cut. This cut holds everything in memory, 12.2 GiB peak for the 1.64 GB
  clip (over 600 GB at planet size, and its node rows are 32 bits); a planet cut is another program (places on
  disk, tags streamed, pairs sorted in runs), not designed. Also not built in Rust: the update, the read to PBF.
  **Germany (4.88 GB, timing only, no oracle): 128.7 s, 41.3 GiB peak; its tiles are 1.60 times the PBF, not the
  clip's 1.14** (long ways outside cities copy their nodes into every tile they cross), so the planet's "about
  124 GB" may be nearer 160-170 GB. The multiple measures Python's loops, not Rust against Kotlin: no Kotlin cut
  exists. The Python `update` was not run on a Rust-cut store (first act of the update step: run it, then
  `storecmp.py --ga 1 --gb 1`). Left on disk: `.scratch/tiles/store-rs` (2.4 GB), `store-rs-germany` (9.5 GB),
  `s12-rs`; `tilestore/target/` (ignored); the Rust toolchain in `~/.cargo` and `~/.rustup`. All can go; the rerun
  is the command above. Main is 12 commits ahead of origin: the next daily run pushes them. **Next, proposed:** the read in
  Rust (331 tiles to a PBF, the engine on it, timed against Overpass's 40 s), then the update, then the planet
  cut's design and one world file. The Overpass plan and the drive stand as they were.
- **The read in Rust: exact, about 1 s a date (11-15, 14:10-14:25; owner: "Yes, the read").** DESIGN.md, "The read
  in Rust". `tilestore/target/release/tilestore.exe read --store .scratch/tiles/store-rs --cities
  .scratch/tiles/ref/cities.json --out X.osm.pbf --stamp 2026-11-12T00:00:00Z` (`--gen N` for another generation;
  run from the repo root, or pass `--base`): **0.97-1.00 s** for t2n's 331 tiles (Python 34-55 s, Overpass about
  40 s), of which the PBF write 0.6 s; the PBF writer is ours (`tilestore/src/pbf.rs`). **Exact three ways:** against
  the Python `read`'s PBF object for object (`tools/stream/tilecheck/pbfcmp.py`: 8,269,618 objects, 0 different); the
  engine's recount at 11-12, 1,114,046 rows, 0 different; and generation 1 of the Python store (the updated one)
  read by Rust and recounted at 11-13, 1,116,244 rows, 0 different. Reading a date is now about 15 s, nearly all
  engine, 849 MiB peak for the read. **That is the read only:** against Overpass the tile store still owes its
  daily update in Rust (9-10 min in Python on the clip) and the planet cut, which is the piece that could still
  sink it. Not measured: a cold read (the files were cached), and anything larger than these rectangles. The PBF
  writer cuts blocks by count, not size (a blob must stay under 32 MiB; not guarded). The handoff argument for
  Kotlin is settled by this (0.6 s); planet memory is the open one. **For the owner to revisit, not decided here:**
  whether this changes the Overpass and drive plan. Runs in `.scratch/tiles/s12-rs/`, `s13-rs/` (can go).
- **The planet cut, designed, not built (11-15, 14:30-14:50; owner: "Yes, planet cut").** DESIGN.md, "The planet
  cut, designed". Three streaming passes (relations, nodes into a 108 GB node-place file by id, ways resolved
  against it and spilled with their places into coarse buckets), then each bucket cut in memory by today's code.
  Border rules written down: far tagged nodes reach a bucket through "needs", member nodes of kept relations are
  spilled, relations get their tiles after the way pass, the relation store is built from a member-way file.
  Measured today for it: Germany's largest z8 bucket is 383 MiB of store, a way lies in 1.001 z8 buckets.
  **The whole cut does not fit on C: now** (about 290-310 GB peak against 263 GB free, the spill's size a guess):
  it waits on the 2 TB drive. **Only the history file of 11-02 is on disk** (no planet snapshot): a cut from it is
  11-02's store. **First to build, no planet resources: the streaming cut held against the in-memory cut by
  `storecmp.py` on the clip and Germany, bucket zoom z8 and z11-z12.** Then one timing of the node file and way
  pass (108 GB, deleted after; proposed pass under 4 h, fail over 12 h). Asked of the owner: the cut's source (the
  history file read at a date by Rust, or a snapshot), and when that 108 GB timing may run.
- **The owner's answers (11-15, 14:55):** the cut's source: **the history file, read at a date by Rust** (to be
  proven on `berlin-history` against `osmium time-filter` first). The 108 GB timing: **on C:, after the clip-scale
  proof**, the file deleted after. Next: **"Yes, build it now"**, the streaming cut, proven against the in-memory
  cut on the clip and Germany. In progress below. **Next, proposed:** the update in Rust (first act: the Python `update` on
  `store-rs`, then `storecmp.py --ga 1 --gb 1`), then the planet cut's design.
