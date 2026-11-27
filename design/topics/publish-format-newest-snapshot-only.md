## Publish format: newest snapshot only (2026-10-24)

- **What the site fetches** (read off `app.js`): `cities.json`, `quests.json`, `sc-releases.json`,
  `icons/index.json`, `history/<city>.json`, and, in the compare view with a quest picked, every
  region's newest snapshot (each city's `asOfDate`). No view and no link reads an older dated snapshot:
  the query string has no date, and the charts read the history files.
- **The archive leaves `docs/`.** The engine writes `data/archive/<region>/snapshots/<asOfDate>.json`
  and its `quests.json` (gitignored; `--out data/archive/<region>`, no engine change), and
  `run.py history` reads the archive. `docs/data/<region>/snapshots/` keeps the region's newest
  snapshot only, a byte copy: 12 files, 2.5 MB. It stays in git, so git history holds each day's
  published newest; months merged later by `backfill_history.py` are in the archive only.
- **Compare reads one small file per quest**, `docs/data/compare/<quest>.json`: each city's open count
  in its newest snapshot, 184 files of about 1.75 KB. Picking a quest fetches 1.75 KB instead of
  12 snapshots (2.5 MB). Checked equal to the old lookup for all 22,195 city × quest pairs.
- **Sizes.** `docs/` went from 1,795 files, 332.7 MB, to 506 files, 19.3 MB (history 15.0 MB). It now
  grows by the history files only, about 0.1 MB a day at 115 cities instead of 2.5 MB. The archive is
  317 MB on disk and grows as `docs/` used to.
- **History did not move.** Rebuilt from the archive, all 115 history files, `cities.json` and
  `quests.json` are byte-identical to the ones built from `docs/data`.
- **Migration is a step, not a commit.** `run.py migrate-archive` moves any snapshot still in
  `docs/data/<region>/snapshots/` (and the engine's old `docs/data/<region>/quests.json`) into the
  archive; `count` and `history` run it first, so the scheduled `update` migrates by itself and its
  `git add docs/data` stages the 1,473 deletions. Idempotent; a file that differs from the archive's
  copy is left in place and logged.
- **A lost archive cannot shrink the site.** `history` refuses to run when the archive lacks a date
  that the published `cities.json` has (a fresh clone, a deleted `data/`), instead of rebuilding a
  shorter history. The snapshots up to 2026-10-24 can be restored from git history; of later ones git
  has only each day's published newest, so the archive is the one copy of the rest (not backed up).
