## The whole area pass profiled: a tail of three runs, and 30% spent rejecting (2026-11-08)

Next by the AddHousenumber session. London alone, europe-west 11-08, the engine after AddHousenumber's fix, idle
machine. A new opt-in trace, `-Dopenquests.taskTrace=<file>` (engine/README.md), writes each area task's start,
end, thread and CPU time. JFR alone cannot say how many threads are busy, because it samples only a few threads
per tick. Scripts and outputs are in `.scratch/prof-area/` (`run.py`, `region.py`, `cpu.py`); the trace reader is kept as
`tools/task_trace.py`. Same counts: London's
snapshot with the trace equals the published one.

- **London's run phase is 26.7 s; perfectly spread, its CPU would take about 15-18 s.** It is 252 s of thread CPU:
  10.5 s over 24 hardware threads, 21 s over 12 cores. The tail runs earned their CPU alone on a core, at full
  speed, and the same work costs more thread time while both threads of a core are busy, so the floor lies
  between the two. The tail costs about 8-11 s, not 16. The tally after the runs is 1.8 s, and the whole area
  pass is 35.7 s with the map data. The first 14 s are CPU-bound with all 24 threads busy. Then a tail: 3
  single runs go on alone for about 10 s.

  | run | starts | wall | CPU |
  |---|---|---|---|
  | AddHousenumber (one run) | 6.0 s | 20.7 s | 17.2 s |
  | AddMaxHeight (one run) | 6.5 s | 17.2 s | 14.1 s |
  | AddLevelThing (one run) | 11.8 s | 14.4 s | 12.7 s |
  | (shared) kerb nodes | 0.0 s | 17.5 s | 13.1 s |

  Busy threads by second: 24 for 0-11 s, then 23 22 18 15 14 9, then 3 3 3 3 3 3 2 2 1.
- **The 8 kerb runs hold 8 of the 24 threads for about 8 s with no CPU** (0.1 s each), waiting for the shared
  kerb search. They start at 9.3 s, once every other run has started, but the search started at 0 and runs
  17.5 s. That is about 64 thread-seconds idle in the CPU-bound part.
- **Where the CPU goes** (JFR, 2,097 samples in the area pass): 60% inside `ElementFilterExpression.matches`,
  half of it (30% of all) in `KeyReject.mayMatch`, the fast reject saying no to elements that lack a required key.
  13% is id lookups (`LongIndex`, `HashMap`) and under 3% is geometry. GC paused for 7.3 s over the whole run.
  By quest: FastAddMaxHeight 16.6%, FastAddHousenumber 7.4%, FastAddIsAmenityIndoor 5.7%, and the rest under 5%
  each.
- **FastAddMaxHeight spends 42% in `HashSet<Long>.contains`.** The twin kept SC's order:
  `it.id in roadsNodeIds && nodeFilter.matches(it)` hashes a boxed id for each of London's 14.7M nodes, and the
  railway crossing filter does the same with two sets, before the cheap tag filter would reject nearly all of
  them. Putting the filter first is exact, since both are pure tests joined by `&&`.
- **Under JFR at stack depth 256 the run phase was 45 s, not 26.7.** Use JFR's shares, not its times.

Proposed, none built, in order of how little each costs:
1. **FastAddMaxHeight: the filter before the set lookup.** Two lines; it shortens one of the 3 tail runs by
   perhaps a third. Check: same snapshots, and verifyFast, since the twin is what changes.
2. **Start the longest runs first.** Order the queue by the cost each run had last time, or by a fixed list:
   AddHousenumber, AddMaxHeight, AddLevelThing, then the rest. If the tail runs started at 0, London's run phase
   would end near the longest run's own length under load, about 21 s instead of 26.7, near the 15-18 s floor
   once (1) shortens AddMaxHeight. This is the cheap test the level
   session named for AddHousenumber. Start the kerb runs only once the search is done, not once every other run
   has started, so they never hold a thread while they wait.
3. **Candidates by key once per map data**, as proposed in the AddHousenumber section. It targets the 30% spent
   in the fast reject, plus some of the filter tree. For one city it shortens only the CPU-bound first half,
   because the tail stays. For a world run, where two engines keep the CPU full, it is the largest saving left:
   perhaps 1.3-1.5 times on the area pass. Largest change of the three: it touches `mapData.filter` for every
   quest, and must keep map data order.
4. **Not worth it now:** GC (7.3 s of pauses across a 95 s run, much of it outside the area pass) and geometry
   (under 3%).

The area pass is 36 of London's 88 s pass (clean run). The rest is reading the file and the map data (nodes 11 s,
ways 16 s, the area's ways and nodes 18 s, for all of europe-west's 128M nodes, though only London was counted), which none of the above touches.
