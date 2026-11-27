## A rewrite in a systems language: discussed, nothing built (2026-11-06)

The owner asked whether a rewrite into a memory-efficient systems language would give a speed-up. Answer: yes,
but not first. The profile above was read again (`.scratch/world-spike/prof.jfr`), and it changes one earlier
conclusion. No engine code changed and nothing was run.

- **What a rewrite would buy, estimated, not tested:** 3 to 5 times on CPU work, about 10 times less memory (about
  1 GB per million nodes today), no collection.
- **What it would cost:** the engine is trusted because it runs SC's own code, checked against SC by the oracle.
  A rewrite ports about 10,500 lines of vendored and ported Kotlin plus the opening-hours, preset and
  country-boundary libraries, and every repin (REPIN.md) becomes a manual port and a full recheck. Geometry maths
  would have to match the JVM closely enough to keep the same counts. Only the 140 filter quests move easily,
  being strings; the 52 custom quests are logic. No port of `ElementFilterExpression` exists (PRIOR-ART.md).
- **Kotlin/Native and GraalVM native-image** keep SC's code, but should help start-up and memory, not sustained
  speed. Expected, not measured.
- **The profile, weighted by CPU.** JFR samples at most 5 threads a tick, so stages with few threads count for
  too much. Weighting each 10 s window by the JVM's CPU load: filters, tag walks and hash lookups about 61%,
  reading the pbf 17%, the rest 21%. Area quests 59%, the pass over the file 30%, map data 11%. CheckExistence
  falls from 12% to 6%. Most of the 61% is quests checking elements that hold none of their keys, which is an
  algorithm problem: a Rust port would need the same fix.
- **Collection:** 9.2 s of pauses in 106 s here, more on a small heap (Ontario about 80 s longer at 16 GB than at
  40 GB). Boxing is a large part of the allocation: `Long` 19%, `Float` 8%, `Pair` 4%.
- **"CPU is the limit" (above, 2026-11-06) is not proven.** The 520 s was five columns on two engines; the 522 s
  was 15 cells on one. Different work, and no run put the five columns through one engine. Larger areas also
  cost more per node in that run: column 1, 31.4M nodes, 14 s per million; column 4, 11.8M, 6.2 s.
- **The engine averaged 7.3 of 24 threads in this run.** About 20 s of 106 s was the serial map build
  (`assemble`, `putNode`) and about 25 s was CheckExistence alone. The recut was running at the same time
  (machine 51-97% busy, JVM far less), so times are rough, but both stretches come from how the code is built.
  So 5.4 s per million nodes includes idle time, and HARDWARE.md's L-hours may be pessimistic for a machine
  that overlaps cells. With 12 physical cores, filling the idle threads will not give 3 times.
- **A repeated run.** `AreaPass.countIn` (`AreaPass.kt:256`) reruns every area quest with a result at LONG_AGO,
  also those with `usesAge = false`, 27 of the 40. They are 31% of CPU, so about 15% is repeated work, if a
  snapshot diff confirms they ignore the clock.
- **The 13 age area quests walk the map data four times** (now, 0.5, 2, 1900), 28% of CPU. The clock and
  multiplier overrides are thread-local, so the four runs can go in parallel without touching SC's code, which
  shortens the tail. One walk with four evaluations would save more, but patches SC's code.

**Proposed order, none of it built:**
1. Clean test on an idle machine: one column alone, then two at once, same files, with process CPU time. About 15
   minutes. It settles the concurrency question and HARDWARE.md's figures.
2. Skip the repeated run: about 1.18 times.
3. Run an age quest's four passes in parallel.
4. Fast reject: 1.7 to 2.5 times, the estimate above. It waited for the cell test, which passed.
5. A compact tag map behind `Map<String,String>` (built in `Pbf.kt` and `AreaPass.kt`, so SC's code is untouched),
   less boxing, a trial of ParallelGC. Not measured, and it overlaps with the fast reject.

Steps 2 and 4 alone would give about 2 to 3 times if they hold, which meets the 2 times a daily count needs in
8 hours on this machine.

**When native code makes sense.** A native data layer only if the planet still does not fit after these
steps; reading the pbf is 17% of CPU, so that alone gives about 1.2 times at most. A full rewrite only if the goal
changes: 16 GB workers, much larger cells, or a count of an hour or two. That is a separate project with its
own repin process.
