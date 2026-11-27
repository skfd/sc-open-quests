## Batch engine speed-up, second round: a match cache and the level quests (2026-11-15)

Same test file, runner and comparer as the section above (Germany f0, 30 GB, two cells at once, the pause target).
Built on `batch-speed` and merged into main the same afternoon (main's engine rebuilt; 96 engine tests pass
there, SnapshotReproductionTest among them). Each step with the same snapshot.

| step | f0 wall | f0 CPU | main pass (nodes + ways) | cells |
|---|---:|---:|---:|---:|
| main (fa262f11) | 117.4 s | 1,874 s | 8.1 + 19.8 s | 70.1 s |
| the level twins keep only the nodes near a mall | 101.1 s | 1,781 s | 8.3 + 19.6 s | 53.2 s |
| **the main pass settles a quest once per tag signature** | **91.5 s** | 1,566 s | 6.2 + 10.9 s | 54.4 s |

Single runs; wall time varies by about 5% between equal runs. f1: 110 s to 86.9 s. With `--dump-state`: 187.6 s
on main (measured the same hour) to 129.8 s, the same 31,695,753 rows. **2.7 times since the engine of 11-14
(245 s).** Ontario's daily-style run shows no gain that can be told from noise: its pass was 51.7 s in today's
daily run (36 GB, main's engine) and 51.4 s recounted alone at 30 GB; the main pass in it went from 17.2 s to
13.3 s (nodes 8.9 to 5.3 s, ways 7.2 to 6.2 s) and the rest took as much longer in that one run. Only 4.6M of
Ontario's ways lie in a city and reach the quests.

**The level quests.** The task trace of the last run showed that a cell's run phase lasted as long as one run:
AddLevelThing, 1.1 s to 10.8 s of a phase of 10.8 s (f0c10), the others done by 7.3 s. Its filter (`!level and
(!location or location = indoor)`) holds for almost every node, untagged ones too, so the twin copied the map data
into a list, looked up every node's geometry by id and put all 14M positions into a grid of boxed lists, to ask a
handful of malls which points they contain. Now a node goes on only if it lies in a 0.01 degree square that some
mall's bounds touch (`NearBounds`, a set of primitive keys), tested before the filter; a node's position is the
node's own. A point outside every mall's bounds was never returned by the grid, and the order of the rest is
kept, so the result is the same. AddLevelThing's wall time over the file's cells: 82.6 s to 31.9 s; the cells'
phase 70 s to 53 s. A cell's longest run is now AddHousenumber (7.9 s).

**The match cache** (`MatchCache.kt`, `-Dopenquests.matchCache=true|false|verify`, on by default). A profile of
last night's engine (`k3.jfr`, a three-cell run from before AddHousenumber's twin) had a quarter of the Java samples in the main pass's `offer`: some 120 quests asked of
each of 23.8M tagged elements, 40% of it in SC's filter trees, 24% in the fast reject, 20% in the custom ports, 15%
in the loop. Most elements are alike in everything a filter can see, so:

- A filter's leaves are of two kinds: those that read tags only, and the *open* ones that read the clock, the
  resurvey setting or the element's timestamp (`older`, `newer`, a date tag against `today`).
- An element's **signature** is, for each tag whose key a tag leaf names (or a key regex matches), the key and the
  *class* of its value: two values are of one class when every tag leaf on that key answers the same for both. The
  classes come from asking SC's own leaves about an element holding just that tag; no leaf is re-implemented.
  `surface=asphalt` and `surface=concrete` may be one class; a house number is not in the signature at all.
- Per signature and element type each filter quest is evaluated once in three values (a tag leaf by SC's `matches`
  on the element at hand, an open leaf as unknown): false whatever the clock (not asked again), true whatever the
  clock (counted with the bits `matchVariants` gives when every variant holds), or unknown (asked of every such
  element, as before, with its dates for `--dump-state`).
- A ported custom quest is never settled as open. It is asked unless the filter its port starts from
  (`CustomQuest.necessary`, the `filter.matches(element) && ...` of each port) is false for the signature.
- Gating by position, notes, parts and the grid stay per element.

On f0: 18.5M ways have 336,774 signatures and 5.2M nodes 75,863, so 98.2% and 98.5% of elements reuse an answer;
**2.2 quests are asked of a way and 1.7 of a node, of 125 and 118**. 694 keys are named by a filter, of 14,868
seen. `fixme` is the only key with many values remembered (12,691, two classes); a key stops remembering at
200,000 values and a type at 2M signatures, and works the answer out each time past that.

**Checks.** `matchCache=verify` asks every quest of every element as before and stops at the first difference,
the `--dump-state` dates too: f0's 23.8M elements passed, and Dublin and Lisboa. f0 and f1 snapshots equal to
main's; f0's state dump the same 31,695,753 rows; Ontario's recount of 2026-11-14 equal to the snapshot main's
engine published that day, its tile grid byte for byte. `verifyFast` on Dublin and Lisboa: every twin equal to
its port on 20 map data runs (AddLevelThing 3 and 179 open there). `MatchCacheTest`: 60,000 random elements made
of the filters' own keys and values, every settled answer checked against SC's matcher at five clocks and three
resurvey settings. 96 engine tests pass in the worktree (SnapshotReproductionTest and TorontoRegressionTest skip
there).

**What the CPU is now** (JFR of f0, Java threads): the area pass 59%, the main pass over the ways 19% and the
nodes 9%, the match cache itself 2.7%. No single item is large any more: reading the ways a second time for the
area pass (`collectWays`) 7.9%, the kerb search shared by two quests 5%, a cell's way geometries 4.2%,
AddHousenumber 3% (a third of it a `HashSet<Long>` asked for every node of every area), AddIsAmenityIndoor,
AddEntrance, AddCycleway and AddMaxHeight about 2.5% each. The collector's pauses are 15.6 s of a run.
**Next, none built:** one read of the ways; AddHousenumber's set as primitives (it is a cell's longest run); the
kerb search; then the cut, which is now the larger part of a world chain.
