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
       `../sc-open-quests-stable` and branch `world-stable` can be removed (removed 11-26); after 11-29 `back` starts to
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
