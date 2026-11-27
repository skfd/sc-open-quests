## Legal pages: the list agreed, nothing built (2026-11-24, late evening; owner: "this website needs terms of use and some other legal stuff like cookie consent")

- **Checked first:** no cookies (none set in `docs/`, no `Set-Cookie` and no Cloudflare beacon on the live home page);
  one `localStorage` key, `sc-open-quests-cities` (recent cities, stays in the browser); GoatCounter
  (`osm-ontario.goatcounter.com`, its no-cookie, no-IP terms recalled, not re-read). A visitor's IP reaches
  Cloudflare, GoatCounter, tile.openstreetmap.org (Map tab) and GitHub (place requests).
- **Owner's answers:** operator named as the handle `skfd`, no real name; based in Canada (no imprint); contact is
  GitHub issues only, no email on a page; nothing planned (no ads, donations, accounts or forms).
- **To build, in order:** (1) a privacy page naming the four parties and the one key; Google Play needs its URL for
  the widget; (2) a line that the published JSON is offered under ODbL (footer and `DATA-FORMAT.md`; neither says so
  now); (3) a short terms page: counts are estimates with no warranty, the data may be reused under its licence
  without hammering the host, the borders stance, links to the vendored libraries' licences; (4) "independent, not
  affiliated with or endorsed by StreetComplete or OpenStreetMap" on the site and in the store listing; (5) operator
  and contact; (6) links to these from `docs/index.html`, `docs/apps/`, the Android about screen and the Scriptable
  script header.
- **Not needed:** a cookie banner (returns only with ads or cookie-based analytics); DMCA, children's, account or
  refund terms; an imprint.
- **Open:** whether to ask StreetComplete's maintainer about the name and icon in the Play listing (trademark status
  not looked up).
- **Built 2026-11-25 on branch `legal-pages` (c35215ed), not merged, not live (owner: "build the pages please"):**
  worktree `~/Code/sc-open-quests-legal` (sparse: `docs/*.html`, `docs/apps`, `docs/img`, the md files; new paths
  there need `git add --sparse`). `docs/privacy/`, `docs/terms/`, their `docs/legal.css`; a footer paragraph in
  `docs/index.html` (independent, privacy, terms, ODbL); the ODbL line in `DATA-FORMAT.md` and README. GoatCounter's
  terms were read (help/privacy, dated 2025-06-08) and the page words them as its own claims. The widget repo has a
  `legal-pages` branch too (34b0c50: apps page generator footer, Scriptable header, two buttons in
  `MainActivity.kt`); `docs/apps/` on our branch is regenerated from it.
- **Not verified:** nothing was opened in a browser and the Kotlin was not compiled (the world loop was running);
  only tag balance and LF were checked. Merging our branch publishes at the next daily run, since it syncs all of
  `docs/`. Merge both branches together, or the `--check` of `docs/apps` goes stale.
- **Merged 2026-11-25, afternoon (owner: "merge"):** both branches are on their mains (ours 21e105f8, the widget's
  34b0c50, fast-forward) and deleted, the worktree removed; `apps-page.js --check docs/apps` passes. Both pages were
  then opened headless from `docs/` (phone light, desktop dark: no overflow, no failed request; shots in
  `.scratch/legal/`). **Live with the daily run of 11-26, 12:15**, which pushes main and syncs `docs/`; after it,
  open `/privacy/` and `/terms/` on the live site and the footer links. Still not compiled: the two buttons in the
  widget's `MainActivity.kt`. Neither repo was pushed by hand.
- **Still for the owner:** whether GoatCounter's "individual pageviews" setting is off (the page
  assumes the default); no governing-law clause was written; contact is a public GitHub issue.
- **2026-11-25, 17:10: `place-ids` is brought up to main (f37f487a), still not tested.** New since the plan: `data/archive-world` (renamed too), the
  publisher's `city/` and `city-parts/` files, and **the loop publishes by itself after RUNNING is gone** (`run.py site`), so
  `apply` also refuses while `pipeline.lock`, `inputs.lock` or the publisher's `daily.lock` is there. 11-24 closed on 11-25 at
  02:12; `world-cities` and `retire-cities` are merged; `freeze-city-files` (new, no ids) merges clean. `dropped-places` now
  conflicts with main in `run.py`, not with `place-ids`.
  A rename must also hold back `run.py site`'s own publish until the big upload is done by hand.
  The gap: after 11-25's day closes and its publish ends (tonight) until 11:15 on 11-26. Tests there first.
  **Order in that gap (11-25, 17:40): `freeze-city-files` goes first** (brought up to main, 6cf26e08; tests, byte compare, merge, one
  `run.py site`); `place-ids`' tests after it is merged or says here that it is not. The two branches merge clean.
  **`freeze-city-files` merged 11-25 18:50 (b4c1f7b6), its `run.py site` done 18:54; nothing of it is running: `place-ids`' turn.**
- **Owner, 2026-11-25 (about 17:15): "yes rename if they pass"** (asked: rename tomorrow night, 11-26, if the tests pass tonight; it was said
  that about 1.13M files are uploaded again and old links break). Read as: the rename and the upload, under HOLD, after the
  tests pass. **The deletes of the old bucket files were not named in that question: ask before them**, after the `--dry-run`. `upload`
  as written refuses when the deletes pass `--max-delete`, so it needs a way to upload and keep the old files first.
- **Order in tonight's gap agreed with the session "City machinery deprecation readiness" (11-25, 17:40):** `freeze-city-files` first; `place-ids`' tests
  wait for its "merged" or "not merged" (119a95b0), then main is merged into `place-ids` and the whole suite is run. Nothing of `place-ids` runs before.
- **`place-ids`' tests PASSED (11-25, 19:05, in the gap after `freeze-city-files`):** main merged in (97def2b0), the whole suite 351 passed, 3
  skipped (two need the Rust tilestore, not built in that worktree; main: 339 passed, 1 skipped). The first run found a real bug, fixed in
  88250657: `places.build()` called `assign()` again without the registry. **Not merged into main yet:** it goes in
  at the rename, 11-26 night, by the owner's go (merge, mint, back up, plan, apply, check, rebuild, upload `--keep-gone`). The worktree is no
  longer sparse.
- **World dailies PAUSED (owner, 11-25, 20:00: "do things asap, pause world dailies until we implement all the new things").**
  `.scratch/planet-cut/HOLD` placed 20:03 (the loop logs "held" and takes no day; nothing else stops). The rename runs tonight, not 11-26
  night. **Lifting it is the owner's call**: delete HOLD; the next run catches up the days it missed. The 11-26 18:45 wake-up is moot.
- **The rename, 11-25 night (under HOLD), as far as it has gone:** `place-ids` merged (02c86d1d; suite 353 passed). **Minted** 1,082,287 ids from
  10-21.0 (`data/place-ids/registry.tsv.gz`, gitignored, sha256 b3d75207...), **backed up** to `sc-open-quests-archive/place-ids/`, downloaded
  again: same hash. **Renamed**: config/parts 4,214 ids (d39e8e4d), the archives 406,136 in 577 snapshots, world-1101 28,694,016 in 2,216
  files, plus the seed's 128 engine snapshots and `report.json` (`rename_places.py check`: 0 files with an old id). The outline cache
  stayed current. **Name layer** rebuilt (f9ae6961): the same as before under the map, 707 files only reordered (ties sorted by id).
  **History** (run.py history) byte for byte the old files under the map. Running: facts `--force` and verify, the publisher's build.
  Left: publisher verify, upload `--full --keep-gone` (deletes wait for the owner), `run.py site`, checkpoint, message the two sessions.
- **Order agreed with "Overture place sizes by area" (11-25, about 20:45):** it merges `dropped-places` now (the 16 duplicates and, by the
  owner's new decision, 63,800 small squares by a rule, `tools/small_squares.py`, read by GERS id; it translates `dropped-places.json`'s
  ids itself). Then this session rebuilds the name layer and history once more, rebuilds the publisher's files and uploads once.
- **Rename, continued (11-25, 21:25):** facts rewritten and verified (2,375 days, 0 different). After `dropped-places` (dae1a357; suite 362 passed)
  the name layer and history were rebuilt again without 63,816 places (b6baff26). The publisher's build (`site2`, v f1b38408abd4) verified:
  0 mismatches. **Uploading** since 21:25: `world_publish.py upload --full --keep-gone`, 1,063,089 files, log `.scratch/overture-next/upload.log`;
  it saves the bucket manifest after each 50,000, so if it stops, the same command resumes. 1,129,125 old files are kept (old ids, the
  dropped places): until the site is deployed the live pages ask for the old ids, and those files stay. Next: `run.py site`, then the old
  files' deletion only on the owner's word, after `rclone delete --dry-run`.
- **THE RENAME IS DONE AND LIVE (11-25, 23:20).** Upload 21:24-23:02 (97 min, 1,063,089 files, 22 batches); live check 0 mismatches over 40
  files. `--keep-gone` now keeps the old files in `bucket.json` "kept" (c820931a), so `daily` plans no deletes: **1,129,125 old files
  (old ids and the dropped places) are still in sc-data, waiting for the owner's word; then `world_publish.py upload --delete-kept
  --max-delete 1200000`.** The site: the first `run.py site` stopped at the site bucket's `--max-delete 2000` (6,254 stale docs files;
  the bucket is a mirror of docs/, so nothing was lost and the old site stayed live); `cloud_publish.py --max-delete 7000` (new option)
  deleted exactly those 6,254 and deployed (8,169 files), then `run.py site` recorded the deploy and pushed main. `cloud_publish --check`:
  8,925 files equal. Headless: the Annex by its new id (series from 11-01), Germany by its new id and Toronto load with no error or failed
  request. **Not done:** `state_checkpoint.py link`/`upload` (R2's checkpoint still has the old ids in place-sets.json: take a new one
  before relying on it); the `share-previews` branch's test links (old ids; done 11-26, d269fe58); the facts' and archives' R2 copies are refreshed by the
  11:15 inputs run. **HOLD stays** (world dailies paused by the owner until the new things are built).
- **Owner (wizard, 11-26, about 00:00): delete the old sc-data files now.** Dry run of one batch first: 50,000 of 50,000 named, all from the list,
  none of the kept also built. Running: `world_publish.py upload --delete-kept --max-delete 1200000` (1,129,125 files, log
  `.scratch/overture-next/delete.log`; the manifest is saved after each batch, so a rerun resumes).
- **Branches fixed and merged (owner, 11-26 05:20: "lets fix and merge branches"; two answers by wizard).** Done while
  the sc-data delete runs, under the HOLD; nothing built or installed:
  - `share-previews`: main merged into it with no conflict, the whole suite green there (317, 3 skipped), then merged into
    main (4c052008) **today, not on release day: the owner's answer.** It goes live with the 12:15 run: that run deploys `cloudflare/wrangler.jsonc` (assets only, unchanged); the
    preview Worker (`wrangler.previews.jsonc`) is deployed by nothing scheduled. Its live checks
    (`cloudflare/test/browser_parity.py`, the README's curl) now name places by their new ids (d269fe58); the node tests keep
    their fixtures' ids.
  - The points fix: source only into main (2596a3ae); `tilestore.exe` not touched (see "11-26" under the 11-24 entry).
  - Removed (worktree and branch): `syspath-leak`, `world-stable` (its one commit is in main as cf3cf87e), the heap and
    disk agent's, `a9b8a34` (merged), the points fix's, `share-previews`. No links in any; main's `.scratch` checked.
  - **Kept:** `agent-a9b152...` (P3's 28.6 GB rehearsal data, kept for the three traces), `place-ids` (the Overture
    session's), `pages-redirect` (an orphan branch, also on origin; never meant for main). Nothing pushed by this session.
