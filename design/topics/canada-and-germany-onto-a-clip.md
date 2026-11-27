## Canada and Germany onto a clip (2026-11-06)

The owner asked whether every region can read the planet history route, as Europe does; yes, after a week
side by side. Why: one pipeline, one timestamp (today Toronto and Berlin have different dates; on 11-06
Bremen's newest Geofabrik extract was 11-04), 4.7 GB less to download a day, and the world count needs the
same route. Against: Docker and one clip stop every region at once, no independent source any more, a new
city waits for a re-cut, the re-cut's memory grows, and series step slightly when the timestamp moves to 00:00Z.

- **The clip:** `config/canada-germany.geojson`, the 115 cities' boxes padded 2 km: 54 parts, 39 square
  degrees (18 of them Wood Buffalo). Registered in osm-extracts, first `recut canada-germany` from
  `history-261102` started 2026-11-06 20:21, log `logs/recut-canada-germany.log`. Europe's clip is untouched.
- **The week:** task `kk-SCOpenQuests-sidebyside`, 15:10 daily, 2026-11-07 to 11-14, runs
  `.scratch/side-by-side/compare.py` (log `logs/side-by-side.log`): fetches the clip, counts each region from
  it into that folder, appends per-city differences from the archived Geofabrik snapshot to `report.csv`.
  Nothing the site reads changes. Self-test on Bremen's own extract: difference 0.
- **Reading it:** the two files are hours apart and Geofabrik can be days behind, so the numbers will not be
  equal; a difference has to look like that gap's edits. Look at the days both timestamps are close.
- **After the week, if it holds:** `"extract": "canada-germany"` on the 12 regions; a check that Docker is up
  before the daily fetch, retrying; raise the re-cut's budget if the first run shows it tight. The Geofabrik
  code stays until a monthly cycle has passed.

**Daily, on local machines (asked 2026-11-06, late evening; hosting elsewhere).** Measured, nothing built.
- **Where the engine's time goes** (JFR, Czechia's 11.8M-node column, 12,680 samples): area quests 64%, the
  pass over the file 27% (reading the pbf 16%), map data 9%. By operation: evaluating element filters 38%,
  walking tag maps and collections 17%, hash lookups 8%. Most of it is a quest asking "is this you?" of an
  element that holds none of its keys. CheckExistence alone is 12%, AddLevelThing 7%, AddTactilePavingKerb 7%.
- **Memoizing by tag set does not work:** 1.1M distinct tag sets among 1.8M tagged elements (1.6 each; names and
  addresses make them unique), the top 1,000 covering 32%.
- **A fast reject should:** each filter expression works out the keys it cannot match without and returns
  false at once when the element has none of them, in the one place all filters pass through. Exact by
  construction. Expected 1.7 to 2.5 times on the whole pass, not yet tried.
- **Recounting only changed tiles pays in quiet places, not busy cities.** One day, nodes in z14 tiles touched:
  Ontario (16,600 objects) 1.8%, 8.5% with a one-tile ring (22% at z12); Hamburg (860 objects) 21%, 64% with a
  ring (98% at z12). Most of the planet should look more like Ontario, so this is a real later step: maybe a
  fifth of the count on a normal day, unmeasured for the world. It needs per-tile state, and age-based quests
  (52 of 193 mention a date) change with no edit at all, so a regular full pass stays.
- **Keep the ~80 region files current from the daily diff** instead of a new planet and cut each day: the
  clip method, exact over 72 region-days. Guessed at 1 to 3 hours against 8.
- **`run.py history` will not scale:** 72 s for 147 cities over 2,093 snapshots, a rebuild of everything each
  run; linear to a million places that is days. Publishing must append.
- **The owner's answers (2026-11-06, late evening):** willing to buy a machine for the count, sized after the
  speed-up is measured; R2 on a subdomain the owner has; the fast reject waits for the cell test.
- **Budget for a day:** diffs 2 h, count 7-9 h, publish 1 h: about 11 hours, if the fast reject delivers.
  Without it 19 hours, on paper only. A second machine divides the count, since files share nothing.
