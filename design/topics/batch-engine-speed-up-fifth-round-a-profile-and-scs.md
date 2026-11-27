## Batch engine speed-up, fifth round: a profile, and SC's pairs of positions from a plain iterator (2026-11-15, evening)

A JFR run of the fourth round's engine on f0 (`r5.jfr`, `r5-alloc.txt`, `r5-cpu.txt`, read with
`.scratch/batch-speed/jfrtop.py`: weight by the first frame that is not the JDK's), to choose what to take out
of the 515 s above. **Built from it: one patch to the vendored SC code, about 11% less allocated in a run;
CPU 1 to 5% less in four interleaved pairs, wall time not shown.**

**What the profile says is allocated** (238 GB by the samples' weights; shares of that):

| | share |
|---|---:|
| `asSequenceOfPairs` (pairs, coroutine objects, iterators), nine tenths of it under `ElementGeometryCreator.create` | 10% |
| decoding blocks (protobuf's `long[]` and `int[]` of dense nodes and their info, inflating) | about 13% |
| `LongArrayAsList.get`: a way's node id made an object (`Way.isClosed` 3.3 GB, the crossing search, AddCrossingIsland, AddMaxHeight) | 3.2% |
| `getLastCheckDateKeys`' strings | 2.8% |
| `TagMap`'s entries, nearly all from `Element.checkValidity` when a way or node is made | 2.4% |
| `hasPrefixed` (`asIfItWasnt` in LifecycleUtils) | 2.3% |

**The patch (`pairs` in `sync-sc.ps1`).** SC's `Iterable<T>.asSequenceOfPairs()` is a `sequence { }` coroutine;
its geometry code (`isRingDefinedClockwise`, `centerPointOfPolygon`, `measuredLength`, `centerLineOfPolyline`,
the area) walks every way's positions through it, some of them twice. The patched function gives
`openquests.pairsOf` (`Pairs.kt`): the same pairs in the same order from a plain iterator, the source first
read when the first pair is asked for, as SC's. SC's body stays in the file under another name
(`asSequenceOfPairsAsInStreetComplete`), and `PairsTest` holds the replacement against it (lists of 0 to 40
items, nulls, a second walk, a list changed between `iterator()` and the first pair, the end of the iterator,
as many items taken from the source). No result changes.

| f0, interleaved, with collector logs | fourth round's engine | with the patch |
|---|---|---|
| allocated, from the young collections' sizes | 215 and 215 GB | 191 and 191 GB |
| CPU | 1,479 and 1,455 s | 1,463 and 1,437 s |
| wall | 94.0 and 85.9 s | 90.3 and 98.0 s |
| young pauses | 12.1 and 11.1 s | 10.9 and 11.9 s |

(Runs `g-marks-3`, `g-pairs-3`, `g-marks-4`, `g-pairs-4`. Two pairs before, on a first form of the same change:
CPU 1,494 and 1,476 s against 1,452 and 1,396 s, wall 94.8 and 92.7 s against 94.9 and 88.7 s.) The machine
was busy again (the fourth round's engine was at 82 s an hour before and at 86 to 97 s here), so **the wall
time shows nothing either way; the allocation figure is the one that repeats.** The pairs are short-lived, so
what they cost is young collections, and the pauses did not move in a way these runs can show.

**Tried and dropped: the filter's test of an element's type.** A quarter of the quest runs' `HashMap.getNode`
samples (6% of all Java samples) sat under `ElementFilterExpression.includesElementType`, which asks a
`Set<ElementsTypeFilter>` on every `matches`. With three flags worked out once in its place, two interleaved
pairs gave quest CPU 375 and 368 s against 354 and 363 s, snapshots equal: not a gain these runs can tell from
noise, and likely the sample of the first read of an element that is not in the cache, not of the set. Not
kept: a patch to SC's code has to earn its place.

**Checks**, on the final build: `same.py` on f0 (four runs) and f1; f0's state dump the same 31,695,753 rows;
Ontario's 11-14 and europe-west's 11-15 recounts equal to the published snapshots, grids byte for byte;
`verifyFast` on Dublin and Lisboa (25 map data runs, snapshot equal to the third round's); 108 engine tests on
main, none failing, SnapshotReproductionTest among them (TorontoRegressionTest skips, its extract pruned).
`sync-sc.ps1` ran
whole against the v64.1 checkout and changed only `Collections.kt` and `SC-VERSION.txt`. **That run also
settles the third round's open point:** `helper:KerbUtil`'s pin was checked against a real checkout and holds.
The checkout at `%TEMP%\sc-v64.1` had lost its index and most files outside the quest sources (a temp cleaner,
by the look of it); it was restored with `git reset` and `git checkout -- .` at the same commit, f8a754b1, and
the harness's own untracked files in it were left as they were.

**What it does not show.** A wall-clock gain. The oracle and London under `verifyFast`: as in the fourth round.

**Next for the engine, none built.** From the same profile, by what they allocate: (1) decoding: the dense
nodes' `long[]`/`int[]` builders are a tenth of a run's bytes and the main pass's nodes and ways are 370 s of
CPU; a reader that decodes a dense block's packed fields straight into the engine's arrays, without
protobuf's builders, is the largest single piece left, and a larger change (its own oracle: the same nodes,
ways and tags from both readers on a whole file). (2) `LongArrayAsList` as a `List<Long>`: `Way.isClosed`
makes two objects a call; a patch like `pairs` or a cache of the two ends. (3) `Element.checkValidity`
iterating a `TagMap`'s entries: give `TagMap` a walk without entry objects. (4) `groupByNodeIds` (4% of Java
samples). Each of 2 to 4 is 2 to 3% of the bytes.
