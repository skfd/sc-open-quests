## Batch engine speed-up, third round: one read of the ways, and node sets by place (2026-11-15, afternoon; owner: "continue engine optimisation")

Same test file, runner and comparer as the two sections above (Germany f0, 30 GB, two cells at once, the pause
target). Built on `batch-speed`, each step with the same snapshot. **The machine was not quiet this time:** another
session cut and read tile stores in Rust on all threads through the afternoon, and main's engine took 98 s to
134 s from one run to the next (it was 91.5 s at midday). So every figure below is from runs interleaved with
the engine it is held against, a few minutes apart (`.scratch/batch-speed/batch.sh`), and the CPU seconds say
more than the wall seconds.

| step | f0 wall, against the step before in the same minutes | f0 CPU |
|---|---|---|
| one read of the ways for both passes | 95.7 and 100.3 s against 109.6 and 105.9 s | 1,508 and 1,536 s against 1,700 and 1,694 s |
| a node found through a table of id stretches | 106.5 and 106.8 s against 109.8 and 110.9 s; alone, below | 1,690 and 1,704 s against 1,691 and 1,758 s |
| node sets as marks by place (the kerb search, AddEntrance, AddCrossingKerbHeight, AddHousenumber) and AddCycleway's clock-free work once | 117.7 and 99.9 s against 125.9 and 116.8 s | 1,549 and 1,572 s against 1,802 and 1,705 s |
| all of it against main (6d7ee700's engine), the other session's cuts running | 117.7 and 99.9 s against 133.9 and 127.6 s | 1,549 and 1,572 s against 1,866 and 1,911 s |
| **the same, after those cuts had ended (15:35)** | **89.5 and 87.4 s against 102.2 and 104.0 s** | 1,518 and 1,485 s against 1,796 and 1,828 s |

**About 15% less wall time and 17% less CPU on f0** (13 to 17 s of about 103 in the calmer pair; 16 to 28 s of
about 130 in the busy one). Main's 102 to 104 s in that last pair is still above its 91.5 s of midday, so the
machine was calmer, not quiet: the ratio is what these runs show, not a new absolute figure.

**Where the time was** (the midday run's phases, trace and profile: `m2-cache`, `m2.jfr`): of 91.5 s, the cells'
area runs 54 s, the main pass's ways 10.9 s and nodes 6.2 s, and the area pass reading the ways a second time
7.0 s, all of that last one before the first cell starts. In the cells the quest runs are about 450 s of about
1,040 s of CPU; the rest is map data and the collector (281 GB allocated in a run by the profile's samples;
15.6 s of pauses; marking beside the program for most of the run). With two cells at once a run takes about
twice its CPU in wall time, so CPU taken out of the cells shortens them.

**One read of the ways.** The area pass decoded every way block again to find the ways with a node in some
padded cell box (`collectWays`), looking each node up twice (its place, then its coordinate): two thirds of
its samples were that search. The main pass looks the same nodes up for every tagged way. Now the main pass's
read hands each way to the area pass (`AreaPass.citySetOf`, `collectWay`): one decode, one lookup a node, one
tag map for both. "ways" plus "area: ways" went from about 20 s to about 14 s in the paired runs. The chunks
are let go once they are one table (the first build kept them reachable through the cells, several GB more
for the collector to walk).

**A table of id stretches.** `NodeStore.indexOf` searched the blocks' first ids and then inside the block,
some 27 steps. It now reads where the stretch of 256 ids that holds the id starts (one `Int` for each 256 ids
between the file's first and last: about 210 MB for a file whose ids span the planet's) and searches the few
nodes there; a stretch is longer where a file's ids span more than 2^27 of them (OSM's do not).
`NodeStoreTest`. **A small gain, shown only when measured alone:** the main pass by itself
(`-Dopenquests.areaPass=false`), four interleaved rounds: "ways" 13.0 to 14.3 s with the table against 14.4 to
15.6 s without, "nodes" 6.6 to 7.7 s against 6.1 to 7.1 s (the table is filled there, on one thread): about
0.75 s net, 3% of that pass's CPU. In whole runs it does not stand out of the noise.

**Node sets as marks by place.** A third of the quest runs' samples were `HashMap` code, and its callers were
SC's own quest code doing one thing: gathering the node ids of some ways into a `HashSet<Long>` (an object an
id, millions in a cell) and then asking it about the map data's nodes. On a city's map data a node is known by
its place in the map data's nodes (`ArrayMapData.nodePosition`), so such a set is a mark at that place; an id
that is no node of the map data is asked of nothing by SC's code either. Each twin gives the port's elements
in the port's order and falls back to the port on any other map data:

- **The kerb search** (`fastKerbNodes` in `FastKerbs.kt`, a copy of SC's `KerbUtil.kt`, pinned as
  `helper:KerbUtil`). SC's code keeps the footway nodes in a set of whole `Node`s (hashed with position and
  tags), counts crossing ends in a map of boxed ids, removes every node of every road and path from it one by
  one and looks each up again for `barrier=kerb`. The twin keeps a byte of marks a node. SC's counts and
  removals do not depend on each other's order, which is why marks can stand for its sequence of steps.
  `-Dopenquests.fastKerbs=false` runs SC's. It was the longest task of the two cells looked at (6.6 s and
  11.1 s of wall).
- **AddEntrance**: three marks (a building's node, an incoming path's, an excluded way's). SC's code also
  offered its building filter every node of the map data.
- **AddCrossingKerbHeight**: the excluded ways' nodes as a bit a node, found once for the quest's four runs.
- **AddHousenumber**: the address nodes' ids in a `LongSet` (plain longs, open addressing, a removal closes
  its gap) in place of the key view of a `HashMap<Long, Node>`.
- **AddCycleway** is the other kind: an age quest whose four runs each filtered the roads and, for every
  eligible road, found its centre and country before looking at its tags. Its twin does what reads no clock
  once per map data (`CYCLEWAY_ROADS`: the roads with no cycleway tagging, and for each road with some what
  `hasOldInvalidOrAmbiguousCyclewayTags` decides before and after its one test of age), and places only the
  roads whose answer turns on the country.

Quest CPU over f0's cells, from the traces of the same two rounds (the engine before these twins, then with them):

| | before | after |
|---|---:|---:|
| the kerb search | 44.5 and 41.8 s | 17.8 and 18.0 s |
| AddCycleway, with its shared part | 37.6 and 36.7 s | 7.1 and 6.9 s |
| AddEntrance | 28.7 and 27.1 s | 8.8 and 9.2 s |
| AddCrossingKerbHeight, with its shared part | 24.5 and 21.9 s | 6.2 and 6.1 s |
| AddHousenumber | 36.6 and 35.3 s | 32.6 and 31.2 s |
| every quest run | 507 and 489 s | 409 and 399 s |

The cells' CPU as a whole went from 1,260 and 1,203 s to 1,017 and 1,008 s, more than the quest runs lost: the
sets were also what the collector was fed. AddHousenumber's set was a tenth of it, not the third the midday
profile suggested.

**Checks**, on the final build unless said. `same.py`: f0's snapshot after each step, f0's and f1's at the end,
equal to main's; f0's state dump the same 31,695,753 rows; `matchCache=verify` on f0 (the main pass now makes
one tag map for both passes). Ontario's 11-14 recount equal to the snapshot main published, its tile grid byte
for byte; europe-west's 11-15 recount with the daily run's settings (London, Dublin, Lisboa) equal to the
snapshot published that morning, its grid byte for byte. `verifyFast` on Dublin and Lisboa: every twin equal
to its port on 25 map data runs, and that snapshot equal to the second round's (run before the last commit to
the node table and again on the final build). New tests: `NodeStoreTest`;
`LongSetTest` (against a `HashSet` through 60,000 adds, removals and questions a seed); `NodeSetTwinsTest`: the
kerb search and the twins of AddEntrance, AddCrossingKerbHeight, AddCycleway, AddKerbHeight and
AddTactilePavingKerb against SC's own code on 400 random small map data (shared ends, closed ways, ways of one
node, nodes the map data lacks, ways with no geometry), in order and at two clocks; it fails when a rule is
taken out of a twin (tried on the kerb search and on AddCycleway). 101 engine tests, none failing, in the
worktree (SnapshotReproductionTest and TorontoRegressionTest skip there).

**What it does not show.** A quiet machine's wall time. The daily runs' gain: Ontario and europe-west were
recounted for equality, and their one pass each (49.4 s against 51.4 s at midday; 37.7 s against the published
run's 43.1 s) is on different loads. London under `verifyFast`: not run, since SC's own code takes tens of
minutes there; London's counts are held by the europe-west recount instead, which shows the same totals and
grid, not twin against port. AddHousenumber's twin is not in `NodeSetTwinsTest` (it needs building polygons);
Dublin, Lisboa and the recounts hold it. As before, no world file with a
polar or antimeridian cell (run the canary first on 12-07). The `helper:KerbUtil` pin is the hash of the
vendored copy with LF endings, not of a StreetComplete checkout (none is on this disk): if the next repin
reports it moved without a change in `KerbUtil.kt`, that is why.

**Next for the engine, none built.** The same line, `.flatMapTo(HashSet()) { it.nodeIds }`, is in twelve more
ports that run as they are (AddBollardType, AddCrossingIsland, AddTactilePavingCrosswalk, AddBarrierOpening,
AddCrossingMarkings, AddCrossingSignals, the two traffic signal quests, AddRailwayCrossingBarrier, AddStileType,
AddStepCountStile, AddEntranceReference): about 67 s of the 390 s of quest CPU left in f0's cells (bollards 13 s,
tactile paving at crosswalks 11 s, crossing islands 10 s, railway crossings 8 s). It is also in AddMaxHeight and
AddAddressStreet, whose hand-written twins run instead of the ports and would take the marks by hand.
**One rule in `port_area_quests.py` would reach the twelve instead of a twin each:** rewrite that line to a call that gives marks by place on a city's map data and SC's
`HashSet` on any other, as `CANDIDATES` rewrote the scans; the oracle and `verifyFast` then hold every port at
once. After it, `WaysCrossingUtils.groupByNodeIds` behind AddBarrierOnRoad, AddBarrierOnPath and AddCrossing
(about 46 s together; maps of boxed ids to lists of ways; a twin there has geometry to keep, so more to check). Then what the collector is fed:
decoding a block is a sixth of a run's allocated bytes, and SC's `getLastCheckDateKeys` builds its strings for
every age test. The longest runs of a cell are now AddHousenumber, AddMaxHeight and AddIsAmenityIndoor (about
30 s of CPU each over the file). The cut is still the larger part of a world chain.
