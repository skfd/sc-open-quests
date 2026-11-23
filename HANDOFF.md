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
`kk-SCOpenQuests` runs daily at 17:15 UTC: 13:15 in summer, **12:15 in winter (EST)**, as its trigger
carries a fixed `-05:00`. Design and known gaps are in DESIGN.md.

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

### Share previews: built on `share-previews`, not merged, not live (2026-11-23, afternoon; owner: "build it, i will upgrade account later")

- **Where:** branch `share-previews`, worktree `../sc-open-quests-previews`, two commits: `bab3d69a` (the
  page's `og:` tags and the site card `docs/img/share-card.png`) and `06bf2326` (the Worker). Its DESIGN.md
  section, "Share previews: a Worker's text for every place", has what it does and what was checked;
  `cloudflare/README.md`, "Share previews", has the go-live steps. 213 tests pass there.
- **Nothing on main or on the live site changed.** The Worker is `cloudflare/wrangler.previews.jsonc`;
  the daily run deploys `wrangler.jsonc`, which is untouched, so merging the branch puts only the tags
  and the card live.
- **Waiting on the owner, two things:** (1) a look at the card (sent in the session) before the branch
  is merged, since merging publishes it with the next daily run; (2) **Workers Paid** before the Worker
  is deployed. It must not go out on Free: about 6 ms to parse `quests.json` plus a city's history is
  past Free's 10 ms of CPU, and a failed page view is a broken page.
- **Checked locally:** all 147 cities' previews say `cities.json`'s number (293 of 293 links); seven
  links in a browser, page against card (city, part, selections, a world place, counted places under
  their place ids); the home page byte-equal; 404s; revalidation; a hostile name escaped.
- **Not checkable before live:** the zone's folder rewrite rule in front of the script. The go-live
  steps deploy by hand, test at once, and say how to put the script-less site back.
- **The site's title and description still say "Canada and Europe"** (page, `og:` tags and the card's
  alt text). Left as is: the wording for the world is the owner's, at release 1.
- **Local check servers are stopped** (ports 8791, 8792). `C:/tmp/pv-fix` and `C:/tmp/pv-check` are
  scratch and can go.

### Share previews for release 1: decided (owner, 2026-11-23)

The 11-10 architecture above is stale: `docs/` is 9,339 files (pages plus PNGs for cities and parts would
reach about 18,060 of 20,000), and about 1M world places can never be static pages. Decided instead:

- **Every place gets a text preview on release day, through a Worker.** It runs on the page request only
  (`app.js`, icons and JSON stay plain static assets), reads `?place=<id>` (crawlers send the query), fetches
  that place's file from `sc-data` and rewrites the head: title "N open StreetComplete quests in <place>",
  description with the 4-week change. Today's `?place=` links work as they are, so **no slugs are frozen**
  and the address scheme (`/toronto/agincourt-north/` against `/<country>/.../<slug>/`) stays open.
- **The picture is one site-wide card on day one** (the mockup's frame, no numbers, no date). The home page
  gets `og:`/`twitter:` tags and that image; its title and description still say "Canada and Europe".
- **Owner: Workers Paid, $5 a month, agreed** (no 100,000-a-day cap on page loads; under the $50 breaker).
  The owner upgrades the plan; not done yet.
- **After release:** per-place pictures rendered on demand in the Worker and kept in R2 (about 300 ms CPU a
  card, which is why Paid), once a card for a world place is designed.
- **To check while building:** the Worker's number must be the page's (same default-on quests summed); what
  the zone's folder rewrite rule and `html_handling: none` do with a Worker in front (`wrangler dev` does not
  reproduce the rule; that interplay broke the home page once); it goes live with or after the world
  publish merge, since it reads the same place files.

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
  cut on the clip and Germany. Done, below.
- **The streaming cut, built and exact below planet size (11-15, 15:00-16:15).** DESIGN.md, "The streaming cut,
  built and proven below planet size". `tilestore/target/release/tilestore.exe scut --pbf X.osm.pbf --out S --day D
  [--bucket-z 8] [--keep-spill]` (`tilestore/src/stream.rs`; the tile rule now in `pairs.rs`, shared with `cut`).
  **Equal to the Python store on the europe clip at bucket zoom 8 and at 12** (59,026 tiles, 438,232 relation
  blobs, both pair indexes; 735,132 border "needs" at z12), **and to the in-memory cut on Germany** (190,006 tiles,
  628,034 blobs). The comparison fails as it should with the needs dropped (`TILESTORE_TEST_NO_NEEDS=1`: 38,141
  tiles differ). Clip: 240 s, 5.2 GiB peak (in-memory: 36-58 s, 12.3 GiB). Germany: 630 s, **33.4 GiB peak**
  (in-memory 129 s, 41.3 GiB): a spill file (one z6 cell, 9.7 GB raw for Germany's largest) is read whole and its
  buckets cut side by side, so the peak is set by the densest z6 cell; to fix for the planet (spill files per z7/z8
  cell, or fewer buckets at once). **Not exercised: the node file by id** (the places are in memory here; a file
  by id for a region would be nearly planet-sized). **Spill: 12.3-12.8 bytes a ref, so about 185 GB for the planet
  as coded**, more than the design's guess; the cut still waits on the drive. Not tuned: every pass spills on one
  thread. `tools/stream/tilecheck/peak.ps1` runs a program and reports wall time and peak working set. The
  streaming test stores (`store-s8`, `store-s12`, `store-s8-germany`) are deleted; their record is
  `.scratch/tiles/storecmp-s8.json`, `storecmp-s12.json`, `storecmp-s8-germany.json` and the `store-s*.log` files.
  Left in `.scratch/tiles/`: `store-rs` (2.4 GB), `store-rs-germany` (9.5 GB, the Germany oracle); both can go
  (C: has 262 GB free). The 33.4 GiB's cause is likely, not measured (log the working set per phase first).
  **Antimeridian, unknown:** a way across 180 degrees would be copied into a whole row of tiles by the segment
  rule (Python's too); count such ways and split the segment before the planet cut. **Next, in this order:** (1) the history file read at a date in Rust, proven on
  `berlin-history` against `osmium time-filter` (done, the last entry of this list); (2, done too) the node file by id and the 108 GB timing of passes 1 and 2
  on the planet's history file (the owner allowed it on C: after this proof; delete the file after); (3) the
  spill-file memory fix (done too; the entries below). The update in Rust is independent of these. **Next, proposed:** the update in Rust (first act: the Python `update` on
  `store-rs`, then `storecmp.py --ga 1 --gb 1`), then the planet cut's design.
- **Batch engine speed-up, third round: merged into main (11-15, 14:15 to 15:50; owner: "continue engine
  optimisation").** DESIGN.md, "Batch engine speed-up, third round". It replaces the second round's "Next for the
  engine" above. **About 15% less wall time and 17% less CPU on Germany f0**: 89.5 and 87.4 s against main's 102.2
  and 104.0 s in the same minutes (CPU 1,518 and 1,485 s against 1,796 and 1,828 s). The tile store session ran
  Rust cuts on all threads all afternoon, so engines were compared only in interleaved pairs
  (`.scratch/batch-speed/batch.sh`), and no quiet-machine figure exists: main itself was 91.5 s at midday. Built,
  the same snapshot after each: (1) one read of the ways for both passes (the area pass takes its ways off the main
  pass's read); (2) a node found through a table of id stretches (small: about 0.75 s, seen only when the main pass
  is measured alone); (3) node sets as marks by a node's place instead of `HashSet<Long>`: twins for the kerb
  search, AddEntrance and AddCrossingKerbHeight, AddHousenumber's address nodes as a `LongSet`, and a twin for
  AddCycleway that does its clock-free work once per map data. Quest CPU in f0's cells about 500 s to about 400 s.
  **Checked:** f0 and f1 snapshots, f0's 31,695,753 state rows, `matchCache=verify` on f0, Ontario's 11-14 and
  europe-west's 11-15 recounts equal to what main published with grids byte for byte, `verifyFast` on Dublin and
  Lisboa (25 map data runs), three new tests (`NodeSetTwinsTest` holds the twins against SC's code on random map
  data and fails on a broken twin); 101 engine tests on main, none failing, SnapshotReproductionTest among them
  (TorontoRegressionTest skips, its extract pruned). **Not checked:** London under `verifyFast` (its ports take
  tens of minutes; the europe-west recount holds London's totals instead); a world file with a polar or
  antimeridian cell (as before: the canary first on 12-07).
  **Main's installed engine was not rebuilt** (the tile store session may be counting through it): the next
  `run.py` rebuilds it by itself (`engine_is_stale`), so **the next 12:15 daily run is the first with these
  changes and pushes them**; anything that calls the installed engine directly before that runs the second
  round's build, which counts the same. If a count looks wrong, `-Dopenquests.fastKerbs=false` takes the kerb twin out;
  the other twins come out of `FAST_TWINS` (FastTwins.kt). At a repin: `helper:KerbUtil` pins SC's `KerbUtil.kt`
  for the kerb twin (REPIN.md, step 3); the pin is the vendored copy's hash with LF endings, no SC checkout was on
  disk to hash, so a "moved" report there with no change in the file is that.
  **Next for the engine:** the fourth round below built the rule this named. `.scratch/batch-speed/` holds this
  round's runs (`r3*`, `b-*`, `c-*`, `q-*`) and four engine snapshots (`eng-*`, 11 MB each): all can go.
- **Batch engine speed-up, fourth round: merged into main (11-15, 16:05 to 16:40; owner: "continue engine
  optimization").** DESIGN.md, "Batch engine speed-up, fourth round". One rule in `engine/port_area_quests.py`
  (`NODE_IDS`): a port's `.flatMapTo(HashSet()) { it.nodeIds }` becomes `.nodeIdsIn(mapData)`
  (`openquests/NodeIds.kt`: a bit at a node's place on a city's map data, a `LongSet` for ids of nodes the map
  data lacks, SC's `HashSet` on any other map data; no `Set`, so only `id in it` compiles). Twelve ports
  regenerated from `%TEMP%\sc-v64.1`; quests with a fast twin keep SC's line. **A small gain: the twelve ports
  63.5 and 60.0 s of CPU to 48.2 and 47.4 s on f0; a whole run 91.0 and 84.6 s to 88.6 and 82.3 s, within
  noise.** The 67 s named before was those ports' whole CPU, mostly scans, not the set. **Checked:** f0 (twice)
  and f1 snapshots, f0's 31,695,753 state rows, europe-west's 11-15 recount and grid against the published
  ones, Ontario's 11-14 the same, `verifyFast` on Dublin and Lisboa (under it every answer of the marks is held against SC's set),
  `NodeIdsTest` (fails when the ids of lacking nodes are dropped), 105 engine tests on main (TorontoRegressionTest skips). **Not checked:** the sc-harness oracle
  on the rewritten ports; London under `verifyFast`; polar and antimeridian cells (canary first on 12-07).
  `-Dopenquests.nodeMarks=false` takes the rule out at run time. **Main's installed engine is still not
  rebuilt** (another session has uncommitted tile store work on main): the next `run.py` rebuilds it, so the
  next 12:15 daily run is the first with the third and fourth rounds.
  **Next for the engine, none built:** quest twins now buy about a percent each (no quest above 27 s of 1,284 s
  CPU). The larger part is the cells' map data and the collector, about 515 s: profile a cell's allocation
  first. Then `groupByNodeIds` (AddBarrierOnRoad, AddBarrierOnPath, AddCrossing: 41 s), then the clock-free
  node id sets of five age ports kept once per map data (a few seconds).
  `.scratch/batch-speed/` also holds `d-*`, `r4-*` and `eng-marks`: all can go. The worktree
  `../sc-open-quests-batch` (branch `batch-speed`, equal to main's engine commit) can go too.
- **Batch engine speed-up, fifth round: merged into main (11-15, 16:40 to 17:20).** DESIGN.md, "Batch engine
  speed-up, fifth round". A JFR profile of f0 (`.scratch/batch-speed/r5.jfr`, read with `jfrtop.py` there), and
  from it one new patch to the vendored SC code, `pairs` (`sync-sc.ps1`, `openquests/Pairs.kt`, `PairsTest`):
  `asSequenceOfPairs()` from a plain iterator instead of a coroutine. **About 11% less allocated in a run (215
  to 191 GB), CPU 1 to 5% less in four interleaved pairs, no wall-clock gain shown** (the machine was busy).
  **Checked:** f0 and f1 snapshots, the 31,695,753 state rows, Ontario and europe-west recounts and grids,
  `verifyFast` on Dublin and Lisboa, the engine tests (see the design section for where they ran). **Not
  checked:** the oracle; London under `verifyFast`. Tried and dropped: flags in place of the filter's set of
  element types (no gain beyond noise). `sync-sc.ps1` ran whole against `%TEMP%\sc-v64.1`, so
  `helper:KerbUtil`'s pin is now checked against a real checkout; that checkout had lost most of its files and
  was restored at the same commit. Main's installed engine is still the second round's build until the next
  `run.py`. **Next for the engine, none built:** a dense-node decoder without protobuf's builders (the largest
  piece left, a larger change with its own oracle), then `Way.isClosed`'s boxed ids, `Element.checkValidity`
  over a `TagMap`, `groupByNodeIds`: 2 to 3% of the allocated bytes each (the sixth round below reorders this).
  `.scratch/batch-speed/` also holds `e-*`, `g-*`, `r5-*`, `eng-types`, `eng-pairs` (this round's build): all can go.
- **Batch engine speed-up, sixth round: merged into main (11-15, 17:20 to 19:35; owner: "fifth round of
  speedup", already merged, so the next).** DESIGN.md, "Batch engine speed-up, sixth round". **Four changes to
  how a cell's map data is put together: on f0 the cells' phase 12% shorter and a whole run 6% (87.4 s to 81.9 s,
  4.5% less CPU; three interleaved rounds).** The build that still had the five main-pass changes showed 9.5%
  on a calmer machine (80.0 s to 72.4 s) and was equal to the four alone side by side. A bit per node for "tagged"; a cell's node order
  from a bit set instead of two sorts (`firstSeen`); a way's node found at the place after the one before
  (`NodeStore.indexOfAfter`); a cell's ways and node ids put in place by the threads that make them. New
  switch `-Dopenquests.assembleTrace=true` (a cell's map data, seconds per step). **Five more changes, to the
  main pass, were built, exact, measured and taken out** (commit e95f9b6c has them, the next removes them):
  nothing net in three interleaved rounds. **Checked on the merged build (dbd3989b):** f0 and f1 snapshots, the 31,695,753 state rows, Ontario and
  europe-west recounts and grids, `verifyFast` on Dublin and Lisboa (25 runs), `matchCache=verify`, 111 engine
  tests on main (`FirstSeenTest` and two in `NodeStoreTest` are new). **Not checked:** the oracle;
  London under `verifyFast`; a world run.
  Timing scripts: `.scratch/batch-speed/quietn.sh` (`V="pairs six5" P=q8 bash .scratch/batch-speed/quietn.sh 3`
  waits for a free machine, then interleaves the builds `eng-<name>` on f0 and writes `q8.out` with the load at
  each run's start). About 9 s of f0's wall there is the rehearsal's whole notes clip read on one thread, which
  a world file does not have. Main's installed engine is still the second round's build until the next `run.py`.
  **Next for the engine, none built:** the collector (a cell's untagged nodes made when asked for); what is
  still one-threaded in a cell's map data, and three cells at once again; the `ScFeatures.getFeature` lock
  (24 s of threads waiting in a run; needs osmfeatures' source read); the main pass measured by itself before
  any other change there (it is 30% of the CPU and none of five guesses moved it), the dense-node decoder
  after that; last the items that only save bytes.
  `.scratch/batch-speed/` also holds `h-*`, `i-*`, `j-*`, `k-*`, `q6-*`, `q7-*`, `r6-*`, `r6b-*`, `eng-six`,
  `eng-six2`, `eng-six3`, `eng-six4`, `eng-pairs`: all can go; `eng-six5` is the merged build. The worktree
  `../sc-open-quests-batch` (branch `batch-speed`, equal to main's engine commit) can go.
- **The history file read at a date in Rust: exact against osmium (11-15, 16:00-17:00; owner: "The next step
  toward the planet timing is the history-file reader").** DESIGN.md, "The history file read at a date".
  `tilestore/target/release/tilestore.exe at --pbf X.osh.pbf --at 2026-10-01T00:00:00Z [--out Y.osm.pbf]` and
  `scut ... --at T` (`tilestore/src/history.rs`, `Blobs::each_at` in `stream.rs`). osmium's rule (visible, at or
  before T, the next version after T), blocks decided on all threads and stitched at their borders.
  **`berlin-history` at seven dates against `osmium time-filter`, object for object: 0 different** (two round
  dates, a version's own second and the second before, two moments in 2008 where the rule gives an object twice);
  `tools/stream/tilecheck/atcheck.sh X.osh.pbf OUTDIR DATE...` reruns it (Docker image `name-ru-repair-osmium`).
  The checker finds the one node that differs a second apart; the border tests (`cargo test` in `tilestore/`) fail
  on a broken rule. **`scut --at` on the history file equals `scut` and `cut` of osmium's snapshot** (1,719 tiles).
  **Backwards timestamps are real** (28 in Berlin, all 2008): inside such a one-second window osmium and `at` both
  give two versions of an object, and `scut --at` stops (run at both 2008 dates; the reader counts ids that do
  not increase, `notIncreasing`, and the cut refuses any: before that check a way given twice passed silently).
  The planet's are not counted: `tilestore at --pbf history-261102.osh.pbf --at T` with no `--out` gives
  `notIncreasing` for a date in one read, worth doing before the hours of a cut; `backwards` is the whole file's
  and will not be zero. **The allocator is now `mimalloc`** (on the Windows
  heap the relation blocks of a history file took 10-13 s each on 24 threads): Berlin's 23.7M versions read in
  1.44 s; the clip's `cut` 24.7 s and `scut` 133.9 s (35.7-57.5 s and 240 s before; one run each, machine not
  quiet), both still equal to `store-rs`. Nothing about the planet's 170 GB is projected. `.scratch/history/`
  holds the logs and `cmp-*.json`; its PBFs and stores are deleted. **Next: the node file by id and the 108 GB
  timing of passes 1 and 2 on `history-261102.osh.pbf` with `--at`** (allowed on C:, the file deleted after; log
  the working set per phase with it), then the spill-file memory fix. The update in Rust is independent.
- **The planet timing of passes 1 and 2: done, 53 minutes, passed (11-15, 17:26-18:23; owner: "go ahead").**
  DESIGN.md, "Passes 1 and 2 on the planet, the node places in a file by id". `tilestore ptime --pbf
  history-261102.osh.pbf --at 2026-11-02T00:00:00Z --nodes F.loc` (`tilestore/src/ptime.rs`; log
  `logs/planet-ptime.log`, figures `.scratch/planet-time/planet.loc.json`). Blob index 284 s (2.4M blobs), **pass 1
  630 s** (16.7 billion versions read, 10,975,350,797 nodes, the node file 114.7 GB), **pass 2 2,554 s**
  (1,229,012,042 ways, 13.08 billion refs, 1.393 billion way-tile pairs); the program's own memory under 1 GiB,
  pass 2's working set 65 GiB of the mapped node file. Threshold was 4 h pass, 12 h fail. **One run, and not
  alone on the machine for almost any of it** (the engine session's note, kept): the engine session, not knowing
  of it, ran f0 counts and checks from 17:23 to about 18:15 (up to 24 threads and 30 GB each, one after another)
  and then two engine test suites; around 18:10 no memory was free. So the seconds are an upper bound: alone it
  would be faster by an amount nobody measured, and pass 2, which leans on the OS cache for the node file, the
  most. Whether pass 2 waited on disk or CPU was not measured. **From 18:25 the engine session runs ten more f0
  counts (`.scratch/batch-speed/quiet6.sh`, about 15 minutes; it waits while a `tilestore` or `osmium` process
  exists): do not time anything until `.scratch/batch-speed/q6.out` ends with "ended"** (it did, 18:55), **nor until
  `q7.out` does** (nine more runs from about 19:00, some 15 minutes; then the checks of the build they choose,
  some 25 minutes more, not timing-critical). **All of that ended at 19:35: the engine session runs nothing more.** **Not the cut's time:**
  no pass 0, no spill, no tagged-node or member-way files, no buckets. **Settled for 2026-11-02:** no node or way
  is given twice at this date (relations not read); every ref has a node; no way has two nodes in a row over 180
  degrees apart (one way has a whole row of 16,384 tiles, not looked up); refs are 13.08 billion, so the spill as
  coded is about 167 GB; node ids reach 14.34 billion. **The node file is deleted** (C: 259 GB free). Checked
  below planet size only: Berlin through a sparse node file gives `scut --at`'s nodes, ways, refs and pairs.
  **Next: the spill-file memory fix** (done, the next entry),
  then the spill's coding and the single-threaded spilling. The whole cut waits on disk: node file 115 GB, spill
  about 167 GB, store 97-136 GB. The update in Rust is independent.
- **The streaming cut's bucket phase in bounded memory: done, exact (11-15, 19:10-20:00; owner: "go on").**
  DESIGN.md, "The bucket phase in bounded memory". Measured first: Germany's peak was the bucket phase, 31.3 GiB
  (the passes 11.3 GiB), the densest z6 spill file read whole. Now **a spill file a bucket** (`--file-z`, default
  the bucket zoom), the spill buffers capped at 1 GiB together, and **spill files cut in groups under a budget**
  (`--cut-gib`, default 2 GiB of records). Germany's bucket phase: **7.8 GiB instead of 31.3**, 62.7 s instead of
  76.5 s; about 1.5 GiB plus 3.2 GiB per GiB of records cut at once; the floor is the largest single bucket
  (Germany's z8: 1.17 GiB of records; the planet's is not known, a finer `--bucket-z` is the lever). **Equal to the
  oracles in all fifteen runs** (Germany against `.scratch/tiles/store-rs-germany`, the clip at bucket zoom 8 and 12
  against `store-rs`; `--file-z 6 --cut-gib 0` is the old arrangement). `scut` logs working set and private bytes
  per phase and samples the bucket phase. Germany's process peak is now the passes' 11.4 GiB, mostly the node
  places in memory, which the planet keeps in a file. `.scratch/history/mem.sh` reruns the six settings (about 20
  minutes; results `mem.out`, `mem2.out`, logs `g2-*.log`, `c2-*.log`, `storecmp-*.json` there); the test stores
  are deleted, the two oracles kept (12 GB, can go once `scut` with the node file is proven).
  **A file a bucket costs appends:** the spill is written on one thread, each append compresses, opens, writes
  and closes; at bucket zoom 12 on the clip (8,561 files, 23,725 appends) pass 2 takes 31.1 s against 16.9 s with
  1,411 files, about 0.8 ms an append; with few files the cost is zstd on that thread, 2.3-2.4 s a GiB of records.
  The planet's appends are not known (`spill:` in the log counts them); `--file-z` coarser, files kept open or
  compression off the pass's thread are the levers, none built.
  **Still unbounded for the planet, in the passes:** all relations in memory, the tagged-node index (about 7 GB for
  298.9M tagged nodes), the member ways' tables. **Next: `scut --nodes F.loc`**, the node file by id inside the cut
  (today only `ptime` has it), held against `scut` on the clip and Germany through a sparse file; then trim those
  tables. Then the planet cut needs only disk (node file 115 GB, spill about 167 GB, store 97-136 GB). The update
  in Rust is independent.
- **CLOSED 11-15, 23:20: the space is back and the delete is fixed.** The owner restarted at 23:14; C: had 283 GB
  free after it (the files in `$Extend\$Deleted` went with the restart). The Berlin test of the delete that cuts
  the file to length 0 first, run once: free space 291,519 MiB before (284.7 GiB), 291,046 MiB after the program deleted
  its file, 291,023 MiB 20 s later (the 0.5 GiB is drift: run again at 01:02 with idle readings around it, it lost
  nothing), and `ptime`'s counts as wanted. Before the change the same run left 20.4 GB taken. What in
  Windows held the deleted files was never found. Still true: never run a country through `--nodes --sparse`.
  **Next:** see the last entry (the spill's appends and coding are done). What follows is the incident
  as it was written while open.
- **WAS OPEN, the owner's: C: has about 43 GB free, not 258 GB (11-15, 21:45).** DESIGN.md, "The node file inside the
  cut, two tables trimmed, and a disk incident". Two things happened. (1) At about 21:13 `scut --nodes --sparse`
  on Germany filled the disk (2.0 GB free) and died; its file was deleted by hand at 21:14:37. A region's sparse
  node file is large (Berlin 22.9 GB, Germany more than 250 GB); **never run a country through `--nodes
  --sparse`**. Guard built and seen to work: under 40 GiB free the writer deletes its file and stops
  (`tilestore/src/nodefile.rs`, `FLOOR`). (2) **About 216 GB is still taken by node files that are deleted:** the
  ones the program removed itself (Berlin three times, the clip twice, a test) did not give their space back,
  while the same file removed with `rm` after the program ended does. Cause not known; taking 54 GB of memory
  (down to 2.5 GB available) freed nothing. No such file is listed anywhere under `.scratch/`. **Checked 22:20 with
  the owner's elevated output:** shadow copies hold 11.8 GB (ruled out); `fsutil volume diskfree C:` shows 42.5 GB
  free, 38.2 GB "Total Reserved" and the rest (about 178 GB) allocated to nothing listed; no tilestore process is
  left. The large reserve points at deleted sparse files still held in the kernel, which a restart would clear;
  that is a lead, not shown. **Found 22:35 (owner's WinDirStat):** `C:\$Extend\$Deleted` holds 176.4 GiB on disk
  (482 GiB of length), among them two files of 95.06 GiB length and 66.73 GiB on disk: the node files, deleted by
  name and still referenced. **Asked of the owner: a restart** (it ends 12 python processes from 11-03 to 11-14
  that are not this project's). **After it: read free space first.** If it is not near 250 GB, the next step is
  an elevated `chkdsk C: /scan`, the owner's. Until then: the 12-07 planet job needs about 170 GB; the daily runs need little.
  The delete now cuts the file to length 0 first (`NodeMap::delete`), **not shown to help**: test it on Berlin
  (`tilestore ptime --pbf berlin-history-261005.osh.pbf --at 2026-10-01T00:00:00Z --nodes X.loc --sparse`, 23 GB;
  free space before and after) only when more than 70 GB is free. `.scratch/tiles/store-rs` (2.5 GB) and
  `store-rs-germany` (8.9 GB) are the oracles and can go if space is needed.
- **Built before that (11-15, 20:15-21:30; owner: "keep building"):** `scut --nodes F.loc [--sparse]`, the node
  places in the file by id inside the cut (deleted after pass 2): equal to the oracles on Berlin, and the clip at
  bucket zoom 8 and 12; Germany not run to the end. The needs now come from one read of the tagged-node file (no
  index, about 7 GB less at planet size) and unkept relations are let go as read: equal to the oracles on the clip
  (z8, z12) and Germany. `.scratch/history/nodes.sh`, `trim.sh` and their `.out` files; **do not rerun `nodes.sh`
  as it is** (its last line is the Germany run). **Next (both done since):** the delete's test above, then the spill's appends and
  coding; see the entry below.
- **Built 11-15 23:40 to 11-16 00:15 (owner: this project may work through the night):** the spill's appends and
  coding, DESIGN.md "The spill off the pass's thread, and its ways' refs coded". Six workers compress and append
  the spill (Germany's pass 2 73.8 s to 27.3 s, the cut 175.5 s to 121.9 s); a way's refs and places are varint
  differences (Germany's spill 6.71 GiB to 5.49 GiB, 9.79 bytes a ref; the planet's about 137 GB by that ratio,
  not measured). Equal to the oracles after each change, on the clip (z8, z12) and Germany, and every way read
  back from its record equal (`TILESTORE_TEST_WAY_CODING=1`). The cut budget still counts the uncoded bytes, so
  the bucket phase's memory is unchanged. Rerun: `bash .scratch/history/spill.sh NAME [warm]` (about 6 minutes;
  the places in memory, no node file). **Next:** nothing here is blocked but the planet cut, which waits on the
  2 TB drive. Both things left open here were done at 00:35-00:55, the entry below (the level stays 1; Germany through
  a node file that is not sparse equals its oracle).
- **Built 11-16, 00:35-00:55 (owner: "keep building"):** DESIGN.md, "Germany through a node file that is not sparse,
  and the spill's compression level". (1) **Germany with `scut --nodes F.loc` (no `--sparse`) equals its oracle:**
  the whole planet path (node file by id, the passes, the coded spill, the buckets) has now run end to end on a
  country. The 107 GiB file was deleted by the program and its space came back. Private bytes through the passes
  4.0 GiB. Rerun: `bash .scratch/history/gnode.sh` (4.5 minutes, needs about 150 GB free). (2) **The spill stays
  at zstd level 1:** level 3 is 4 % smaller, level 6 is 9 % smaller and slower (`TILESTORE_SPILL_LEVEL`,
  `level.sh`). **Next:** the planet cut, which waits on the 2 TB drive (node file 115 GB, spill about 137 GB, store
  97-136 GB). Not done and not needed for it: the spill's tags coded, the passes' single thread, the
  antimeridian's whole-row way.
- **Built 11-16, 00:53-01:00:** the spill and the bucket phase stop under 40 GiB free, as the node file does
  (DESIGN.md, the last paragraph). The spill's stop was seen (`TILESTORE_TEST_FLOOR_GIB`), the bucket phase's was
  not. The clip and Germany equal their oracles after it. So a planet cut that runs out of room stops with a
  message and 40 GiB left, it does not fill the disk. **After such a stop, remove by hand** the node file given
  to `--nodes` (115 GB on the planet; the stop does not delete it) and the store's `work` folder. **Next:** unchanged, the planet cut on the 2 TB drive.
- **Stale files deleted from `~/Code/.osm-data` (11-16, owner: "all three"), C: 285 GB free to 308 GB.** The
  changesets dump of 10-26 (8.3 GB; `rank_sc_cities.py` keeps its scan in `.scratch/rank/`, a rerun fetches a
  newer weekly dump), skyditor's 22 European extracts of 10-27 (7.5 GB; its squares are cut in
  `skyditor/research/landuse-edges/work/`), and 11 regional history clips of the retired planet 261005 (about
  7 GB): the nine provinces, Hamburg, Bremen. **A recount at a repin now re-clips such a region from the current
  planet** (`backfill_history.py`, about an hour each), or reads the `canada-germany` clip's history once the
  regions switch to it. `berlin-history` is kept (the tile store's checks use it).
- **Scratch cleared (11-16, owner: "delete both sets and the stream, keep the seed"), C: 307 GB free to 521 GB.**
  Deleted: `tiles/geom-12/13/14`, the z15/z16 stores, `s12-rs`, `s13-rs`; `batch-speed/` but its scripts; the
  worktree `../sc-open-quests-batch` and branch `batch-speed` (merged); `world-de/cut`, `world-de2/cut`,
  `planet/world-test`, `world-places/lv-one`, `lv-many`, `de`; **the world stream's node store
  (`store/planet.loc` and `.state`) and rows (`planet/world-stream/`).** Kept: the seed
  `planet/world-places/` (6,460 files, checked after), `world-places/world/`, `tiles/ref`, `store`, `store13`,
  `store14`, `store-rs`, `store-rs-germany`, `stream/europe-west/`. The daily run reads none of `.scratch`.
  **To take the stream up again, before 12-07 (the 12-07 job retires `history-261102`, which the node store is
  built from):** `bash .scratch/store/planet.sh > logs/planet-loc.log 2>&1` (about 40 min; the old log says
  "planet done", so overwrite it, or `world-days.sh` would stop at the missing `planet.loc.state`), then
  `tools/stream/world-days.sh` (it fetches kept diffs, rebuilds `world-stream/` from the seed and applies every
  day from 11-09, 8-14 min a day). **The Rust planet cut now fits on C:** about 260-310 GB peak plus its 40 GiB
  floor against 521 GB free, so it no longer has to wait for the 2 TB drive (the owner's call).
- **The planet cut, as it was started (11-16 01:47; ended 03:30, the entry below).** `.scratch/planet-cut/run.sh`, hidden, log
  `logs/planet-cut.log`; binary `.scratch/planet-cut/tilestore-4b1003b4.exe` (main at 4b1003b4, smoke-tested first:
  `gnode.sh gsmoke` on Germany equal to `store-rs-germany`). `scut` of `history-261102` at 2026-11-02T00:00:00Z,
  defaults (z14, bucket z8, 2 GiB), node file `.scratch/planet-cut/planet.loc` (115 GB, not sparse), store
  `.scratch/planet-cut/store`. C: 544 GB free at the start. (While it ran: no node-file tests, no timings, no
  large writes on C:.) If it stops with exit 101, remove `planet.loc` and `store/work` by hand. The oracle for
  its exactness, `europe-2026-11-02.osm.pbf` (sequence 5164, the same instant), is pinned in `europe/pins.json`.
- **The planet cut ran to the end and agrees with the clip of the same instant (11-16, 01:47-03:30; owner: "Yes,
  run the cut").** DESIGN.md, "The planet cut, run". 6,135.7 s; 32,110,824 tiles; **the store is 268 GiB on disk**
  (pack 232.55 GiB, about 2.7 times the planet's PBF, against the design's 97-136 GB), `.scratch/planet-cut/store`.
  Spill 90.16 GiB (7.40 bytes a ref); about 287 GiB at the peak; private memory at most 11.6 GiB. **Exactness:**
  inside the 11-02 europe clip (2 km in), 13,964 of 14,001 tiles equal; every one of the other tiles (58 at 0.5 km)
  equals the clip's once four ways the clip lacks are taken out, ways whose nodes all lie outside the clip's polygon
  (osmium's extract drops them; the planet is right). `tools/stream/tilecheck/subcmp.py`,
  `.scratch/planet-cut/why3.py`. **C: 274 GiB free now.** Beside the store, the world stream's rebuild (about 107
  GiB node store plus about 48 GB of rows) and the 12-07 job (about 170 GB) no longer both fit: before 12-07 07:30
  either `planet.loc` goes again or this store does (owner's call). **Next, proposed:** the update in Rust (first
  act: the Python `update` on `store-rs`, then `storecmp.py --ga 1 --gb 1`), so this store can be brought to a
  current day; or the engine's count on a planet read of t2n's rectangles against the engine on
  `europe-2026-11-02.osm.pbf` itself (re-pinned for it; `.scratch/tiles/ref/` is the 11-12/11-13 recount, not 11-02).
- **The day's update in Rust: equal to the Python update on two days, 15 times faster (11-16, 08:05-08:40; owner:
  "rebuild daily update").** DESIGN.md, "The day's update in Rust".
  - **Command:** `tilestore/target/release/tilestore.exe update --store S --diff N.osc.gz --before D-1.osm.pbf --day D
    --polygon C:/Users/kk/Code/.osm-data/europe/polygon.geojson`
    (`tilestore/src/update.rs`, `osc.rs`; commit d8fcc8f4).
  - **Result:** on a copy of the Rust cut of 11-12 (`.scratch/tiles/store-rsu`), diffs 5175 and 5176 give
    generations equal to the Python store's 1 and 2 (storecmp: every tile, relation blob and pair). Times: 42.5 s and
    38.5 s, against 623 s and 571 s; peak 10.3-10.7 GiB.
  - **Checks:** a negative control fails as it should. `tests/test_tilestore_update.py` sends the synthetic day
    through the binary too.
  - **Not the planet: a planet day is at least 180,583 tiles and 7.71 GB of payload** (lower bound from diff 5165,
    `.scratch/planet-cut/reach-5165.json`), against the clip's 2,595 tiles. Four things stand in the way, designed
    in outline only:
    - a node store kept and moved forward daily: about 115 GB, or about 57 GB as tile keys
    - the rebuild in groups of tiles: a single working set would be roughly 80 GiB (an estimate) on an 87.6 GB machine
    - pair indexes merged in a stream, not rewritten: 22.3 GB a day
    - disk: about 8 GB a day of new pack plus compaction. Fourteen days of catch-up does not fit on C: before 12-07.
  - **Pinned:** `europe-2026-11-03.osm.pbf`, the oracle for a first planet update (diff 5165); unpin when done.
    Diffs 5165-5176 are hard-linked in `.scratch/planet/diffs-keep`.
  - **Left on disk:** `.scratch/tiles/store-rsu` (4.1 GB, can go).
  - **The node store can be the world stream's `planet.loc`** (osmium `dense_file_array`, 8 bytes per id, the
    same information). If the update reads that layout, the node store costs no disk beyond the stream's rebuild.
  - **Owner's call, open:** disk, and where the planet store starts. The 268 GiB 11-02 store plus 14 days of catch-up
    (more than 100 GB of packs before compaction), or a fresh cut of the 12-07 history file. Either way it sits
    beside `planet.loc` and the 12-07 job, and C: cannot hold all three.
  - **Built after that, no disk needed (11-16, 08:40-09:20):** DESIGN.md, "Toward the planet". Each is held
    against the Python store on both clip days (`.scratch/tiles/rsu-days.sh [update args]` resets `store-rsu` to
    generation 0 and checks both).
    - `--world`, and `--before-loc F`: a node file in the world stream's layout (8bb2b2a0)
    - pair indexes mapped and merged in a stream, and `--prune-pairs` (e1f90086)
    - `--group-z G`: the reached tiles rebuilt one cell at a time (02811a1b). Equal at G = 8, 12 and 14; the clip
      day's peak drops from 10.3 GiB to 5.5 GiB.
    - `--group-mib M`: groups by a budget of old payload (08a86e24). A group costs about 0.2 s on top of its tiles
      when the diff share is the whole diff, and a planet day spans at least 3,623 zoom-8 cells. In world mode on
      the clip, 3 groups at 256 MiB equal one working set (131,000 tiles). With all the planet's flags together
      it is shown only on the synthetic day.
    - Grouping bounds the tile rebuild only. The carried copies and the relation store's working set are still
      single; on a planet day the relation side is small (the diff's relations: 49 MB of blobs).
  - **Left before a planet run:**
    - a Rust step moving the node file forward by a day's diff (small, not built). The stream's `planet.sh` moves
      its file to 11-08 in the same run, and the 11-02 store needs it at 11-02.
    - the disk call above
    - the size of the carried copies on a planet day (not measured)
- **The planet store's first day: done, exact (11-16, 10:41-11:16; owner: "keep building whatever needs to be built").** DESIGN.md, "The planet store's first day". Node file at 11-02 in 17 min, equal to the 11-02 clip; the update by diff 5165 13.2 min, private memory at most 20.1 GiB, 195,294 tiles, pack 8.03 GB; node file moved to 11-03 equal to the 11-03 clip; every tile difference against the 11-03 clip explained by the four ways osmium's extract drops; generation 0 against that clip differs in 1,482 tiles (the control). About 9.2 GB a day kept. 7.45 GiB of the gen-0 pack is dead after the day, 4.51 GiB of it in whole 64 KiB chunks. What was written while it ran:
  Built first (9f65401e): `tilestore loc build|advance|check` (`tilestore/src/locfile.rs`), the node file in
  osmium's dense_file_array layout (the layout `update --before-loc` and the world stream's `planet.loc` share),
  built from a history file at a date, moved forward by a day's diff (refuses a diff not after what
  `F.loc.state` holds), checked against a snapshot; equal to pyosmium's file before and after the synthetic day
  (`tests/test_tilestore_update.py`). The update now refuses to start under the 40 GiB floor.
  **Running:** `.scratch/planet-day/run.sh` (hidden, log `logs/planet-day.log`; rerun with the Start-Process line
  in its header, every step skips what is done): node file at 11-02 (`.scratch/planet-day/planet.loc`, about 107
  GiB), `loc check` against `europe-2026-11-02`, `update` of `.scratch/planet-cut/store` by diff 5165 (`--world
  --group-mib 512`, **no `--prune-pairs`**, so generation 0's pair indexes stay and a wrong result can be redone),
  `loc advance` to 11-03, `loc check` against `europe-2026-11-03`, a cut of that clip (`clip-1103`), then `subcmp.py
  --gp 1` at 2 and 0.5 km. Differences to explain with `.scratch/planet-day/why.py subcmp-K.json clip-1103 store 1`.
  **Disk told to the owner:** this run fits (about 180 GiB at the peak with the floor, 266 free at the start);
  before the 12-07 job (07:30, about 170 GB) about 50 GB short if the store and the node file both stay; to run
  store, node file, world stream and the monthly job daily, about 350 GB more (a month of packs at about 8 GB a day
  without compaction is most of it). The owner is clearing personal files.

## Neighbourhood series and the widget's "Toronto/Parkdale" (2026-11-16, 10:30-11:05; owner: "can we build it")

- **Built on branch `hood-series` (worktree `../sc-open-quests-hoods`), not merged: merging is publishing.**
  `run.py history` now also writes `docs/data/history/<city>/<partId>.json` for every registered part
  (DATA-FORMAT.md, "A part's series"): the city series' shape, zeros left out of snapshots restored as 0
  where the city counted the quest, null where it did not; `in` names the part's name-layer file for the
  site's link. No engine change: `parts` and `partsAged` are already in every snapshot.
- **Backfill:** from the archive, so every one of the 4,214 parts in 81 cities has its days since 2026-10-27
  (aged split included, gaps where the city was not counted). Nothing before 10-27 without a recount of the
  monthly snapshots with parts. Measured over the real archive into `C:/tmp/hoods`: 4,214 files, 34 MB raw,
  1.5 MB gzip in all; Parkdale 11.5 KB raw, 1.5 KB gzip; about 24 s on top of `history` (the name-layer scan
  is 0.3 s warm, up to a minute cold). docs/ goes from 5,125 files to about 9,340, under the 20,000 cap;
  every part file changes each day the city is counted. **Growth:** about 1.6 MB raw a day across the files
  (25 MB for 16 dates), so a full series would add about 570 MB a year to a 135 MB docs/; built with a
  window instead, `PART_SERIES_DAYS = 35` (the widget needs 28 + a week), about 55 MB steady, the archive
  keeping every day. `days=None` keeps all, if the owner prefers. A full `history` into `C:/tmp/hfull`
  left every published file byte-equal (440 of 440) and added only the 4,214.
- **Not the final layout:** DESIGN.md "Place statistics for the whole world" puts place series on an R2 data
  subdomain (`place/<id>.json`). This is the interim on static assets; it can move when that is built.
- **Widget (`../sc-open-quests-widget`, 0701ac0, main, not pushed):** Parameter `Toronto/Parkdale` (first
  `/`, `›` or `>`; exact name before prefix), `; quest` after it still works; tap opens the part's page.
  19 model tests pass; `PREVIEW_DOCS=C:/tmp/hoods-site node ios/test/preview.js ... "Toronto/Parkdale"`
  renders 1,685 open, -5 since 10-27, equal to the 11-14 snapshot's default-on sum. `tools/check.js` fails
  only on "published apps page is current" until `node tools/apps-page.js ../sc-open-quests/docs/apps`.
- **The owner's answers (11-16, 11:10):** merge and write the apps page; publish the last 35 days.
  Done: `hood-series` fast-forwarded into main (008748ea), worktree and branch removed; apps page written
  (6f3a8635), widget `tools/check.js --no-gradle` all ok. The 12:15 run publishes both (its `history`
  writes the 4,214 files). Left for the owner: download `open-quests.js` again on the phone (the phone
  keeps its copy: the old script answers `Toronto/Parkdale` with "No city called ..."). Widget repo commits
  (0701ac0, 370ffe0) are on its main, not pushed.

## Chart ends hoverable from the gutters (2026-11-16, 11:25; owner: "hard to hover first and last point")

- Done in `docs/app.js` (`edgeHover`, and the `setCursor` hook): level with the plot, the white beside it
  out to the card's edges reads out the first snapshot on the left and the last on the right, synced to the
  other charts, pinned ones too. Fixed with it: the hover rings never showed when the pointer arrived on the
  last snapshot from idle. DESIGN.md "The chart's ends from its gutters". Checked by
  `.scratch/edge-hover/probe.py` (serve `docs/` on 8766; 17 of 17 ok) and `probe2.py`, `tapdist.py`
  (phone taps work 10px or more outside the plot).
- **The planet store's second day: exact too (11-16, 11:18-11:33).** DESIGN.md, the same section. Diff 5166 in
  10.6 min with `--prune-pairs`, node file at 11-04 equal to the 11-04 clip, tiles explained by the same four ways,
  control 1,314 differ. **The store is at 11-04, generation 2** (`.scratch/planet-cut/store`), the node file
  `.scratch/planet-day/planet.loc` at 11-04 too; generation 0's pair indexes (22.8 GB) are still kept and can go.
  The live payload stays at about 232.6 GiB; dead space grows about 8.5 GB a day: **compaction is the next build**
  (daily packs copied forward; the cut's pack given back in place, 64 KiB holes). C: 115 GiB free.
  **Disk for the owner, firm now:** for a month of daily planet updates after 12-07 with the node file, the world
  stream and the monthly job: about 345 GB more than today without compaction, about 150 GB with it.
- **Compaction built (11-16, 11:35-11:50):** DESIGN.md, "Compaction". `tilestore compact` (daily packs copied
  forward) and `tilestore punch` (pack 0's whole dead 64 KiB units zeroed in place), both exact on the clip, punch's
  negative control caught. The planet store is compacted at generation 2 and unchanged against `clip-1104`.
  **Running:** `.scratch/planet-day/run3.sh` (hidden, log `logs/planet-day3.log`), waiting for today's 12:15 daily
  run to end, then day 3 (diff 5167) on the compacted store with `--prune-pairs`, checked against
  `europe-2026-11-05` (generation 2 as the control). **Next:** the planet punch at generation 3 (dry run against an
  independent count first; then subcmp of generation 3 again), then compaction's effect over days.

## What the site shows: a product review (2026-11-16, 13:00; owner: "discuss information we display as product designers")

Nothing changed on the site. Written in `design/product-review-2026-11-16.md`. In short: the site is
for players ("how is my place doing?"), but the city page reads as an analyst's dashboard, and the
neighbourhood page, which is the template for a million place pages, is the thinnest one. Proposed,
first: build the unified place page now (DESIGN "A neighbourhood is a place"), reading today's part
series, which the site does not yet use. After that: open the chart on recent time with notes at the
import steps, call the change "net", fold zero rows into "N done here", drop the density tiles from the
city page, and fix the phone table's clipped questions. Four questions to the owner are at the end of
the file.

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


## Rule: published counts cover every quest (owner, 2026-11-16, late evening)

Anything published counts all quests, never an easier subset (DESIGN.md, "Don't"). For the planet: the world
stream's tier 1 alone is never published; a world day goes on the site only with tier 2 and area dates in it and
checked against a full count. Until then the world's published numbers can only come from full counts.

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

## Spend breaker on hosting: built (2026-11-19, 10:00-10:45; owner: "make sure there is a spent breaker on hosting. 50 bucks a month max")

DESIGN.md "Spend breaker" has the why. `tools/spend_breaker.py` prices R2 (the only billable part) from
GraphQL analytics, trips at $40: latch file plus `sc-data.comentality.com` public access off, publishers
refuse R2 writes until `python tools/spend_breaker.py --reset`. Hourly task `kk-SCOpenQuests-spend`
(`logs/spend.log`); `cloud_publish.py` and `archive_backup.py` call `gate()` before writing. The world
publisher on `world-publish` got a strict gate and a per-run file cap. Tests: `tests/test_spend_breaker.py`.
- **Owner, in the dashboard (no API for these, and the token has no billing access):** Manage Account,
  Billing, Billable Usage, Create budget alert at $10, $25 and $40, so a trip also reaches email. Done by the
  owner, 2026-11-19. If the
  account is ever moved to Workers Paid, set a Workers spending limit there too (Billing, Spend Management).

## World vs the daily run's cities: they agree (2026-11-19, late evening; side session)

`tools/world_compare.py` (read-only, ~15 s) held the world's `osm-<city>` counts and each city's name-layer place
against the published snapshots for 11-02 to 11-06; report in `.scratch/world-compare/report.md` (verdict on top,
from `findings.md`). Aligned on the clock (Europe's snapshot D = world D; Canada/Germany's D ~21:21Z = world D+1),
473 pairs: median 0.000%, p90 0.003%, +2,591 of 138.3 M, 289 exact. Gaps: 11-02 Europe was SC v64.0 (+0.6%,
AddAcceptsCards); 2.6 h of edits for Canada/Germany (Sarnia 11-05 +2.1%, 289 buildings); notes off by 1-11 in 5
pairs. Overture places differ from the OSM outlines (Bratislava -13%, Halifax -2.4%, Cape Breton -2.2%), so
counted cities keep `osm-<city>`. **The world can stand in for the daily run's numbers** once the owner picks a
clock (midnight UTC, or cut the world at the extract time). Rerun after 11-07 lands for 11-06's Canadian cities. `--measure agedOnly` (11-20, `report-aged.md`): 434 of 473 exact,
net +13 on 4.2 M. **Rerun 11-21 for 11-02 to 11-13** (`.scratch/world-compare/to-1113/`, the first report left as
it was): 1,419 aligned pairs, median 0.000%, p90 0.004%, 850 exact, the worst still Sarnia 11-05; days 11-07 to
11-13 each within ±0.003% summed; `agedOnly` 1,284 of 1,419 exact. No Canadian snapshot for 11-04 and 11-09. DESIGN.md now says counted cities take `osm-<city>`, never the Overture place.
**Clock decided (owner, 11-20): midnight UTC**, the world's own; recorded in DESIGN.md next to that rule. Nothing
changes in the daily run until the world replaces it.

## Daily city run: down 11-19 to 11-21, Geofabrik moved regions (fixed 2026-11-21, 13:10)

- **The 12:15 run failed three days in a row** at its download step (11-19 Quebec, 11-20 and 11-21 Ontario), so
  the pilot cities' newest count is 11-18 and nothing was pushed since 11-19. Geofabrik moved the Canadian
  provinces and Berlin, Hamburg and Bremen into folders of their own (`north-america/canada/ontario/ontario-latest.osm.pbf`);
  the old URLs redirect to a 404.
- **Fixed in `../osm-extracts`** (its REGIONS table; and `fetch` now answers a Geofabrik 404 by asking
  `index-v1-nogeom.json` where the region is and warns that REGIONS is stale). The run was restarted by hand
  11-21 13:10; the missed days 11-19 and 11-20 are not backfilled (the extracts are only today's).

## World places publisher: built, not merged (2026-11-19, night; owner: "when is it sane to publish world stuff?", then "Yes, build it")

- **When it is sane:** release 1's rule, 30 gated days from 11-01, so the day 11-30 is counted: about **12-01**. The
  catch-up is not what limits it (about 3-3.5 h a day; caught up about 11-21 or 11-22); the calendar is.
- **Built on branch `world-publish`** (worktree `../sc-open-quests-worldpub`), three commits: the format (DESIGN.md,
  "World places published: the files"), `tools/world_publish.py` with `tests/test_world_publish.py`, and the place
  page (`docs/app.js`, `tests/fixtures/world/` with `check_world.py`, 45 checks). **Merged into main 11-19, 23:05**
  (it touches nothing the catch-up imports); the output and cache moved to main's `.scratch/world-publish/`, so
  `python tools/world_publish.py build` from main needs no `--out`/`--work`/`--world`. The page is inert until release: `WORLD_HOST = ""` in `app.js`, so it asks the world nothing
  unless `?world=` is given (pages without it read text-identical to main's, checked).
- **The files:** `latest.json` (max-age 300), `place/<base>/<id[:2]>/<id>.json` (written when `base`, the newest
  1st, moves) and `latest/<date>/<parent[:2]>/<parent>.json` (daily); both dated folders immutable. A quest's
  series is change points `[i, open, aged]`. Only 12-hex places the name layer has, only `open`/`agedOnly`, only
  gated days, no gaps. A parent is the name-layer parent; a country's is `world`; a country with no Overture id
  (AC, EA, EH, IC, PS, TA) is addressed by its lower-case code, as the page's `countryId`.
- **Run on the real world, 11-01 and 11-02** (output `../sc-open-quests-worldpub/.scratch/world-publish/site/`,
  cache `.../work/`): 1,018,472 place files in 19 min (once a month, 0.91 GB raw), 110,413 parent files in 3.5-4.5
  min (daily, 0.82 GB raw; each new day reads one counts file, about 60 s). `verify --sample 3000`: **0
  mismatches** reading the files back as the page does (place file plus parent file, and every parent's file over
  its whole window) against `counts.npz` on both days. That proves the files equal the world's counts, not that
  the world's 12-hex places are right: see the crosscheck below. Headless on the real files: Germany 20,095,288 open (−2,458 on
  11-02), Ontario, Plauen and a neighbourhood draw tiles, chart, quest table and children, no console errors.
- **Not done, in order:**
  0. **Released early, 2026-11-21 (owner: "can we release now whatever we have, and while full back fill has not
     completed keep pilot cities?", then "Go, all four" and "Once a day").** Pilot cities keep their own daily
     numbers; every other place reads the world, "As of" its newest gated day (11-13 at release; the catch-up
     reaches today about 11-23). Done: CORS rule set (`world_publish.py cors --set`: GET, HEAD from
     `https://street-complete-statistics.comentality.com`, checked: a foreign origin gets no header); verify 0
     mismatches (800 places, 13 days); the first upload started 12:23 through `world_publish.py daily` (1,128,897
     files, about 160/s, about 2 h; log `logs/world-daily.log`); a place file checked live: `application/json`,
     br, immutable, MISS then HIT. Task **kk-SCOpenQuests-worldpub** daily 15:30 local runs `daily` (build; if the
     day is new, verify 2000 and upload; `work/uploaded.json`, `work/daily.lock`). Cost: about $4.50 this month,
     then about $15 a month for the daily `latest/` plus $4.50 when `place/` moves on the 1st (the breaker's
     estimate, trips at $40). **Left:** `WORLD_HOST` in `docs/app.js` once the upload has finished, then deploy.
     **STOPPED 2026-11-21 13:03 (owner: "lets do the stable urls and proper fix. if you think we need to stop
     upload you can do it"):** the first upload was killed about 39 minutes in. State left behind:
     - the bucket holds orphans under `place/2026-11-01/` (roughly 375k objects, nothing else; no `latest.json`),
       to be purged by that exact prefix;
     - task `kk-SCOpenQuests-worldpub` is **disabled** (`schtasks /Change /TN kk-SCOpenQuests-worldpub /ENABLE`
       once schema 2 is live);
     - `.scratch/world-publish/work/daily.lock` was stale; deleted 13:05 (the task stays disabled);
     - `WORLD_HOST` is still `""`, so the site reads nothing from the bucket.
     **Schema 2 is being built on branch `world-stable` (worktree `../sc-open-quests-stable`), agreed 11-21:**
     stable paths `place/<id[:2]>/<id>.json` (the whole series, change points by day number from `first`) and
     `children/<p[:2]>/<parent>.json` (per child and quest: newest and four weeks before), each fetched with
     `?v=<latest.json v>`, cached a day; only files whose bytes changed are uploaded, by a manifest of what the
     bucket holds. Why: 11-02..11-13 only about 12,500 of 110,423 parent files and 34,000 of 1,018,552 places
     change on a day (`.scratch/world-publish/parents_changed.py`), and a country page downloaded `world.json`
     (2.1 MB) for its own entry (`.scratch/world-publish/page_open.txt`). The schema-1 text below describes
     the old layout; the new one is DESIGN.md "World places published: stable paths (schema 2)" on the branch.
     **Live, 11-21 16:45: schema 2 is in the bucket through 11-13 and merged into main (433a40df).**
     - Bucket: 1,128,975 files (`place/`, `children/`, `latest.json` v 20a53b131333); `check` 0 mismatches.
       First upload 13:45-16:28 (the session's 2 h limit killed it at 800k; it resumed from
       `work/bucket.json`). The day after went through `daily`: 34,612 place and 12,697 children files,
       47,309 uploads in 5 min. DESIGN.md "World places published: stable paths (schema 2)" has the numbers.
     - Page: `WORLD_HOST = "https://sc-data.comentality.com/"` in `docs/app.js`; checked headless against the
       live bucket (`.scratch/world-publish/live_page.py`: Plauen, Germany, Thiergarten, Ontario). **Not
       deployed until a city run finishes** (it deploys `docs/`).
     - Task `kk-SCOpenQuests-worldpub` is enabled again (15:30 daily; `daily` now uses `site2`, never `--full`:
       a plan past 200,000 files stops and wants a look, `upload --print` then `upload --full`).
     - Publisher output is `.scratch/world-publish/site2`; manifests `work/local.json` (built) and
       `work/bucket.json` (uploaded). Losing `bucket.json` means a full re-upload (about $5).
     - **Left:** `.scratch/world-publish/site` (schema 1, 1.7 GB) can be deleted; worktree
       `../sc-open-quests-stable` and branch `world-stable` can be removed; after 11-29 `back` starts to
       slide, so watch the first days' upload counts in `logs/world-daily.log`.
     **The city run failed 11-21 13:52** (`java.lang.OutOfMemoryError: Java heap space`, `AreaPass`, Europe's
     11-21 file at `-Xmx14g`, "what the machine can spare", beside the catch-up and other runs). It left
     `docs/data/*/snapshots/` empty mid-rotation (14 uncommitted deletes), so `docs/` must not be deployed by
     hand. Rerun through its task at 16:50 (`schtasks /Run /TN kk-SCOpenQuests`); see `logs/scheduler.log`.
     **The rerun failed the same way at 17:25** (Europe's 11-19 file for `europe-west`, `-Xmx13g`): the engine
     needs more heap than the machine spares beside the planet catch-up (python 16 GB plus its java workers;
     24 GB free of 88). Not retried again. The live site is unchanged (data through 11-18, the old `app.js`
     with no world host), so nothing is broken, but **the world pages are not live until `docs/` deploys**.
     Ways out, the owner's choice: wait for the catch-up to end and let the 12:15 run go; pause the catch-up
     for one city run; or `git checkout -- docs/data` (back to the committed 11-18 files) and
     `python tools/cloud_publish.py` to deploy only the page.
     **Owner, 17:30: "Page only, now". Done 17:40:** `git checkout -- docs/data` (the 14 snapshot files back),
     `python tools/cloud_publish.py` (1 file copied, `app.js`; site version d716c438), `--check` 9,338 equal.
     On the live site with CORS on (`.scratch/world-publish/live_site.py`): Germany and Plauen read
     `latest.json`, `place/...?v=20a53b131333` and `children/...?v=...` from `sc-data`, "As of Nov 13", no
     errors; Toronto asks the world nothing. **World pages are live.** City data stays at 11-17/11-18 until a
     city run fits in memory; the 12:15 run on 11-22 may fail again while the catch-up runs.
  1. **Daily build after each world day.** `python tools/world_publish.py build` once the loop has closed a day
     (it reads only gated days). Wire it into `planet_store_day.py` after the day's cleanup **only once the
     catch-up has ended** (never edit the running script). Until then run it by hand. **Run by hand 11-19, 22:49, through
     11-06** (the first compressed counts files, 113 MB each, about 37 s a day to read): 110,415 parent files in 135
     s; `verify --sample 3000` 0 mismatches over 6 days. Places counted after `base` (1,018,472 at 11-02, 1,018,499
     at 11-06) have no place file until 12-01, so the page shows them "Not counted yet" until then.
     **Run by hand again 11-21, 11:02, through 11-13** (beside the catch-up): 678 s, 110,423 parent files,
     1,018,552 places at 11-13; `verify --sample 3000` 0 mismatches over 13 days.
  2. **At release (owner's go):** the bucket's CORS rule (GET, HEAD from the site's origin); then
     `world_publish.py upload` (`--print` shows the rclone commands; never run yet, credentials untouched): the
     first upload is about 1.13M PUTs, hours at 64 transfers; then `WORLD_HOST = "https://sc-data.comentality.com/"`,
     merge, and the next run publishes the page.
  3. Whether a counted city's own page should also show the world's numbers is not decided: counted cities keep
     their own data (DESIGN, same section). Visible effect: Ontario's children table lists Toronto with the
     world's number, and its link opens the city page with the city's own (different polygon, different count).
  4. **Before release, the independent check:** once day 11-08 has passed its gate,
     `python tools/world_publish.py crosscheck --day 2026-11-08 --json .scratch/world-publish/cross-1108.json`
     (worktree: add `--world ../sc-open-quests/.scratch/planet/world-1101`). It compares every published place,
     per quest, with the 11-08 whole planet count with places (`.scratch/planet/world-places/report.json`, kept
     for this; v64.1, same instant), reads 644 MB, about 2 min. Expect near-equal, not exact (notes layers differ,
     as the gate's 11 cities). Exercised on 11-02 against it (six days apart): world -0.081%, 89.2% of places equal
     in every quest, the largest gap a building import in Azumino (Japan, +109,523 by 11-08): plausible change.
     **Done 11-20, 08:55 (11-08 gated 06:54): passed.** 1,018,508 places in both; **99.968% equal in every
     quest**; open world 6,681,050,595 vs the report's 6,681,050,914 (−319, −0.000005%). Largest gaps: China −33
     (Hanzhong, Shaanxi −13), GB −6 (England −6), Turku −6; by quest AddMaxHeight −162, AddHousenumber +38, the rest
     under 40. Notes-layer noise, as expected. Output `.scratch/world-publish/cross-1108.json`.
  5. After the first upload: fetch one `place/` file and `world.json` (1.16 MB raw) from `sc-data` and check
     `Content-Type: application/json`, a compressed encoding, and `cf-cache-status` HIT on the second fetch.
- **Disk:** the local site is 1.13M small files, 1.73 GB raw (about 4.5 GB with 4 KB clusters); `place/` is rebuilt when
  `base` moves (12-01) and the previous kept (`KEEP_PLACE`), `latest/` keeps three days.

## The place page: merged (2026-11-16, evening; owner: "pick from handoff ui work", then "merge it now")

**Owner, 11-16 late evening: accepted, but the design is preliminary and not reviewed by the owner.** The direction
is right, and processing places (city down to neighbourhood) is genuinely valuable. So treat the layout, tiles,
wording and tab structure as a first draft open to change, not as decided design; build on the direction.


- **Merged into main from branch `place-page`; the next scheduled run publishes it.** DESIGN.md, "The place page".
  One page for a counted city and each of its parts, reading the part series; the chart opens on 90 days ("All since
  2017" in the link), steps marked (Toronto's 2026 import named), density tiles replaced by the 4-week change
  (mapping vs resurvey) and the most-open quest type, zero rows folded into "N quest types done here", the phone
  table fixed, `app.js:1506`'s stale line gone with the old part cards. Tabs: Places, Compare cities, Map (the owner
  approved the collapse). Widget links (`?place=&in=`, `?city=`, `&pin=`) all land on it. Checks:
  `.scratch/place-page/drive.py`, `clicks.py` (serve `docs/` on 8767), `fixtures.py` (serve the repo root on 8769).
- **Data:** `run.py history` now writes `place`/`in` on each city in `cities.json` (146 of 147; London, GB has no
  row). A full rebuild into `C:/tmp/pp` changed only `cities.json`. Not committed by hand: the first daily run after
  the merge writes it. Until then the page shows "Ontario, Canada" as text instead of the linked chain.
- **Left from the review, not done:** sort ticked quests first in the table (Toronto's opens on two unticked rows
  bigger than the total), the class name moved off each row, the shorter phone header, relative dates elsewhere.
  Compare's table scrolls sideways on a phone (it did before too). The 90-day chart's y axis starts at 0, so a
  city's month barely moves the line; worth revisiting if the change should be visible.
- **Repin rule: forward from the release date (11-16, evening; owner: "forward from release day agreed").** REPIN.md
  step 6: at a repin each region's snapshots from the release's publish date on are recounted
  (`backfill_history.py recount --region R --since DATE`, then `merge`), from the extracts the store keeps 14 days;
  nothing older changes, so the release shows as a step on its date. The repin issue now says "within 14 days".
  A full recount from history is the on-demand exception (a history download first). Found and fixed on the way:
  `backfill_history.py`'s count did not pass the parts registry, so a merged recount would have dropped every
  snapshot's parts; now it does (Bremen 11-14 and 11-15 recounted equal to the published, parts included).

## R2 cache test done; place-data host `sc-data` set up (2026-11-17, 02:30; owner at the desk)

- **Result (DESIGN.md, "The R2 cache premise: checked"):** a cache HIT is not an R2 read (PNG: 30 fetches,
  1 GetObject); JSON is never cached without a rule (60 of 60 DYNAMIC, all R2 reads); the zone's 4-hour
  Browser Cache TTL raises a lower origin max-age. Scanner bots probed ~30 secret-looking keys within two
  minutes of the certificate. `run.py`'s verdict line misread this (it counts bucket-wide reads).
- **Place-data host:** bucket `sc-open-quests-data` (ENAM, empty) created by Claude; `sc-data.comentality.com`
  attached by the owner, ssl and ownership active. Owner's name choice over `street-complete-data`.
- **Cache Rule "sc-data cache" deployed by Claude in the owner's Chrome** (owner: "use chrome to do it yourself");
  JSON on `sc-data` now MISS then HIT with its own max-age. Test domain removed the same way; the test bucket and
  its objects deleted by API. `sc-open-quests-data` is empty again. Nothing open from this step: `sc-data` is ready
  for the place publish (DESIGN.md, "Place statistics for the whole world").

## Parked: retire the Python tile store (owner, 2026-11-16, about 22:25: "write down to return to this cleanup at some point")

- **What:** `tools/stream/tilestore.py` and `tiles.py` (about 1,400 lines). The Rust `tilestore/` replaced their cut,
  update and read; the live paths (`planet_store_day.py`, `world_cells.py storecut`, `storecheck_cities.py`) already
  run the Rust binary. Quest logic was never in either: it is the Kotlin engine's.
- **Still importing them:** `tests/test_tiles.py`, `tests/test_tilestore_update.py` (Rust update held against the
  Python one on the synthetic day); `tools/stream/tilecheck/` `storecmp`, `subcmp`, `why`, `edge`, `reledge` (Python's
  reader decodes the store); dead or nearly: `chain-z.sh`, `day12.sh`, `overpass/bench.sh`, `opbench.py`.
- **To do it:** a Rust `compare`/dump command (or keep a ~100-line Python decoder) for the tilecheck tools; tests
  against fixtures or osmium instead of Python; delete the dead scripts. Gain at a repin: the tile rule lives in two
  places (`AreaPass.kt`, Rust) instead of three.
- **When:** not before release 1's loop is caught up and checked (subcmp/why are its diagnosis tools); early
  December at the earliest. Not while the release-1 agents' worktrees are open.

## Parked: benchmark a native Windows osmium (owner, 2026-11-16, about 22:30: "lets put benchmarking it into todo")

- **It exists (checked 11-16, about 22:35):** conda-forge builds `osmium-tool` for win-64, versions 1.18.0, 1.19.0 and
  1.19.1 (the latest on every platform; the Docker image is 1.18). Not on MSYS2; osmcode's GitHub releases ship no
  binaries. No conda, mamba, micromamba or pixi is installed here: the install is one micromamba (single exe) or
  pixi, into its own env (no change to the Docker image). Not yet run: whether every command we use works there.
- **Why (as asked):** every osmium time we had went through Docker's mount (reads 4.5x slower, a pass 1.85x), so
  the Rust-vs-osmium figures seemed unfair to osmium. For history work native turned out slower, not faster
  (below); Rust `tilestore at` 1.4 s against native `time-filter` 21-24 s on Berlin.
- **Still to measure:** `fileinfo -e` and `extract -s smart` on a Europe clip (Docker: 19-20 s / 74 s through the
  mount, 4.4 s / 40 s on container disk), warm and cold, when the machine is quiet.
- **Decides:** whether release 2's monthly backfill (`backfill_history.py` slices and cuts) stays on osmium, goes
  native, or moves to Rust. Not before release 1's catch-up.
- **Switching, asked by the owner (11-16, about 22:40: "maybe we can look into switching to it now?").** The install was
  refused by auto mode (downloading and running micromamba): it needs the owner's explicit yes. Timings wait for a
  quiet machine (at 22:40 the store's catch-up and two release-1 jobs held about 46 GB). Every Docker osmium caller:
  - **osm-extracts** (`osm_extracts.py`, `OSMIUM_IMAGE`; shared with the other projects): `apply-changes -H` (the
    planet history kept current: 2-3 h a week through the mount, the biggest gain), clips' `extract -s smart`,
    `check-refs`, `merge`, `extract --with-history`, `time-filter`. Its own change, its own repo, all projects' runs.
  - **here:** `backfill_history.py` (`extract --with-history`, `time-filter`), `add_parts.py` (`getid -r`,
    `export`), `world_cells.py` cut (`extract -s smart`; the storecut from the Rust store replaced it in release 1's
    plan), `tilecheck/atcheck.sh` (test). The Overpass bench runs osmium inside the Overpass container: stays.
  - **How:** one knob per repo (`OSMIUM=docker|native` or a path), default Docker until each command's output is
    shown equal (same file through both: `osmium diff -q`, or byte-equal where the writer is deterministic), then
    the default flipped. Native osmium takes Windows paths, so the `/osm`, `/in`, `/out` mapping goes behind the knob.
    Order: the install and a smoke run of every command above; timings when quiet; here first (small, ours);
    osm-extracts after, its next weekly history update as the proof.
- **Installed and smoke-tested (11-16, 22:45-23:20; owner: pixi via winget, "both repos").** pixi 0.81.0 (winget
  `prefix-dev.pixi`, `%LOCALAPPDATA%\pixi\bin\pixi.exe`); `pixi global install osmium-tool=1.19.1`: launcher
  `~/.pixi/bin/osmium.exe`, the real exe `~/.pixi/envs/osmium-tool/Library/bin/osmium.exe`. Provenance checked:
  the package's sha256 equals anaconda.org's; the feedstock's recipe pins osmcode's v1.19.1 tarball, whose sha256
  matches a fresh download. Docker's image untouched.
  - **Same output, every command** (`.scratch/osmium-native/smoke.sh`, Bremen 11-02 and Berlin's history 261005,
    planet diff 5165): `extract -s smart -b`, `-s complete_ways -p`, `--with-history`, `time-filter`,
    `apply-changes`, `apply-changes -H`, `sort`, `getid -r`, `cat -f osm`, `merge` (pbf + xml), `export
    geojsonseq` all equal by `osmium diff -q` or text; `check-refs -r` equal but for CRLF line ends (parse
    tolerantly if switched).
  - **But native is 2-3x slower on history decodes and diff applies** (the machine was busy, both sides
    alternating, so ratios not absolutes; Docker's times include its mount): Berlin history extract 34 s against
    97 s; `time-filter` 8-12 s against 21-24 s; `apply-changes` 15 s against 42 s; `apply-changes -H` 41 s against
    113 s. Native was faster on the only snapshot extracts run (Bremen, 20 MB: 9.5/10.6 s Docker against 2.8/4.2 s,
    where Docker's start and mount may dominate). Not the file write (to a pipe the same); thread count barely
    matters (`OSMIUM_POOL_THREADS=1` 29-47 s, 4 and 8 about the default); not zlib (uncompressed, native reads
    Berlin's history in about 19 s, the same as compressed; Docker reads it compressed in 9 s). Only round 2 of
    the zlib rerun is clean (a Docker run overlapped round 1). `.scratch/osmium-native/threads.sh`, `zlib.sh`.
  - **Cause unknown.** Three things differ: version (1.18.0 / libosmium 2.22 against 1.19.1 / 2.23.1), platform
    and compiler, allocator. The Rust store's heap problem looked different (there one thread was faster).
    Cheapest discriminator: conda-forge's native `osmium-tool=1.18.0` in a second pixi env, same files.
  - **Not measured:** snapshot work at size (`fileinfo -e`, `extract -s smart` on the 1.75 GB Europe clip) and
    anything planet-sized; "the weekly planet update would get slower" is a projection from Berlin, not shown.
    The earlier "native osmium might be 5-10 s on Berlin" (this evening's Rust-vs-osmium answer) was wrong: 21-24 s.
  - **So nothing switched**, owner's call (asked). Test outputs deleted (5 GB); the three scripts kept. To remove
    the install: `pixi global uninstall osmium-tool`, `winget uninstall prefix-dev.pixi`. A mimalloc build of
    osmium (conda-forge `mimalloc` 3.6.1 has win-64) was refused by auto mode and is not the next step.
- **The owner's answer (11-16, 23:35): "we will have to retest on quiet machine. also please research reports about
  it on github or wherever they host".** The retest is open: `smoke.sh`, `threads.sh`, `zlib.sh` again with no
  store run, catch-up or release-1 job going (check `Get-Process tilestore*,python,java` first), plus the Europe clip
  (`fileinfo -e`, `extract -s smart`) and, if the owner allows its install, native `osmium-tool=1.18.0` beside 1.19.1.
- **Research (11-16, 23:30-23:45): no report anywhere of osmium being slower on Windows**, and no benchmark of it.
  - Searched osmcode/osmium-tool, libosmium and pyosmium issues, both conda-forge feedstocks, all of GitHub and the
    web. Rate-limited partway through GitHub's search, but the later broad searches returned nothing relevant.
  - **Windows is built, not tuned:** the maintainer, in osmium-tool#59, "I personally don't know anything about
    Windows"; Windows issues there are about compiling (#263, #59), never speed.
  - **conda-forge's build is a plain CMake Release build** (`recipe/build.bat`, Ninja, MSVC); no allocator choice,
    so it runs on the default Windows heap.
  - **One concrete lead, for diff applies only:** libosmium 2.23.1 `osm/timestamp.hpp` parses XML timestamps with
    `_mkgmtime` on Windows (`timegm` elsewhere). libosmium#363 found the same call (`timegm`) made XML parsing
    1000x slower on iOS and was closed as the vendor's problem. `.osc` diffs are XML, so `apply-changes` could pay
    this. PBF timestamps are integers, so it cannot explain `time-filter` or `fileinfo -e` on PBF.
  - **General Windows heap evidence, not osmium's:** an LLVM RFC measured the CRT allocator at 38 min against
    mimalloc's 2 min 22 s on a 36-core link; GDAL users reported `free()` of many small allocations slowing more
    than linearly. libosmium allocates per block in its pool threads, so it fits, but is still not shown.
  - libosmium's changelog 2.22 to 2.23.1 names no speed change, so a version regression is unlikely but not ruled
    out (that is what native 1.18.0 would test).

## Blog draft: how StreetComplete quests age (owner, 2026-11-17, late evening)

- Owner: "write an article ... it will go into our future blog". Draft at `blog/how-streetcomplete-quests-age.md`
  (front matter `status: draft`). It covers which quests age, the intervals (from SC's quest filters, counted in
  the `StreetComplete-fast` checkout; the Temp `sc-v64.0` checkout has no sources left), how "older" is decided
  (`ElementFilter.kt` `CompareTagAge`), what an answer writes (`ResurveyUtils.kt` `updateWithCheckDate`), and why
  the site splits resurvey from mapping. No blog exists on the site yet; nothing links to it.
- Owner: "should reference sources in that cool wikipedia way". Now 32 GFM footnotes under "References", each a
  line-pinned link into SC's **v64.0** tag (sources fetched sparse to Temp `sc-v64.0-src`; every link checked to
  land on the cited line). Counts redone on v64.0: 67 of 192 quest types age. Cash and cards aging is on SC's
  unreleased main only (cited at c994ef37) and sits in a "Coming next" note. The draft's numbers are no longer from
  `StreetComplete-fast`, which is main plus the owner's fork.

## Line endings: LF everywhere (owner, 2026-11-17, evening: "we often stumble on LF vs CRLF ... fix it for good")

- Cause: `core.autocrlf=true` (Git for Windows' system config and `~/.gitconfig`) checked 5,449 tracked files out
  as CRLF, while every tool here writes LF (Python `newline="\n"`, the engine, osmium, Claude's Write). A file was
  CRLF if git last wrote it and LF if a tool did, so the same file differed between main and a worktree. That
  broke Edit matches, byte compares, the R2 copy of `_headers`, and the folder-by-folder LF pins in `.gitattributes`.
- Fixed in `.gitattributes`: `* text=auto eol=lf` first, `*.bat`/`*.cmd` CRLF, `docs/vendor/**` untouched. Plus
  `.editorconfig`. The index was already LF, so that commit changed no file.
- **Still to do, once no other session or long run is live:** rewrite the files still CRLF on disk (about 5,450).
  This skips anything with uncommitted changes (dry run without `--apply`):
  `python ~/.claude/skills/kk-line-endings/rewrite.py . --apply`
  Afterwards `git ls-files --eol | grep -c w/crlf` should print 3: `gradlew.bat` and the two vendor files.
  Worktrees made before the fix need the same command run inside each one.
- The owner's lazy recipe for any repo that trips on this is the `kk-line-endings` skill; a hook asks for it
  (2026-11-17). This repo has had it applied: `.vscode/settings.json` sets `files.eol` to LF, and CLAUDE.md
  carries the rule for program output.
- Not covered by attributes: output a program writes (untracked, `.scratch`). Write it with `newline="\n"`, and
  compare text without regard to CR. `engine/sync-sc.ps1` records the raw-byte sha256 of each vendored file, which
  depends on the SC clone's own line endings. Under LF those hashes describe CRLF bytes the repo no longer has.
  Nothing re-checks them, but normalize them on the next sync.

## Parked, distant future: other validators' backlogs (owner, 2026-11-17, about 00:10: "an expansion sort of feature for distant future")

- **Idea:** chart other QA tools' open issues per city over time, the same way we chart open quests. Searched
  2026-11-17 and found nobody doing it. Details in PRIOR-ART.md, under "Validators charting their own counts
  over time".
- **Possible sources:** Osmose's daily count per check (`/en/issues/graph.json?item=&country=`; it splits by its
  own regions, so it would need its issue points clipped to our polygons instead); KeepRight's daily dump of
  open errors for the whole planet, downloaded every day (but KeepRight is unmaintained since April 2024);
  `fixme=*` and similar tags counted from our own extracts.
- **When:** not on any release's path. Pick it up only after open quests over time have shipped.

## Parked until Release 1 is out: retire the daily city run (owner, 2026-11-23, 12:40: "its ok to wait, add it to the list of work")

- Owner asked why the cities are still processed when the world has the same daily data. The numbers no longer
  need it ("World vs the daily run's cities: they agree"; clock decided, midnight UTC), but the run carries
  other things. Nothing built; not to start before Release 1, and after the heap and disk branch is merged
  (the same code).
- **What `run.py update` still carries:** the Europe clip and the daily diffs (the world's input and its gate's
  oracle: the world stood still on 11-23 when this run died on Docker); the site's city snapshots in `docs/data`
  and their push; the monthly history from 2017-01 (the world starts 2026-11-01; its monthly backfill is
  Release 2); the cloud publish, the archive backup (the world's gated days too) and `check-release`.
- **To retire it:** (1) the Europe clip and diff fetch, the archive backup and the release check move into the
  world's daily run; (2) the site's city pages built from the world's `osm-<city>` counts; (3) the 2017-2026
  monthly city series kept frozen, or replaced when the world's monthly backfill exists; (4) the Canadian and
  German fetches and the per-region engine runs stopped. Saves about two hours of machine a day and the
  memory competition behind two of this week's stops.
- **The city gaps stay until then (owner, 11-23, 12:49: no action now, the joining of cities and world fills them).**
  Not counted by the city run: Ontario 11-19 and 11-21; the other Canadian regions, Berlin, Hamburg and Bremen
  11-18, 11-19 and 11-21; all twelve 11-09; a few older days by region. Europe's four lack 11-22, expected from the
  next run (the clip was filled at 12:37, after the city run). `osm-extracts fill` makes clips only, not these twelve.
  **So (2) must read the world's `osm-<city>` counts back to 2026-11-01, not from the day of the switch**, or the
  gaps stay. Checked again on 11-23 at 23:20, after tonight's work (owner's ask).

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
