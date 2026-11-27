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
