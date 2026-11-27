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
