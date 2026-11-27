## Planet job: monthly while nothing counts from it (2026-10-30)

- **First update, measured.** `history-261005.osm.pbf` plus the 24 daily diffs 5137-5160 became
  `history-261029.osh.pbf` (158.8 GB) in one pass: 7,281 s, osmium peak 15.6 GB (osm-extracts estimated
  23.8 GB). Almost all of the time is the rewrite: the PBF is sorted, block-compressed and unindexed, so
  any change means reading the 159 GB file and writing a new one.
- **Every run writes about 160 GB**, whatever the number of diffs. Weekly that is about 8 TB of SSD
  writes a year, daily about 58 TB, for a file no counted place reads yet (no region has
  `"cadence": "weekly"`). The owner chose monthly: `kk-SCOpenQuests-weekly` runs on the first Monday of
  each month at 07:30 (`schedule-weekly-add.ps1`), about 2 TB a year. Names stay "weekly": the command,
  the task, the log and the cadence key.
- **Not longer than monthly.** A pass takes at most 31 diffs (`--max-diffs`, the memory cap: about
  3.4 GB + 0.85 GB a diff estimated, 15.6 GB measured at 24), so a two-month backlog costs two rewrites.
  A place requested later still gets monthly points without a gap: the history file only has to reach
  each month's 1st.
- **When a region goes weekly,** a monthly history file gives it the same data four weeks running.
  Then either schedule the job weekly again, or count current data from a small extract of the counted
  places kept current with each daily diff (about 100 MB a day, applied and clipped in minutes; the
  history file stays monthly). The second also fits moving the 115 Geofabrik cities to one daily diff
  (4.7 GB of extracts a day today). Its open risk is edges (a way joined to nodes outside the clip); the
  check is a week side by side with the Geofabrik counts of the same cities. Not built.
