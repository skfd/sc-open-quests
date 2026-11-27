## Batch engine speed-up (2026-11-14 night to 11-15; owner: "spend some time doing optimizations for current implementation of batch engine. think outside of the box too")

A rewrite in a systems language is the owner's other track; this is the JVM engine as it is. Built on branch
`batch-speed` (worktree `../sc-open-quests-batch`). Runner and comparer: `.scratch/batch-speed/run1.py`, `same.py`
(gitignored); test file Germany f0 of `.scratch/world-de2` (113M nodes, 18 cells, 30 GB heap, 24 threads).

**Where the world count's time went** (its own logs, `.scratch/planet/world/files/*/log.txt`): 128 files, 15,217 s of
passes; **12,465 s (82%) is the cells' area runs, one cell after another**, 3,520 s of that building map data. And
on f0, by process CPU: of 2,467 s only 651 s was quest runs. The collector was the largest consumer: the file's
records kept the heap about 70% full of small objects (114M node records, 19M way records, 24M tag maps with their
arrays and strings), walked by every marking cycle, and each cell allocated three 0.7-1 GB arrays of references
(SC's `LatLonRaster` over a box of 8 by 7 degrees) that ended in full collections.

**Built, each step with the same snapshot** (`same.py`: every field but runSeconds and engineCommit):

| step | f0 wall | f0 CPU |
|---|---:|---:|
| the engine as it was (d148d0e1) | 245 s | 2,467 s |
| the area pass's nodes as columns; a city's elements picked from int arrays | 202 s | 2,074 s |
| key indexes and the node index of a map data built on all threads; a sparse twin of `LatLonRaster` | 171 s | 2,059 s |
| ways as columns, tags as numbers of one dictionary (a `TagMap` is made when a city's map data wants the element) | 161 s | 1,959 s |
| one node table for both passes (`NodeStore`): the area pass no longer decodes the nodes again; the file's blocks let go before the cells | 162 s | 2,173 s |
| `-XX:MaxGCPauseMillis=5000` (a larger young generation, less copying; `world_cells.py` sets it, the launcher the daily runs share does not: it is measured on a cell file at 30 GB only) | 145 s | 1,817 s |
| **two cells at once** (`-Dopenquests.areaCities=2`, `world_cells.py`'s setting) | **123 s** | 1,912 s |
| three cells at once, 30 GB / 40 GB | 120 s / 118 s | 2,032 s / 2,016 s |
| two cells, and AddHousenumber's twin measuring only the areas that hold an address node (its step 5 measured and sorted every area of a city; the sort is stable, so the few kept come in the same order: 79 s to 30 s of its CPU) | **117 s** | 1,893 s |

Single runs; wall time varies by about 5% between equal runs.

- **2.1 times on f0** (245 s to 117 s; f1 110 s). With `--dump-state`: 272 s to 172 s, `state.bin` the same 31,695,753 rows.
  A daily-style run (Ontario's 53 cities on the 11-13 clip, with notes, parts and the tile grid): 78 s to 54 s, the
  snapshot equal and the grid files byte for byte.
- **Cells at once needed the memory work first.** At the start three at once gained 6% and cost 6-12 full collections;
  the cells' phase is now CPU-bound at two (19 of 24 threads busy with three, and no faster).
- **The sparse raster keeps SC's squares** (same corner, same square size, the points of a box row by row, west to east,
  each square's in insertion order) and holds only the squares that have a point. `-Dopenquests.verifyFast=true` on
  Bremen: every twin equal to its port on 24 map data runs. The 500M-slot refusal stays (the ports still build SC's).
- **Checks:** 87 engine tests pass (SnapshotReproductionTest and TorontoRegressionTest skip in the worktree: no
  `data/cities`, extract pruned); f0's snapshot at every step; Ontario's snapshot and grid; f0's state dump.
- **Measured and dropped:** JDK 25 with compact object headers (220 s against 210 s); a later marking start
  (`InitiatingHeapOccupancyPercent=80`: 11% less CPU, the same wall); an earlier one with 12 marking threads; the
  parallel collector (46 full collections with three cells); `MaxTenuringThreshold=0`; a fixed 35-45% young generation;
  ZGC (not in this JDK build); a way's geometry sharing its nodes' position objects (kept, no measurable change).
- **What the CPU is now** (JFR samples of a three-cell run, Java threads only; the collector's pauses are another
  330 s of CPU): quest runs 35%, the main pass over the ways 26% (two thirds of it `offer`: 140 quests asked of every
  way), the main pass over the nodes 12%, the area pass's ways 6%, map data 8%.
- **Built, exact, and taken out again: quests by key in the main pass** (an element offered only to the quests that
  name one of its keys, a bit per quest, instead of every quest's reject test). The same snapshots on f0 and f1; the
  ways' CPU 401 s to 377 s, the nodes' 160 s to 180 s: nothing net. The reject test is not where the main pass's time
  is; the filter trees of the quests that pass it are.
- **Next for the engine, none built:** (1) one read of the ways too (the area pass still decodes them a second time,
  6%); (2) AddHousenumber and AddLevelThing are a city's longest runs and 50% of the quest runs' samples; (3) the
  filter trees of the main pass (a highway is asked by some forty quests, each walking its own tree).
- **One engine or two** (f0 and f1 of the rehearsal, the pause target set): one engine with two cells at once, the
  files one after the other, 243 s at 30 GB; two engines side by side with one cell each, 223 s at 22 GB each; two
  engines with two cells each, 243 s. The CPU is the limit, so **`world_cells.py count` runs one engine by default**
  (it ran one in practice: two never fit). The 1.4 times of a second engine (2026-11-07) is gone with the idle threads.
- **More checks, after the table:** Dublin and Lisboa with `verifyFast` and two cities at once: every twin equal to
  its port on 20 map data runs (Hamburg's was stopped after 17 min in the port's own AddMaxHeight, not hung).
  `SparseLatLonRasterTest`: random points and boxes against SC's raster (a city, a ten-degree cell, across the
  antimeridian, both poles, empty, coarse). On main after the merge: 93 engine tests pass, SnapshotReproductionTest
  among them (a stored extract recounted to its committed snapshot). f1 to f3 equal between the settings above.
  **Not checked: a real world file with a polar, antimeridian or open-sea cell** (the world's cut is deleted): the
  12-07 count should run its canary file first, as before.

**The cut is slow because of Docker's bind mount** (`.scratch/batch-speed/cutio.sh`, the 11-08 europe clip, 1.75 GB,
osmium 1.18 in the `name-ru-repair-osmium` image):

| | through the Windows bind mount | on the container's own disk |
|---|---:|---:|
| `osmium fileinfo -e` (one read of everything) | 19-20 s | 4.4 s |
| one region pass (`extract -s smart`, 2 outputs) | 74 s | 40 s |
| the same, `pbf_compression=none` | | 38 s |
| the same, `-s complete_ways` | | 36 s |

- osmium reads 4.5 times slower through the mount (a plain `cat` of the file: 143 MB/s, so it is the many small reads,
  not the disk), and a whole pass is 1.85 times slower. The world's cut was 262 min and its slice 74 min, both through
  the mount (with cold caches the same: 80 s against 43 s, `cutcold.sh`, a clip not read that day and the container's
  page cache dropped): **on a native disk the cut should be about 140 min**, and the slice (a 130 GB history file read through
  the mount) should gain too. Compression and the strategy are not the cost.
- **Two ways to get there, the owner's call (nothing installed):** a native Windows osmium (conda-forge has
  `osmium-tool` for Windows, to be checked; no VM, no limit of 8 outputs a pass from Docker's 43 GB), or the planet
  and the cut's outputs on the WSL disk (about 270 GB of a VHDX that does not shrink: does not fit today).
- **Beyond that, osmium itself is the limit** (40 s for 1.75 GB with most of 24 threads idle: one thread routes
  everything). A cutter in the engine's own build, on its parallel block reader (this clip's 128M nodes decoded in
  6.7 s), could cut the planet in one stage: a table of each node's files by id (about 28 GB in memory), the ways
  routed by their nodes, a second read to write. An estimate of 30-40 min against 262, not built; its risk is
  matching `smart`'s relations exactly (the bar: the same counts on the rehearsal's 16 files).
- **For the monthly history** (118 world months, each a slice and a cut today): cut the *history* file once into
  the 128 files (`extract --with-history`, as the regions' monthly history does) and `time-filter` each small file per
  month. That removes the slice and the cut from every month (5.6 h of 10.5 h). `--with-history` has no `smart`:
  relations lose member ways outside a file's box, which reached no count for a region ("Monthly history", above)
  but file borders run everywhere.
  **Measured on the Germany rehearsal (`cwcut.sh`, `diffsnap.py`): none move.** Its four files cut again from
  `germany-2026-11-07.osm.pbf` with `-s complete_ways` (0.05% smaller) and counted: every city field of all 46 cells
  equal to the smart cut's, quests and denominators (76,063,895 open); only the file's hash differs. So relations
  completed across a file's border decide no count here, and the history cut is worth a rehearsal of its own (a
  history clip cut into files and time-filtered, against a slice cut the usual way: what `--with-history` adds beyond
  `complete_ways`, all versions' nodes, is not covered by this). An estimate, not measured: the once-only cut some
  8-10 h through the mount in two stages; then a month is 128 small time-filters (several at once) and the count,
  about 2.5 h against 10.5 h: 118 months in about 12 days of machine time against 52.

**The world chain with what is built** (estimates from f0's ratio, not a world run): slice 74 min, cut 262 min,
count about 4.4 h to about 2.2 h: 10.5 h to about 8.3 h. With the cut off the bind mount: about 6 h.
