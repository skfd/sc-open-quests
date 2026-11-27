## Batch engine speed-up, fourth round: the node ids of some ways as marks, by one rule in the port script (2026-11-15, evening; owner: "continue engine optimization")

The rule the section above proposed, built and merged into main. **A small gain: about 14 s of quest CPU on
Germany f0 (the twelve ports 63.5 and 60.0 s to 48.2 and 47.4 s), not the 67 s the section above named:** that
figure was the twelve ports' whole CPU, and most of it is their scans and filters, not the set. A whole run
shows 2 to 3% less wall time in two interleaved pairs, which is within what the same engine varies by.

| | third round's engine (`eng-final`) | with the rule (`eng-marks`) |
|---|---|---|
| f0 wall | 91.0 and 84.6 s | 88.6 and 82.3 s |
| f0 CPU | 1,365 and 1,319 s | 1,366 and 1,284 s |
| every quest run, CPU | 355 and 342 s | 345 and 324 s |
| the twelve ports | 63.5 and 60.0 s | 48.2 and 47.4 s |
| AddBollardType | 11.5 and 9.9 s | 4.7 and 4.9 s |
| AddCrossingIsland | 10.0 and 9.8 s | 8.0 and 7.5 s |
| AddTactilePavingCrosswalk | 10.9 and 10.0 s | 9.1 and 8.7 s |
| AddRailwayCrossingBarrier | 7.7 and 7.7 s | 6.8 and 6.9 s |
| AddStileType | 3.9 and 3.2 s | 2.3 and 2.4 s |
| the two traffic signal quests | 9.4 and 9.5 s | 9.5 and 9.4 s |

(Runs `d-final-1`, `d-marks-1`, `d-final-2`, `d-marks-2` in `.scratch/batch-speed/`, in that order, the machine
calmer than in the afternoon; the per-quest figures are thread CPU summed from the task traces.)

**The rule** (`NODE_IDS` in `engine/port_area_quests.py`): in a port, `.flatMapTo(HashSet()) { it.nodeIds }`
becomes `.nodeIdsIn(mapData)`, which gives an `openquests.NodeIds` (`NodeIds.kt`). On a city's map data that is
a bit at each node's place in the map data's nodes, plus a `LongSet` of the ids of nodes the map data lacks (a
way at the edge of the data names some), so **every id is answered as SC's `HashSet<Long>` answers it, whoever
asks**; the third round's twins could leave those ids out because their own code never asks about them, a rule
applied blind to every port cannot. On any other map data it is SC's `HashSet`. `NodeIds` has `contains` and
nothing else and is no `Set`: a port that iterates such a set or asks its size does not compile after the
rule, so a future SC change cannot be rewritten into a different result. `-Dopenquests.nodeMarks=false` keeps
SC's set everywhere.

**Not applied to a quest with a fast twin** (the script reads `FAST_TWINS` from `FastTwins.kt`): AddEntrance,
AddCrossingKerbHeight, AddMaxHeight and AddAddressStreet keep SC's line, since their ports do not run in a
count and are what `verifyFast` and `NodeSetTwinsTest` hold the twins against. The other line of
AddCrossingIsland (`{ it.nodeIds.firstAndLast() }`, asked about way ends) is left as it is. Before the rule was
added, the script was rerun on all 40 ports from the SC v64.1 checkout
(`%TEMP%\sc-v64.1`) and reproduced every file and pin; with the rule, the diff is the twelve ports, each with
one line, one import and its header.

**Checks.** `same.py`: f0 twice and f1 equal to the third round's engine; f0's state dump the same 31,695,753
rows; europe-west's 11-15 and Ontario's 11-14 recounts equal to the published snapshots, their grids byte for
byte (Ontario and one more f0 on the final build, after the last commit).
`-Dopenquests.verifyFast=true` on Dublin and Lisboa: the twelve ports have no twin, so under that switch
`nodeIdsIn` builds SC's `HashSet` beside the marks and asks both about every node of the map data, every id
of the set and every id a port asks about, and stops the run on a difference (`CheckedNodeIds`); the run
passed, with the twins equal to their ports on 25 map data runs and the snapshot equal to the third round's.
`NodeIdsTest` (four tests): every id from 0 to past the last one answered as SC's set answers it on 200
random map data whose ways name nodes the map data lacks, failing when those ids are dropped
(`KEEP_OTHER_NODE_IDS`, the test's switch); each of the twelve ports on 300 random `ArrayMapData` against the
same data seen as plain `MapDataWithGeometry` (no marks, no candidates by key: SC's path), same elements in
the same order at both clocks, each port finding something; the set of ports that hold `nodeIdsIn` is exactly
those twelve and none has a fast twin; the check that `verifyFast` turns on passes on whole sets and throws
when the lacking nodes' ids are dropped (called with its switch as an argument, so the test does not depend
on the property). 105 engine tests on main, none failing, SnapshotReproductionTest among them
(TorontoRegressionTest skips, its extract pruned).

**What it does not show.** The port test cannot fail on the dropped ids, since none of the twelve asks about
an id that is no node of the map data (the direct test does). The wall gain is not separated from noise.
London under `verifyFast` and the polar and antimeridian cells: as in the third round. The oracle
(`tools/sc-harness` CheckCustomQuests), which the third round's text said would hold the rewritten ports, was
not rerun: the ports are held by the tests and recounts above, not against the app's own run.

**Where the time is now** (`d-marks-2`: 82.3 s wall, 1,284 s CPU): the main pass's nodes and ways about 370 s
of CPU; the cells about 845 s (the log's cell lines), of which the quest runs are 324 s, so **about 515 s of the cells' CPU is making
map data and the collector, and no one quest is above 27 s** (the shared searches 33 s together, AddHousenumber
27, AddMaxHeight 25, AddIsAmenityIndoor 21, AddBarrierOnRoad 19, AddLevelThing 18, CheckExistence 14). More
quest twins now buy a percent each.

**Next for the engine, none built, in the order of what they could take out.** (1) What the collector is fed
and the map data's making, the 515 s: profile one cell's allocation again (decoding a block was a sixth of a
run's bytes at midday; `getLastCheckDateKeys` builds its strings for every age test) before choosing. (2)
`WaysCrossingUtils.groupByNodeIds` behind AddBarrierOnRoad, AddBarrierOnPath and AddCrossing (41 s together
now; maps of boxed ids to lists of ways; a twin has geometry to keep). (3) Small: five of the twelve ports are
age quests whose four runs each gather the same set from a filter that reads no clock; a rule that keeps such
a set once per map data and filter could take a few seconds more out of their 32 s.
