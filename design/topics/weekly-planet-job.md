## Weekly planet job (2026-10-24)

The sc-open-quests side of the owner's choice above: places counted on request get monthly history since
2017 and then weekly counts, all from the planet history file that `osm-extracts fetch planet-history`
keeps current with replication diffs. Canada and Germany stay daily from Geofabrik. No place is weekly yet:
the place list is the breakdown session's.

- **A region says how it is counted.** `"cadence": "weekly"` in `config/regions.json` (default `"daily"`).
  `download`, `count`, `backfill` and `update` skip a weekly region (it has no extract); `history`, the
  notes clip and `cities.json` see every region. An unknown cadence fails the run.
- **`run.py weekly`**, one code path with `tools/backfill_history.py` (`weekly()`): (1) `osm-extracts fetch
  planet-history`; any failure, disk the likely one, is logged and the file is used as it is (an older
  history is still a valid source); (2) clip every weekly region from the newest history file in one
  pass, deleting each region's older clip; (3) count the 1st of each month since 2017-01 that the region
  lacks, at 12:00Z as before; (4) a slice at the history file's own replication timestamp, skipped if a snapshot already
  counts that slice (a history file the fetch could not move on); the engine dates it in the region's zone
  and the snapshot is dropped if the region has that date already (no tzdata needed); (5) merge into
  `data/archive/`, rebuild history, commit `data weekly <UTC date of the history file>` and push
  (`--no-push` commits only, on `update` too). With no weekly region it stops after (1).
- **History file naming.** `backfill_history.py` takes `history-<YYMMDD>.osm.pbf` (the planet site's dump,
  today's 261005) or `.osh.pbf` (osm-extracts' diffed file), the newest by date; the meta's
  `derived_from` goes into clip and slice metas, and a slice of a diffed file has no `source_url`.
  `months --to` defaults to the last month whose 1st, 12:00Z, the file reaches: 2026-10 for 261005, as the
  hard-coded default was. Clips are named after the history file, so a new file means new clips.
- **Never across the daily run.** The job takes the pipeline lock per step, not for its ten hours: each
  count (as `backfill_history` always did) and merge + history + publish together. No step starts that
  would reach the 13:15 update's window (12:55-13:50): the fetch waits if the window is under two hours
  away, the planet clip under 90 minutes, a count or the publish inside it. The fetch itself touches only
  the store, which osm-extracts locks. The planet clip, like the engine, waits while memory is busy
  (`run.engine_heap_gb`); a region's slices are small and do not.
- **Schedule:** `schedule-weekly-add.ps1` registers `kk-SCOpenQuests-weekly`, Mondays 07:30, ten hours,
  start when available, no second instance; not registered yet. A new weekly region's first run counts
  118 months (Bremen under a minute each with its slice, Ontario 5 min: past the ten hours, so run `backfill_history.py
  months` by hand first, or let the next weeks finish it; staged months are kept across runs).
- **One snapshot per date.** A month's 12:00Z slice beats a weekly slice of the same local date (a file
  ending 2026-11-02T00:00Z is still the 1st in Toronto). A file ending on a 1st before 12:00Z gives that
  date's snapshot from the weekly slice, and the month's 12:00Z slice is then skipped.
- **Checked end to end without the planet.** A stand-in history file: Bremen's 261005 clip plus the
  planet's daily diffs 5137 and 5138 (`osmium apply-changes -H`, 25 s, 73 MB to 166 MB: the diffs carry the
  whole world's edits), named `history-261007.osh.pbf` with a meta at 5138's 2026-10-07T00:00:00Z, in a
  scratch store; a clone of the repo with one region `bremen-weekly` (Bremen's poly and two cities), its
  archive seeded with Bremen's published monthlies up to 2026-09, notes dump 261022 (the one the published
  months used), and a stand-in osm-extracts that fails for disk. `run.py weekly --no-push`: the failed
  fetch is logged and the run goes on; the clip is back to 73 MB; 2026-10-01 is counted and its slice is
  **byte-identical** to the published one's (same sha256), with all 366 city x quest counts and every
  denominator equal (`notes.open` 645 against 634: the one-pass notes clip's wider area, as above); the
  'now' slice is dated 2026-10-07 (02:00 in Berlin), totals Bremen 258,140 and Bremerhaven 65,856 between
  the published 2026-10-01 (258,131 / 65,896) and the 2026-10-12 daily (258,251 / 65,785). A second run
  counts nothing (119 dates already there), rebuilds history and commits `data weekly 2026-10-07`
  (188 files) without pushing.
