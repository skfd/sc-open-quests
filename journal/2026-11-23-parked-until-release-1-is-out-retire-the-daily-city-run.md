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
- **Asked again 11-24, 14:55 ("are we ready to turn off city machinery ... keep the monthly backfill?"). Read, nothing
  changed: not ready.** Of the two waits only Release 1 is left (23 gated days of 30; the branch merged this morning).
  - **The pause recipe (`data/cities.paused` and the task disabled) now stops the world by the next day:** the diff,
    the Europe clip and the notes dump come only from this run's download step (today's loop took diff 5186,
    `europe-2026-11-24`, `planet-notes-261124`). `fetch planet-diffs` cannot stand in: it counts from a history file,
    deleted 11-16. It worked in the backfill because those files were on disk. **The world's least daily need:
    `fetch europe`, `fetch notes`, `archive_backup.py`**; those three run on their own before anything is stopped.
  - **Missing from the list above:** denominators (`counts.json` has none; the compare view's per-road-km and the
    history files use `highwayKm`); `docs/data/quests.json`, built by `history` from the regions' `quests.json`
    (the world place pages load it too); the widget reads `docs/data/{cities,quests}.json`, `history/`, `parts/`;
    neighbourhoods: all 147 `osm-<city>` are in the world's 11-23 counts, 41 of the 4,214 parts are not (by id; 16
    Berlin, 8 Hamburg), and the rest were checked for presence, not for equal numbers; `world_compare.py` last ran to 11-13,
    before the swap, and Canada and Germany are in no daily gate: rerun it, in a gap, before the switch.
  - **The saving, from today's log (12:15-13:36, not two hours):** the twelve Geofabrik downloads 53 min (4.5 GB),
    `fetch europe` 4, notes 17 s, notes clips 2, Canada and Germany counted 6, Europe's four 8 (with 11-22's catch-up),
    history and publish 7. Memory: the region engines' heaps, `minHeapGb` 27 for europe-central. No sibling project
    relies on this run for Ontario: `toronto-streets-osm` and `address-importer-friend` fetch it themselves.
  - **"Monthly backfill":** the 2017-2026 series in `data/archive` stays (frozen, on R2); `kk-SCOpenQuests-planet`
    already off since 11-16, its history file deleted; `tools/backfill_history.py` stays (imported by
    `world_cells.py`; Release 2's base). The only history left for the cities is
    `canada-germany-history-261102.osh.pbf` (5.5 GB): keep it; Europe's would need a planet download.
  - **Done at the owner's word (11-24, "Delete both"):** the sidebyside task (ended 11-14; its XML is in
    `~/Code/.task-backups/kk-SCOpenQuests-sidebyside.2026-11-24-before-delete.xml`) and the eight dated `canada-germany`
    clips; kept: the history file, the metas and `canada-germany-latest.osm.pbf` (the 11-14 clip's other name, so 9 GB
    came free, not 10). `latest.json` names a file that is gone: the clip is dead until a recut. Their only
    reader found was `.scratch/side-by-side/compare.py`. Disk 101 to 110 GiB free, mid-day, against the loop's 115.
- **Begun before Release 1 (owner, 11-24, 15:05: "go ahead with your recs, we can do it before release 1").** On branch
  `retire-cities` (worktree `../sc-open-quests-retire`, ef5ce98e), 264 tests OK, the compare page looked at; **to merge
  only between two world days** (`run.py` and `planet_store_day.py` are the loop's), then `schedule-inputs-add.ps1`:
  - `run.py inputs` (task `kk-SCOpenQuests-inputs`, 11:15, log `logs/inputs.log`): `fetch europe`, `fetch notes` (three
    tries, 10 min apart), the facts' and the world's backup, `check-release` (gone from `update`). It holds
    `data/inputs.lock` while it fetches; the loop waits for it up to an hour. `update` still fetches both (no-ops then).
  - `docs/data/quests.json` from `tools/site_quests.py` (`config/site-quests.json` + cities' country codes; byte for byte
    today's file for 147 cities); REPIN.md step 5 has `take`.
  - The compare view's "Per road km" is gone (owner: "we dont want that feature"), and `highwayKm` from the site's files.
  - **Left:** the city pages from `osm-<city>` (waits for the neighbourhoods' answer, a session of its own:
    "City neighbourhoods missing from the world counts"; parts sit inside the same snapshots), `world_compare.py` rerun in a
    gap, the site deploy's new home, then the city task off. The widget's files come with the city pages.
- **City pages from the world begun (11-24, 17:20; the neighbourhoods are answered, next section).** Branch `world-cities`
  (worktree `../sc-open-quests-world-cities`, off `retire-cities`): `tools/world_cities.py` turns each gated day into region
  snapshots of today's shape (`data/archive-world`), `run.history(world=...)` joins them to the archive at 11-01; parts are
  the world's alone. Seven tests OK on made-up data; **not yet run on the real counts** (waits for the loop's day). Nothing
  calls it and `docs/data` is refused without `--live`. The rule for which quests a city counts matches the newest
  snapshot of all 147 cities. The world has no `taggedNodes`/`taggedWays`/`openAllNotes` (the site reads none of them).
  **Run on the real counts 11-25, 01:31-01:45, beside no loop (into a session scratch folder; nothing of main or the site
  written): it agrees.** 23 days in about 5 min, the build 2 min 36 s, 4,654 files. Against `docs/data`: all 52,728 city
  series before 11-01 identical; the quest sets and the null pattern identical in all 147 cities; Europe's four regions
  on the same day, 11-03 to 11-23: sums of `open` +4 to +10 of 19 million, 99.7% of cells equal, `agedOnly` 99.97 to 100%;
  the other regions (world D+1 against city D) -0.001 to +0.005%, 98 to 99% equal (93% on 11-04, few cities). **11-01 and 11-02
  step: the city run was on StreetComplete 64.0 on 11-01 and part of it on 11-02, the world is on 64.1 from 11-01**
  (+0.27% in Europe, nearly all `AddAcceptsCards` and `AddOpeningHours`), so the release step in the charts moves to 11-01.
  The world fills the days the city run missed (Toronto: 161 dates, 157 before). Parts: the same 4,214 files, the same 86
  empty, world 11-23 against city 11-22: 200,271 cells equal, 950 differ, sums +571 of 23.8 million. One quest left out:
  Bratislava's `AddCycleway` (open in the world there, not a quest the city counts). Full tests on the branch: 271 OK.
  DATA-FORMAT.md written. `coverage.json`, `quest-releases.json` and `sc-releases.json` are not part of this build. **Not done:
  anything live; the dates' guard needs 11-24 closed. Next: the owner's word on going live.**
- **Day 11-24 starved, 11-24 19:05 (not stopped yet; the engine room gives up about 19:23).** Tier 2 `new`, about 112 of 127 groups;
  no engine since 18:23: 10 GB of commit left, 16 needed (8 and 8 kept back), disk 42 GiB. Commit was 98.6 of 108.6 GB at 19:04:
  the loop's own python 16.9, 54 claude processes 16, pools 23, Windows Terminal 4.5, WSL/Docker 6 (one container,
  `onagri-pg`). **Partly this session's doing:** a recursive `grep` of 15:23 and a `du` of `.scratch` of 17:03 went on running
  after TaskStop said they were stopped (their `.exe` children outlive it); ended at 19:04, about 2 GB came back. The
  neighbourhoods session was also running scripts (`areas_to.py`, about 3 GB) from 18:30 on. Owner, 19:06, asked what may be
  closed: **"Nothing, let it stop"**; resume in a quiet gap. `retire-cities` waits for the day to close, not for its stop.
  **Corrected 20:50: it stops about 22:24, not 19:23.** Each of the four workers gives up after its own hour and takes the next
  group: f112, f114 to f116 gave up about 19:22, f117 to f120 about 20:22, f121 to f124 wait until about 21:22, then f125 to f127.
  `rect_rows` leaves its pool without cancelling what is queued. f112's failure is already recorded, so this run ends in STOPPED
  even if memory comes back (read from the code; not waited out). 112 of 127 groups have an engine's result. 20:47: commit 99.8
  of 108.6 GB, disk 40.7 GiB, 0.7 over the floor under which `loc advance` and `compact` refuse.
- **STOPPED 22:23:37 on 11-24, 11-24 in `world finish` (tier 2 `new`, f112 first), for want of commit; not restarted, owner
  asked.** Copy: `.scratch/anomalies/STOPPED-2026-11-24.txt`; STOPPED is still in place. The process freed its memory by
  22:25; task Ready. `day.pkl` there, `finished` absent: the documented resume redoes `finish`. **At rest, 22:27: 26.4 GB of
  commit left (82.2 of 108.6 committed), and the loop's python itself reached 17 GB in tier 2 `new`: a resume now would
  stand at 9 GB again and starve the same way.** It needs about 34 GB at rest for one engine at a time, 41 for two (11-23 at
  rest: 37). Read off the log: 22 GB left at 17:20 (`old`, one engine alive), 16 at 17:30 as `new` began, falling to 7.
  **Disk 40.3 GiB:** all 127 of `before/`'s files (52.6 GB) are already replaced, so the resume's restore gives about 52 GB
  back and finish takes it again: expect about the same low, on the 40 GiB floor. It wants about 10 GiB more free first.
  Nothing closed or deleted. When both are there: remove STOPPED, start the loop with `WORLD_T2_WORKERS=2`.
- **Resumed 23:06:34 on 11-24 (owner, 23:00: "yes enable and start engine to run. we want to progress", to closing Docker/WSL
  and idle sessions).** Loop pid 62096, `WORLD_T2_WORKERS=2`, two group workers; the world was put back to 11-23 at 23:07:50,
  disk 40 -> 93 GiB. Commit at rest 35 GB (26 before): Docker Desktop and WSL stopped (`docker desktop stop`, so `onagri-pg`
  comes back with Docker), and seven finished sessions closed: Osmium Windows speed, Skills and steward review, Weekly advisor
  11-23, Should the done-check exist, Task Beholder, Crs Guessing Game, mapsme-fork-watch-2d (transcripts kept). `vmmem`'s
  4 GB is another virtual machine (`vmwp`, since 11-21), not WSL's; left. **35 - 17 - 8 leaves room for one engine at a time,
  barely.** Disk nothing deleted: the low will be near 40 GiB again, where `loc advance` and `compact` refuse; those steps
  resume cheaply once disk is there. Candidate, not approved: `.scratch/planet-day/clip-1103` to `-1105`, 7.3 GB.
  **Deleted at the owner's word, 11-25 about 17:35** (43.2 -> 50.5 GiB free, 11-25's tier 2 `new` just done); `.scratch/planet-day/run*.sh`,
  one-off scripts of 11-16, still name them and would cut them again from Europe clips that may be gone.
  **Docker must be started again before the 12:15 city run on 11-25.**
- **11-24's gate PASSED; STOPPED 01:30:14 on 11-25 at `compact`, under the disk floor (39.0 GiB free), nothing written; not
  restarted.** Tier 2 ended 01:01, gate 20 of 32 equal, clip 19,335,063, world 19,335,075 (+12), worst city 0.00177%. Store at
  generation 23, node file and world at 11-24, `finished` there; what is left is `compact`, the day's record, the delete of
  `world-days/2026-11-24` and the facts. Commit 48 GB free now. Copy: `.scratch/anomalies/STOPPED-2026-11-25.txt`.
  **Clearing the floor is not enough this time: this compaction copies packs 18 and 21, 41 GiB, before it deletes anything**
  (11-21's copied 0.09), and only the start is checked against the floor: 39 + the clips' 7.3 GiB would pass and run the disk
  down to about 5. It wants 82 GiB or more free. `world-days/2026-11-24/before` (52.6 GB, the world at 11-23, hard links no longer shared) is the
  day's way back, read only by a `finish` that did not end; after the gate nothing reads it, and the loop deletes it minutes
  after `compact`. Deleting it by hand first gives 91 GiB. **Asked of the owner, nothing deleted.** Docker is still off.
- **11-24 CLOSED 02:12:31 on 11-25** (owner, 02:00: "go ahead"): `before/` deleted (disk 31 -> 85 GiB: 8 GiB had gone in
  the half hour before, not traced), loop restarted 02:03. `compact` removed 59.5 GiB of files in 169 s, low 44 GiB; 129 GiB
  free after. Store generation 23; world 24 gated days, 11-01 to 11-24; its facts written by hand (02:20).
- **`retire-cities` (37a66bd3) and `world-cities` (a2a626bf) merged into main, 02:13-02:20; 271 tests OK; worktrees and
  branches removed.** `kk-SCOpenQuests-inputs` is registered (daily 11:15) and ran once, 02:13-02:19: the Europe clip of
  11-25 with diff 5187, the notes dump of 11-25, the two backups, "inputs done". **`run.py history` on the merged
  code changes 148 files, by `highwayKm` alone (the per-road-km figure the owner dropped); committed.** The 12:15 city run deploys
  `docs`, so the dropped column reaches the site then. Docker is running again (`onagri-pg` up).
  Still the city run's: the site deploy (`publish_cloud`) and the city counts. Still open: the owner's word on switching the
  city pages to the world; a new home for the deploy; then the city task off.
- **The city pages are switched to the world's counts on main (owner, 11-25, 03:20: "yes switch"); fb0d8422 code, 20e9fe45 data;
  pushed 06:47, below.** The 12:15 city run deploys it from the working tree; **it probably will not push: `publish` returns before
  `git push` when `docs/data` has nothing new to commit, and from now on each day's data is committed only when a new gated day
  changes it. So a push is asked for, or built into the new deploy.** `run.py history` for `docs/data` first writes the world's missing
  days (`data/archive-world`, 19 s each) and always joins them; `migrate_archive`, which each city `count` runs first, would have
  moved the world's published snapshots into the city archive: it now skips them. 273 tests OK; a second build changes 0 files.
  Against the files before: 52,728 series before 11-01 identical, no date and no quest lost, Europe's 11-24 +6 of 19,335,063.
  Wording: the footer says "OpenStreetMap at 00:00 UTC that day", neighbourhoods "from the daily count of the whole world".
  Toronto, Casa Loma, Berlin, Paris and the compare page opened locally, no page error.
  - **The pages are older until the deploy moves:** at 12:15 the newest gated day is yesterday's 00:00 UTC. Europe is a day
    behind what the city run gave, Canada and Germany's three about 21 hours, under the same date.
  - The task's own `python` imports numpy; the phone widget reads none of the fields the world's snapshots lack.
  - The city run still counts all its regions: nothing but `world_compare.py` reads them now.
  - Way back: `git revert 20e9fe45 fb0d8422` (the archive is whole), then `run.py history` and a deploy; a revert alone
    leaves the live site as it is.
  **Pushed 11-25, 06:47 (owner: "pusj and thats it?").** The site itself changes at the 12:15 deploy.
- **Publishing is the world run's last step (owner, 11-25: "do both please"; step 1).** `planet_store_day.py` ends with `run.py site`
  (`publish()`, after RUNNING is gone; also when it took no day or stopped; log `logs/site.log`): first `world_publish.py daily`, then
  history, commit, push and deploy if the site lacks the day or docs/ changed. `inputs` (11:15) runs it again for what failed.
  Tasks `kk-SCOpenQuests-site` and `-worldpub` are removed (XML in `~/Code/.task-backups/*-removed-2026-11-25.xml`). The 20 h and 36 h rules
  went: **a committed docs/ change goes live at the next run.** A catch-up of several days publishes once, at its end.
  **Step 2, on main (1a7dd1f4, 11-25 12:06):** the page joins the history file's dates before 11-01 to the world's days on sc-data;
  `world_publish.py` writes `city/`, `city-parts/`, `cities.json`, `city-trends.json`, `city-quests.json` (DESIGN.md, "The counted
  cities"). Without them (or with sc-data down) the page falls back to today's files. Compared in a browser for all 147 cities,
  4,214 parts, 193 compare files, trends and totals: 44,355,752 values, 0 different (`.scratch/city-test`). 285 tests OK.
  **Done 11-25, 12:53-13:24:** `planet_store_day.py --max-days 0` ran the hook (exit 0, 31 min: 23 of them the events cache, rebuilt because
  the city list joined its stamp); 297 city files up, verify and live check 0 mismatches; live Toronto, Berlin and compare read them.
  Not yet seen: the hook after a run that took a day (tonight). **The cache rebuild costs about 1 min per gated day, so a changed
  quest list (an SC release) or city list costs 25 min now and hours by next summer; nothing done about it.**
  **`latest.json` gets `questsFrom` (d33b0565):** the first counted day of a quest a release adds, so it is null before (page and widgets), not
  a rise from 0. Empty until SC's next release, so seen in tests only. The page's part goes live with the next `run.py site`.
  **Both widgets read sc-data (owner, 11-25: "yes"; `../sc-open-quests-widget` c3cf6d6):** compared with the old files for 147 cities and
  4,214 parts, 10.9 million values, 0 different; Android on the emulator, Scriptable in the preview. APK and script in ~/Dropbox/my-apps.
  They still read the site's `data/cities.json`, `quests.json`, `parts/` and icons.
  **`docs/apps` has the new script (285f9061; owner, 11-25: "yes"),** the widget repo's checks all ok; live with the next `run.py site`
  (tonight's loop), so check `/apps/open-quests.js` after it. iPhones that have the old script keep it until it is downloaded again.
  **Live 11-25 18:40 with the loop's publish of 11-25** (`/apps/open-quests.js` equal to `docs/apps`).
  **The city files end on a set day: merged 11-25 18:50 (b4c1f7b6; owner: "yes, do it in a safe way").** `config/city-files.json`
  `{"until": "2026-11-25"}`: `history/`, part series, `trends`, `compare`, snapshots and `cities.json`'s counts stop there, so a new day
  needs no commit and no deploy (DESIGN.md, "docs/data's own city files end on a set day"; undo = revert, the next site run writes
  the days since). Not 10-31 as first said: the last published day, so the switch moved no byte and the no-sc-data fallback is as new
  as it can be. `run.py site` deploys only when the tree of `docs/` or `config/` is not the deployed one (`data/site-deployed.json`
  keeps "day" too, for the old code). **Checked before merging:** 290 tests OK; the branch's `history` in main wrote 0 files
  (`git status docs` clean); pages from a copy of `docs/` with the 11-24 data, through a local CORS proxy to sc-data and with
  sc-data down: Toronto, picker, compare (175-185 kinds), Berlin, map, a part (Agincourt North), the parts card from the files'
  own day; no error but the blocked fetches. **After:** `run.py site` once: history 0 files, nothing committed, 1 file deployed
  (`app.js`, live equal), pushed; a second run "nothing to do", pushed.
  **`kk-SCOpenQuests` (12:15, `run.py update`) disabled 11-26 11:15 (owner: "yes", then "can you do it now while we are on hold for
  world dailies?"),** before its run of 11-26, so the new code was never seen under `update`. **Deleted 11-26 (owner: "delete task"):**
  `schedule-add.ps1` makes it again.
  It downloaded the city extracts, counted them, published and backed up `data/archive`; `data/archive` and its 2017-2026 history stay
  as they are, and `tools/backfill_history.py` still works by hand. Back on: `Enable-ScheduledTask kk-SCOpenQuests`.
  **Not yet seen:** a loop day taken under the new code (the world dailies are on HOLD since 11-25 20:05): its publish should be place
  files only, no commit, no deploy, main pushed. **Left:** the owner's phones on the new builds (Android not confirmed).
- **The site's deploy is its own run, and the world's city pages are live (owner, 11-25: "yes"; 194d497b, 44ec7856).** `run.py site`, task
  `kk-SCOpenQuests-site`, hourly 07:20 to 23:20, log `logs/site.log`: when the newest gated day is not the one in
  `data/site-deployed.json` (not committed) it does history, commit, push (now also with no new data) and deploy; a change of
  `docs/` alone goes up 20 h after the last deploy. Not while the loop's RUNNING is there (unless the last deploy is 36 h old),
  under 8 GB of commit, beside another holder of `pipeline.lock`, or off main: the next tick tries. 2.4 GB of commit at its peak. 281
  tests OK. **First tick 07:20-07:22 on 11-25:** pushed, 4,465 files up; `cloud_publish.py --check` 9,338 files equal live;
  a second run said "nothing to do". Not yet seen: a tick that takes up a new day by itself (tonight's 11-25 day, or 07:20 on 11-26).
  `update` (12:15) does the same deploy, so both may run until the city task goes.
- **`world_compare.py` rerun for 11-14 to 11-24 (07:05, beside no loop; `.scratch/world-compare-1124`): it agrees.** `open`: 1,210 city-days on the
  nearest clock, 725 exact, median 0.000%, p90 0.003%, worst 0.212% (Oshawa 11-23, clocks 2.6 h apart); same clock (Europe) within
  0.002%; sums +2,270 of 363 million. `agedOnly`: 1,126 of 1,210 exact, worst 1.085% (Oakville, 11-20), sums +100 of 11.4 million.
  **Left: the city task off (asked of the owner 11-25; wait for one new day taken up by the site run).** The loop does not need it:
  without a city run its `SCHED` check finds no "=== download" and does not wait.
