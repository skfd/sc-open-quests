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
