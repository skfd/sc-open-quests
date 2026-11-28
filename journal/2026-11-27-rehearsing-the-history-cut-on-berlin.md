## Rehearsing the history cut on Berlin (2026-11-27, evening; release 2's first step)

The parked first step of release 2 (journal/2026-11-24-parked-the-worlds-monthly-backfill-on-several-machines.md):
"rehearse the history cut on one region". The plan for the world's monthly backfill is to cut the planet history file
once into the world plan's 128 files with history (`osmium extract --with-history`, which has no `smart` strategy,
only `complete_ways`), then for each (month, file) slice the file with `osmium time-filter` and count it. Today's
order is the other way round: slice the planet at the month, then cut the snapshot with `-s smart`. The open question
(batch-engine-speed-up.md, "For the monthly history"): does cutting first lose anything a count sees? The Germany
rehearsal answered it for `complete_ways` against `smart` on a snapshot (none move), not for a history file.

**Answer: on Berlin, cut-then-slice gives exactly the counts of slice-then-cut, at three months.** Nothing the cut
drops reaches a count; nothing the cut adds reaches one either.

### What was run

- Input: `~/Code/.osm-data/berlin-history/berlin-history-261005.osh.pbf` (413 MB, the history clip the published
  monthly points were sliced from; read-only, mounted `:ro`).
- Plan: the live world's `plan.json` (`.scratch/planet/world-1101`, read only; the 11-18.0 plan is equal by
  `prepare`'s check). Berlin lies in two files, split at 13.7 E, the file border running north-south through
  Köpenick: **f4** (cells f4c5, f4c7) and **f113** (cells f113c4, f113c6); both in region **r14** (8 files). The
  cells' boundaries and the parts meeting Berlin's box (842 parts over the four cells, osm-berlin in each) were
  copied, not linked, into `.scratch/backfill-rehearsal/geo/`.
- Three inputs per date T, counted by main's installed engine (built 11-26; SC 64.1, registry v64.1) with
  world_cells' flags (areaCities 2, the GC pause, the plan's UTC JVM, each cell its own zone), the notes clip
  `planet-notes-261125-berlin.jsonl`:
  - **A**: the clip time-filtered at T, counted as the city Berlin (as `backfill_history months` does).
  - **X** (today's order): A cut into f4 and f113 with `-s smart` on the plan's padded boxes.
  - **Y** (release 2's order): the clip cut with `--with-history -s complete_ways` in two stages as
    `world_cells.cut` does for a planet (region r14, then f4 and f113 from it), each file time-filtered at T.
- T = 2017-01-01, 2020-01-01, 2026-09-01, each at 12:00Z.
- Tool: `tools/history_cut_rehearsal.py` (setup, cut, slice, count, compare, objdiff); outputs and `timings.json` in
  the worktree's `.scratch/backfill-rehearsal/` (1.5 GB).

```
python tools/history_cut_rehearsal.py setup --out .scratch/backfill-rehearsal \
  --plan C:/Users/kk/Code/sc-open-quests/.scratch/planet/world-1101/plan.json --main C:/Users/kk/Code/sc-open-quests \
  --files f4,f113 --bbox 13.05,52.30,13.80,52.70
python tools/history_cut_rehearsal.py cut --out .scratch/backfill-rehearsal --clip ~/Code/.osm-data/berlin-history/berlin-history-261005.osh.pbf
python tools/history_cut_rehearsal.py slice --out ... --clip ... --at 2026-09-01T12:00:00Z
python tools/history_cut_rehearsal.py count --out ... --at 2026-09-01T12:00:00Z --notes C:/Users/kk/Code/sc-open-quests/data/notes/planet-notes-261125-berlin.jsonl [--quests v64.0]
python tools/history_cut_rehearsal.py compare --out ... --at 2026-09-01T12:00:00Z --published C:/Users/kk/Code/sc-open-quests/data/archive/berlin/snapshots/2026-09-01.json
python tools/history_cut_rehearsal.py objdiff --out ... --at 2026-09-01T12:00:00Z
```

### Counts

| T | X against Y, every number of the four cells (quests, denominators, parts, partsAged) | osm-berlin part over the cells against A | A against the published point | A with registry v64.0 against published |
|---|---|---|---|---|
| 2017-01-01 | 29,007 numbers, **0 differ** | 951,497 / 951,501 (AddHousenumber -4) | 951,501 / 948,769 | 948,806: AddOpeningHours +37 only |
| 2020-01-01 | 31,147 numbers, **0 differ** | 1,105,128 / 1,105,126 (+1 AddHousenumber, +1 AddBarrierOnRoad) | 1,105,126 / 1,102,306 | 1,102,408: AddOpeningHours +102 only |
| 2026-09-01 | 30,912 numbers, **0 differ** | 1,115,676 / 1,115,674 (AddHousenumber +2) | 1,115,674 / 1,112,615 | 1,112,947: AddOpeningHours +332 only |

- **The slice is the published one byte for byte.** A's sha256 equals the `source.sha256` of the archived points at
  all three dates (2017-01 `4391da66...`, 2020-01 `420e5d3c...`, 2026-09 `dc4a466c...`), and A's denominators equal
  the published ones (2020-01: 640,337 tagged nodes, 752,368 tagged ways, 9,264.859 highway km).
- **A against published is the 64.1 repin, not the cut.** The published monthly points are SC 64.0 (engine
  b5af7d75, 10-21). The differences are AddAcceptsCards +2.7k, AddOpeningHours, AddAirConditioning, AddGritBinSeasonal,
  AddAirCompressor; Berlin's own dailies jump by the same amounts on 11-02, the first 64.1 day (11-01 -> 11-02:
  AddAcceptsCards 24,974 -> 27,742, AddOpeningHours 28,025 -> 28,354, AddAirConditioning 12,721 -> 12,695). With the
  v64.0 registry on today's engine only AddOpeningHours stays off (+37 / +102 / +332), so that part of the change
  is in the engine's port, not the registry. Berlin's monthly points before 11-02 were never recounted with 64.1
  (REPIN.md's step 6 recounts from the release date on): a seam of about +0.27% at the repin. The release-2
  backfill counts every month with one engine, so the world's series will not have it.
- **Cells against the whole city: 2-4 quests in about a million** (AddHousenumber, AddBarrierOnRoad), the same in X
  and Y: the osm-berlin outline against the city's boundary file, a cells matter under the owner's 0.1% bar, not the
  cut's.
- Notes: the published points used the 261022 dump, this run 261125; OsmNoteQuestType does not differ.

### What the cut drops and adds (osmium diff of X against Y, per file)

| T, file | only in X (smart of the slice) | only in Y (history cut, then slice) | in both, identical |
|---|---|---|---|
| 2026-09-01 f4 | 37 nodes, 5 ways | 26,654 nodes, 359 ways, 948 relations | 9,238,530 |
| 2026-09-01 f113 | 32 nodes, 4 ways | 21,292 nodes, 200 ways, 463 relations | 169,846 |
| 2020-01-01 f4 | 34 nodes, 5 ways | 19,933 nodes, 338 ways, 1,116 relations | 6,232,481 |
| 2020-01-01 f113 | 26 nodes, 2 ways | 15,619 nodes, 190 ways, 321 relations | 117,619 |
| 2017-01-01 f4 | 10 nodes, 1 way | 14,852 nodes, 297 ways, 1,257 relations | 5,167,964 |
| 2017-01-01 f113 | 45 nodes, 6 ways | 12,061 nodes, 167 ways, 299 relations | 102,943 |

- **Dropped: multipolygon members beyond the padded box, as the design expected.** Every way only in X is an inner or
  outer of a landuse/natural multipolygon crossing the file border, lying just past the 2 km pad (13.7317 E for f4,
  whose box ends at 13.7305; 13.667 E for f113, whose box starts at 13.6695): r5816560 natural=wood, r7601587 and
  r3109373 (Köpenicker Werder) landuse=forest, r7987483 and r7999432 wetland, r5441080 (Schwarze Berge) forest,
  r12415631 landuse=railway, r13855701 (Schmöckwitzer Werder) forest, missing an **outer** in f113. `smart`
  completes these relations; `complete_ways` cannot. None reached a count: such a relation's centre lies in the file
  where it is whole, and the members' own tags (forest, wetland, parking) are counted in the file holding them.
- **Added: what the history file knows about the box at other times.** Relations with a member in the box at any
  version, ways that touched it at some version, and every node any version of those ways used. The slice at T
  keeps the versions alive at T, wherever they are then: Y's f113 holds nodes near Leeds (x -1.40), moved or once
  wrongly joined to a Berlin way (the clip itself carries them: it is a `complete_ways` history clip). They lie
  outside the file's cells, so no cell counts them. In bytes: Y's slices are 1.2-1.5% larger than X's for f4 and 38-45%
  for the small f113 (2.78 against 1.92 MB at 2026-09).
- So **the cut is safe where Germany's snapshot rehearsal and this one look**. Still unseen: a large multipolygon
  whose centre lies in one file and whose missing outer lies more than 2 km beyond (big lakes, forests and
  wetlands across a file border: Finland, Canada, Siberia), and the polar and antimeridian files.

### Timings and sizes (through Docker's bind mount, the clip on C:)

| step | seconds | in | out |
|---|---:|---:|---:|
| history cut, stage 1 (clip -> r14, 1 output) | 27.3 | 413.4 MB | 413.4 MB |
| history cut, stage 2 (r14 -> f4, f113) | 29.6 | 413.4 MB | 424.2 MB (f4 412.7, f113 11.5; +2.6% from the pad and ways in both) |
| time-filter of the whole clip (A), per month | 6.6-8.4 | 413 MB | 53 MB (2017-01), 67 MB (2020-01), 118 MB (2026-09) |
| time-filter of f4 + f113 (Y), per month | 7.9-8.8 | 424 MB | A's size + 2.2-2.5% |
| smart cut of A into f4 + f113 (X), per month | 3.9-8.7 | 53-118 MB | +0.2-0.4% |
| count A (Berlin whole) | 10.5-15.8 | | |
| count X f4 + f113 / Y f4 + f113 | 14.0-19.7 / 13.2-21.6 | | |

- History-cut rate here: about 14-15 MB/s of input with everything written. A pass that writes little reads faster:
  the Ontario clip from the planet history (163 GB, one small output) took 50 min, about 54 MB/s. Splitting
  Berlin's passes by that read rate leaves about 20 MB/s for writing.
- **Planet extrapolation** (history-261102 was 170.7 GB; the file is gone from the store since 11-16, only its meta
  remains). Stage 1: 16 regions at 8 outputs a pass = 2 reads of 171 GB and about 172 GB written; stage 2: 16 region
  passes, about 172 GB read and about 176 GB written (Berlin's +2.6% is a border through a dense city; the world's
  borders mostly run through emptier land).
  - read 54 MB/s + write 20 MB/s: stage 1 1.8 h + 2.4 h, stage 2 0.9 h + 2.4 h: **about 7.5 h**.
  - Berlin's flat 14-15 MB/s on every byte in: stage 1 2 x 3.1 h, stage 2 3.4 h: **about 9.7 h**.
  - So the design's 8-10 h holds, with the cut through the bind mount; off the mount (native osmium or the WSL disk)
    the design measured passes 1.85 times faster. **Out: about 172-176 GB, not 160 GB.**
  - Not learnable from 413 MB: osmium's memory for 8 history outputs over 14.3 billion node ids (smart on a snapshot
    holds about 4.2 GB an output); the first stage-1 pass should be watched, or run at fewer outputs.
- **Disk:** the planet file (171 GB, to download again or bring back with osm-extracts) plus stage 1's regions (172 GB)
  peaks at about 345 GB with the planet kept, about 190 GB if it goes after stage 1. C: had 166 GB free tonight,
  with the 12-01 switch still to peak +80 GB: the cut does not fit beside the world today.
- **A month after the cut:** the time-filters are read-bound (Berlin ~50-60 MB/s of history in), so a month's 128
  slices read all ~175 GB: about 55 min serially through the mount, less with several at once, against today's
  74 min slice + 262 min smart cut. The counts cost the same either way (Y's slices are about 2% larger than X's). With the
  design's ~2.2-2.5 h count a month is about 2.5-3.5 h: 118 months in 12-17 days of this machine.

### Next for release 2

1. A planet history file and the disk for it: about 171 GB for the file plus about 176 GB for the cut (or delete the
   planet after stage 1), after the 12-01 switch has freed the old world (about 65 GB).
2. The cut itself (`world_cells.cut` with `--with-history`, `osh.pbf` outputs and `complete_ways` instead of `smart`:
   `tools/history_cut_rehearsal.py cut` is that change in small), detached, watching stage 1's first pass for memory.
3. A planet-scale canary before counting 118 months: at one month, a few files cut both ways (X and Y as here),
   chosen for the risk left: dense lake and forest multipolygons across file borders (Finland or Sweden, Quebec), a
   polar and an antimeridian file. Then the job queue and the slicer's choice (osmium time-filter here, or
   tilestore's own history reader).
