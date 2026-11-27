## Where a cell run's time goes: one Germany file measured (2026-11-10)

The owner asked what would make the recount by cells faster. First read off the Germany prototype's logs,
then measured at the owner's word: file f0 of `.scratch/world-de` (113M nodes, 9 cells, 9,363 place entries),
one engine alone at 30 GB, the machine otherwise nearly idle (another session's small runs). Runner, traces,
collector logs and the profile are in `.scratch/cells-fast/` (gitignored; `run1.py`, `jfr_phases.py`).

**The reading of the logs was wrong in one thing.** A cell's log names its three slowest quests by the sum of
their runs, and an age quest has four. AddChargingStationSocket "41 s" is four runs of about 6 s on other
threads, not the run a cell waits for. The trace shows that run is AddHousenumber or AddLevelThing.

| run of f0 | wall | process CPU |
|---|---|---|
| the engine as it was (d1cebeb7), three runs | 406, 416, 475 s | 4,122, 4,234, 4,235 s |
| 44 GB heap | 384 s | 3,926 s |
| the parallel collector, 30 GB | out of memory in the first cell | |
| two scan twins (below) | 364 s | 3,850 s |
| scan twins and the grid key (below) | 333 s | 3,670 s |

The 475 s run is the one without places: its CPU equals the others', so **places cost nothing measurable**
(9,363 entries; 790 had cost Ontario 4% of a pass). Wall time alone varies by 15% between equal runs.

**CPU by phase** (process CPU against the log's lines, the run with the collector's log; 4,234 s):

| phase | CPU | share |
|---|---|---|
| main pass over the file (nodes 232 s, ways 670 s) | 966 s | 23% |
| the area pass reading the file again | 356 s | 8% |
| map data built per cell | 452 s | 11% |
| the cells' quest runs and tallies (the task trace) | 1,155 s | 27% |
| in the cells' run phases, outside any task: the collector | 1,248 s | 29% |

- **The quest runs are a quarter of the CPU, not half.** The 51% read off the logs was wall time: alone, a
  cell's run phase keeps 3 to 8 of the 24 threads busy and waits for its longest single run.
- **The collector is the largest single cost.** In 416 s: 190 young pauses (25.5 s), 6 full collections
  (29.3 s), and a concurrent marking cycle running for 139 s. A 44 GB heap changes little (about 6% less wall and CPU,
  4 full collections), so it is not the heap's size.
- **What fills the heap** (live class histograms at four moments): 9.7 GB after the main pass; 19.3 GB in a
  middle cell, 15 of it the file's own records, kept for every cell: 114M `NodeRec` objects 5.5 GB, long
  arrays 4.9 GB (way refs, the node index, ids), tags 2.0 GB, the pbf blobs 1.7 GB. The cell's own map data
  is about 4 GB.
- **The first cell held 30.0 GB: two arrays of 5.7 GB each.** SC's `LatLonRaster(bbox, 0.0005)` (AddHousenumber,
  AddIsAmenityIndoor) is sized by the map data's box, and cell f0c0's box is 26.5 by 13.45 degrees, because
  stray nodes stretch Germany's grid to longitude -20: 1.43 billion slots. Four of the six full collections
  are in that cell, and it is why the parallel collector runs out of memory there. **For the world this is a
  blocker, not a cost:** a cell sized by nodes over an ocean or a desert is far larger than this one.
- **Inside the quest runs** (profile of the engine with the scan twins, shares of the samples there): hash
  maps 24% (gets, puts, and the tree walks below), `mapData.getNode` 10%, the fast reject still 13% (scans
  through SC's own `mapData.filter(expr)`, which walks every element), `includesElementType` 4% (a hash set
  of three enum values). In the main pass's ways: the filter
  tree 31%, the fast reject 22%, `Polygon.contains` 8.5% (a cell is a rectangle and is tested as a polygon).

**Built, same counts** (engine/README.md, "Fast twins"):
- **Twins for the two age quests that walked every element four times,** CheckExistence and
  AddChargingStationSocket (`FastScans.kt`): candidates by key first. Their CPU in the file: 197 s to 29 s.
- **A grid key that spreads** (`gridKey`, the three grids of `openquests/fast/`): `(x shl 32) or y` hashes to
  `x xor y`, so a dense grid's buckets turned into trees; 6% of the quest runs' samples were tree walks while
  the level grid was built. AddLevelThing's CPU 113 s to 85 s.
- **Checked:** f0's snapshot equals the unchanged engine's, and the Germany prototype's of 11-09, in every
  field but `runSeconds` and `engineCommit`, places included; `-Dopenquests.verifyFast=true` on Dublin and
  Lisboa found every twin equal to its port (20 map data runs), before and after the grid key; 79 engine
  tests pass, SnapshotReproductionTest included (Ontario recounted; TorontoRegressionTest skips, its extract
  pruned).
- **f0 alone: about 410 s to 333 s, CPU about 4,180 s to 3,670 s** (one run of the new engine). Not run with
  two engines at once, where the CPU is what counts: expect the 12%, not the 19%.

**Not worth doing, measured:** a larger heap; the parallel collector; clipping notes to the cells (cells tile
their file's box, so the file's clip is already theirs; the 21 s here is the prototype's single clip of 2.09M
notes for the stretched box).

**Next, in order, none built:**
1. **No giant boxes.** The planner must not hand the engine a cell far larger than its data: trim a country's
   grid to where its nodes are, and for the world cap a cell's sides in degrees. A long way's centre can lie
   in a square with no nodes, so empty cells cannot simply be dropped; and a near-empty cell is not free
   today (item 2). The engine should refuse a box whose raster would not fit, by name, instead of dying in a
   full collection.
2. **The file's records as arrays, and per-cell lists made once.** `NodeRec` as five arrays, tags only for
   the 5.3M tagged nodes: about 3 GB less live and 114M fewer objects for every marking cycle. Each cell's map
   data starts by filtering all 133M records of the file (`buildMapData`), so its cost grows with the number of
   cells in a file.
3. **`mapData.filter(expr)` asks for candidates** (a patch to SC's `MapDataXt.kt`, exact as on 11-08): every
   scan the ports and SC's helpers still do, at once. About 13% of the quest runs.
4. **Smaller things in the profile:** a rectangle cell tested by its box; `includesElementType` without a
   hash set.
5. **One read, not two** (8% of the CPU, and the second read is where the records of item 2 are made).
6. After 1 and 2, measure two engines again: the 2.3 s per million nodes is from before all of this.

The count is still about 6.5 hours of a chain whose cut is 6 and whose daily upkeep is unmeasured. Item 1 is
needed before any stage larger than a country; the rest is worth perhaps a third off the count.
