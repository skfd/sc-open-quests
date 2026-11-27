## The world state store (2026-11-14, early morning)

The world seed is done (128 files, 2,011,107,291 rows, 48.3 GB, checked against its count file by file) and does
not fit in memory, where `stream.py`'s `State` loads and sorts all of europe-west's 6.8M rows. Measured on the seed
(`.scratch/planet/seedkeys.py`, `seedkeys.log`):
- **The files partition the world by element:** 1,061,205,063 distinct elements (116.9M nodes, 942.7M ways, 1.7M
  relations), and only 95 keys in more than one file (112 extra copies). An element belongs to the file whose
  `rect` (plan.json) holds it, as the count decided; 2,244 cells, each with its time zone, are the files'
  "cities".
- **Lookups need the files sorted, not an index:** a file's rows come in engine-thread order. Looking five planet
  days of touched keys (25.9M) up in one file of 18.6M rows takes 20.7 s with `np.isin` (45 min for the world), but
  1.4 s with `searchsorted` once the file is sorted; sorting a file takes 11-14 s (about 28 min for the world,
  once). One day's touched keys (about 4.6M) against all 128 sorted files is then well under a minute.
- **So the store is the seed's own 128 files, sorted by (key, quest, kind)** (what `State.save` sorts by), each
  rewritten only when a day changes it (a 450 MB file writes in about a second), with a manifest of each file's
  rect, rows and key range. A removal searches every file (a deleted or moved element has no position to route
  by, and searching is cheap); an addition goes to the file whose rect holds the element; the 95 keys in two files
  stay in both, as the count has them.
- **What a world day still needs beyond this:** the node location store (`planet.loc`, 107 GiB, built from
  `history-261102.osh.pbf`, which the 12-07 planet job retires, and on a disk that job needs about 170 GB of) for
  tier 1, and a store answering "map data of these boxes at D and D-1" for tier 2 (estimated about 300 GB). Both
  are the owner's call on disk and timing. The daily touched-element engine run must use the seed's cells and
  zones (one engine run, the 2,244 cells as its cities), not `stream.py`'s single `--zone`.

**Sorted (11-14, 04:17-04:31):** `world_state.py sort` on 4 processes, 832 s; 2,011,107,291 rows kept, 1,061,205,175
keys over the files, the same 95 in two files. `world_state.py find` with the five planet days' touched keys
(25,862,383, of which 1,112,729 have rows in the state: most touched nodes carry no quest) against all 128 key lists
takes 153 s, warm or cold: CPU, about 1.2 s a file, so about 30 s for one day's 4.6M keys. Fast enough to leave
unindexed; a file's key range (in the manifest) could skip most files for most keys if it ever matters.

**The one tier-2 row left, traced (11-14, 05:00; `.scratch/stream/housetrace.py`, output beside it).**
`w1577774915` (`building=house`, no address) is one of about 45 houses (ways 1577774915-1577774989) mapped on 11-12
over Fortune Green Road, London, where buildings with addresses already stand (`w12391097xx`, 110-118, with
`entrance` address nodes on their outlines: 110A and 110B lie a few metres west of the new house). No address node
lies inside the new house itself. A hypothesis, not shown: AddHousenumber decides such a building by order: step 1 lets each address-less
building take ("consume") a shared set of address nodes in map-data order, and step 5 lets areas take address nodes
on their outlines smallest first, then drops every building whose centre lies in such an area (and
`associateBy { center }` keeps one building per centre). Map-data order follows a `HashMap`'s iteration, which
changes with how much map data is loaded (the Bremen check of `ArrayMapData`, above), so the recount's rectangle and
the whole city can hand these nodes out differently. The app's own answer depends on what it downloaded in the same
way. If so, not fixable by the stream short of recounting with the whole city's map data. The 36 AddHousenumber the 11-12 recount lacked (w191632543,
w525502455, w526944931...) are likely the same family; not traced.

**Tested (11-14, 05:15; `.scratch/stream/ring.py`, `ring.txt`): mostly map data extent, not order.** 11-12's 189
rectangles recounted on the 11-12 clip. At the stream's 300 m ring: 22,001 open AddHousenumber inside them against
the whole count's 22,036, lacking 36 (35 of them in one block near 51.47, -0.02, one at 51.48, -0.29) and adding
`w1577774915`. At a 1,500 m ring: 22,039, lacking none and no longer adding `w1577774915`, but adding 3 others
(`w378203971`, `w378204031` near 51.584, -0.040; `w1176630809` near 51.474, -0.027). So 37 of the 37 came from how
far the map data reaches (some address-carrying area or building beyond 300 m decides them), and a wider ring
brings a few disagreements of its own (not traced; order is still a candidate for those). The 1,500 m ring reads
24.6M nodes against 3.6M and took 73 s against 46 s here. For the world store this is the ring-size trade-off:
the store must serve the ring the recount needs, and 300 m is not exact for AddHousenumber.

**The world seed agrees with europe-west's 11-08 count (11-14, 05:25; `.scratch/planet/seedvseurope.py`, log
beside it).** The read-back passes (`seedcheck.py` on the sorted files, 0 problems); every row lies in its file's
rect but 9 on an edge (rounding); the 95 keys in two files are all relations (`seedroute.py`). On the elements both
hold (2,152,775 keys in f34, f44, f90 and f106: Lisboa, Dublin, London), **all 5,405,119 tier-1 rows are equal in
every field** (key, quest, kind, flags, date, position), none on one side only. The world's cells and time zones
give the same tier-1 rows as the Europe cities, so europe-west's day dumps (11-09..11-13) can check a world-path
stream on those elements.

**The world's tier 1 on five days (11-14, 05:12-05:48; `tools/stream/world-europe.sh`, log `logs/world-europe.log`).**
`world_state.py subset` copied the four world files holding Lisboa, Dublin and London (f34, f44, f90, f106) to
`.scratch/planet/world-test/`; `apply` ran diffs 5171..5175 through the world's cells (one engine run over the
small PBF with the 64 cells of those files as its cities, each with its time zone, at UTC like the count) with
europe-west's 11-08 node locations, and `check` held each day against europe-west's whole count on the 2.46M
elements it has inside those rects plus those its 11-08 dump had. At 11-08 the copies equal the count (3,239,324
open, 2,064,743 waiting). On 11-13, every field compared as `stream.rows_check` does: matches 3,343,307 against
3,343,305, waiting 2,065,352 against 2,065,355; 774 matches and 706 waiting rows equal but for the position (ways
whose nodes moved while they kept their version, 28 of them touched earlier; and 4 relation rows), and 3 + 1
matches and 3 + 6 waiting rows on four untouched relations. **The same numbers, row for row, as europe-west's own
tier-1-only stream** (`europe-west/check-2026-11-13.txt`: 3,343,307 / 3,343,305, the same three relations, 774
positions with 28 touched): the world path adds no difference, and what is left is tier 1's known limits, which
tier 2's recount removes (t2a). A day took 5.5-7 min here: reading the diff 2 min, the small PBF 1 min with
europe-west's node index (200-250k ways not placed: they lie outside europe-west), the engine 2.7 s, and **writing
the four files 140-165 s**, which at 128 files would be about half an hour: re-sorting each whole file is the cost.
**Then merged, not sorted (11-14, 06:00):** `replace_in_file` now inserts the day's rows into the sorted file
(`merge`: one int64 per row for (key, quest, kind), `searchsorted`, `np.insert`) instead of sorting it again: on f90
(24.7M rows) with a day's touched keys, 1.0 s against 31 s, the same rows in the same order. A file's update is then
about 3 s (finding the rows 1.2 s, merging 1 s, writing 0.6 s), so a world day's files about 6-7 min if every file
changes.
**Rerun with the merge (11-14, 06:05-06:30, `logs/world-europe-2.log`):** the four files at 11-13 hold the same rows
as the sorting run's, the 11-13 check unchanged; the files' step 47-51 s a day against 140-165 s. Then `in_keys`
marks with `bincount` instead of `np.add.at`, and the key list is taken from the sorted keys without `np.unique`'s
sort: one update of f90 with a day's keys is 4.0 s in all (read, find, merge, write, key list), so the files of a
world day at most about 8.5 min.

**The world's first day (11-14, 12:56-13:08; `tools/stream/world-days.sh`, log `logs/world-days.log`).** `planet.loc`
rebuilt (115 GB, 34 min with the six diffs to 11-08), the stream state hard-linked to the seed
(`.scratch/planet/world-stream/`), and diff 5171 applied to all 128 files: reading the diff 114 s, the small PBF
74 s (432,104 tagged ways, **none unplaced**: the planet store places every way), the engine 11 s over the 2,244
cells, the files 459 s (569,034 tier-1 rows dropped, 840,698 added, none outside every file's rect); 11.5 min in
all. On the elements europe-west's whole count of 11-09 has: matches 3,340,642 = 3,340,642 and waiting 2,064,632 =
2,064,632, all equal but for the position of 17 + 15 rows of untouched ways (nodes moved, the way kept its version:
tier 1's known limit).
