## Batch engine speed-up, sixth round: a cell's map data, about 6% off a run (2026-11-15, 17:20 to 19:35; owner: "fifth round of speedup", which was already merged, so this is the next)

**Built and merged: four changes to how a cell's map data is put together, every snapshot equal. On f0, in
three interleaved rounds, the cells' phase is 12% shorter (50.2 s to 44.4 s) and a whole run 6% (87.4 s to
81.9 s, 4.5% less CPU). Five more changes, all in the main pass, were built, shown exact, measured, and taken
out again: nothing net.** The build that still had those five showed 17% and 9.5% (80.0 s to 72.4 s) in three
pairs on a calmer machine, and no difference from the four alone when the two ran side by side.

**Read first, from what was on disk** (the fifth round's profile `r5.jfr`, the runs `g-*`, a new reader
`jfrtree.py`: of the samples under a function, the share of each callee):

- **About 9 s of f0's wall time here is not the engine's in a world run.** The rehearsal's f0 has no notes clip
  of its own, so the run reads the whole clip (954 MB, 2,091,648 notes) in 10.6 s on one thread before the
  passes. A world file has its own (`world_cells.py notes`): at most 166,178 notes, read in 1 to 2 s
  (`.scratch/planet/world/files/*/log.txt`). Not changed.
- **The collector is still the largest single consumer:** in `g-pairs-4`, 87 pauses, 13.4 s of 98 s, and 227 s
  of 1,437 s of CPU. What a pause copies is what survives (a cell's map data, promoted at age 1 or 2), not what
  is allocated, which is why the fifth round's 11% fewer bytes moved no pause. The flags were tried in the
  first round. Not addressed.
- **One lock:** `ScFeatures.getFeature` serializes every call into osmfeatures. The profile holds 609 waits
  for it over the recording's threshold, 24 s of threads waiting (CheckExistence's twin 10.7 s, AddPlaceName
  in the main pass 9.0 s), for 0.6% of the samples spent inside. Not built: its `getByTags` reads plain
  `HashMap`s of lazily made indexes, which is safe to read unlocked only after every index a call can want
  exists, and that needs osmfeatures' source read, not its bytecode skimmed. Worth about a second.
- A quest task's clock time was twice its thread's CPU time in `g-pairs-4`. That was the busy machine, not a
  finding.

**What stays** (all in `AreaPass.assemble` and `NodeStore`; none is an SC patch; shares are of the profile's
Java samples):

| | where the profile or the trace had it | |
|---|---|---|
| a bit per node, "tagged", asked before the search among the tagged | `NodeStore.tagsOf` for each of a cell's 15M nodes, 1.3% | |
| a cell's nodes in the order they first come, from a bit set over the file's nodes (`firstSeen`) | two parallel sorts per cell (every node of every way, then the distinct ones: 15M in a large cell), most of 3.0% | a tile's few nodes still sort: clearing a bit per node of the file would cost more |
| a way's node found at the place after the one before (`NodeStore.indexOfAfter`), else the search, when a cell looks up its ways' nodes | the loop over a way's nodes, about 1% | a way's nodes were mostly made together, so the next id is the next of the file |
| a cell's ways and geometries put into arrays by the threads that make them; node ids taken as the nodes are made | not CPU: one thread reading 2.5M pairs twice and 15M ids at random | below |

**One-threaded steps of a cell's map data** (`-Dopenquests.assembleTrace=true`, new: a log line per cell with
each step's seconds). On the large cells, before the last row above: the two lists off the pairs 0.25 to 0.68 s,
the id table 0.18 to 0.30 s, of 2 to 5 s for the whole map data. After: 0.00 s and mostly 0.05 to 0.18 s. Both
runs under load, so the steps' sizes are rough; that they are gone is not. Still on one thread: the bit set walk
(0.1 to 0.4 s) and parts of the hash order (0.2 to 0.6 s with its sort).

**Built, exact, and taken out again: five changes to the main pass.** The same next-place search for a way's
nodes in `processWays` (the profile's 4.1%); a way's place among the relations' member ways by walking both
lists instead of a search per way (1.0%); a raw coordinate taken as it is in a block of 1e-7 degrees and no
offset (a line of 1.6%); "does a note hide this position" asked once per element, not per matching quest
(0.9%); tags kept by their places in the block's string table instead of a look-up per string (about 2.5%).
Together a tenth of the samples, and in the pairs below the main pass's CPU is the same with and without them.
Why is not known. One reading, not tested: those lines are where a thread waits for memory, and the wait moves
to the next read instead of going away. They are in the history (e95f9b6c, taken out in the commit after) with
their tests.

**Timing, f0, interleaved** (`quiet6.sh` and `quietn.sh` in `.scratch/batch-speed/`: they wait until no
`tilestore` or engine runs, 50 GB is available and the load is under 25%, and note the load at each run's start).

Five pairs, the fifth round's engine against all nine changes (`q6-*`, 18:42 to 18:56). Pairs 1 to 3 on a calm
machine; before pair 4's second run something else started (load 63%), so 4 and 5 are not clean:

| pair | wall | CPU | the cells' wall | the cells' CPU | the main pass's CPU |
|---|---|---|---|---|---|
| 1 | 80.7 to 72.9 s | 1,234 to 1,169 s | 45.6 to 38.1 s | 814 to 726 s | 348 to 390 s |
| 2 | 80.8 to 71.5 s | 1,286 to 1,138 s | 47.8 to 38.7 s | 863 to 712 s | 367 to 355 s |
| 3 | 78.5 to 72.7 s | 1,264 to 1,186 s | 45.5 to 38.7 s | 838 to 728 s | 362 to 372 s |
| 4 | 82.9 to 84.7 s | 1,322 to 1,395 s | 48.6 to 44.9 s | 884 to 836 s | 365 to 478 s |
| 5 | 86.1 to 82.9 s | 1,385 to 1,370 s | 49.3 to 46.1 s | 908 to 863 s | 415 to 436 s |

Three rounds of three, a less calm quarter of an hour (`q7-*`, 18:59 to 19:12): the fifth round's engine, all
nine changes, and the four that stay:

| means of three | fifth round | all nine | the four that stay |
|---|---:|---:|---:|
| wall | 87.4 s | 81.4 s | 81.9 s |
| CPU | 1,419 s | 1,320 s | 1,355 s |
| the cells' wall | 50.2 s | 43.7 s | 44.4 s |
| the cells' CPU | 922 s | 812 s | 846 s |
| the main pass's CPU (nodes and ways) | 425 s | 438 s | 435 s |

- **The cells: 12% less wall for the four that stay (second batch), less in each of its three rounds; 17% for
  all nine in the clean pairs (46.3 to 38.5 s), less in each of the five.** A whole run: 6% less wall and 4.5%
  less CPU for the four that stay; 9.5% and 8% for all nine in the clean pairs. The two builds side by side
  (second batch): 81.9 s and 81.4 s.
- **The main pass: nothing.** In the second batch its CPU is 438 s with the five changes, 435 s without, and
  425 s in the fifth round's engine; in the first batch's clean pairs 372 s with them against 359 s. So they
  went, by this project's rule for exact changes that show nothing net.
- The build that is merged (the four, with the others' code removed) was not timed by itself: it differs from
  the second batch's third column only by code that no longer runs.
- Before these, under the planet timing's load (17:26 to 18:23), three pairs said 10% less CPU, 2% more, 3%
  less: nothing, and they are not used.

**Checks, on the merged build** (`eng-six5`; the build with all nine changes passed the same set before): f0
and f1 snapshots equal to the fifth round's engine; f0's state dump the same 31,695,753 rows; Ontario's 11-14
and europe-west's 11-15 recounts equal to the published snapshots, grids byte for byte; `verifyFast` on Dublin
and Lisboa (25 map data runs, snapshot equal to the fifth round's); `matchCache=verify` on f0; 111 engine tests
on main, none failing, SnapshotReproductionTest among them (TorontoRegressionTest skips, its extract pruned).
New tests: `FirstSeenTest` (the bit set and the sort against a plain set, both sides of the line between
them), and two more in `NodeStoreTest` (every node asked after right and wrong places; a tagged node's tags and
every other node's none). With four pieces broken on purpose, all at
once, on the build with all nine changes, five of its six new or changed tests failed (not rerun one by one).

**What it does not show.** The oracle and London under `verifyFast`, as in the rounds before. A world run: f0
is one file of the Germany rehearsal.

**Next for the engine, none built.** (1) The collector: fewer objects that outlive a pause, which means a
cell's untagged nodes not as 15M `Node` objects (made when asked for), perhaps a quarter of what a cell
promotes (a guess from object sizes, not measured); SC's code iterating `mapData.nodes` decides whether that
is possible. (2) What is still on one thread in a cell's map data (above), and whether three cells at once
gain now that a cell's one-threaded part is smaller (they did not in the first round). (3) The lock above.
(4) The main pass is 30% of a run's CPU and none of this round's guesses moved it: measure it by itself (a
run of only the node and way passes, repeated) before another change there; the dense-node decoder belongs
after that measurement, not before. (5) `Way.isClosed`, `Element.checkValidity`, `groupByNodeIds`: bytes, and
bytes have not bought time.
