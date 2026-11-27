## The clean engine test (2026-11-07)

Czechia's five columns, 97.5M nodes, from 00:06 with the recut finished and the machine idle. Old engine is
d4b4fe25, new is 4c8784c3. CPU is the processes' own time; heap 26 GB, 20 GB with three engines. Script and
results in the session's scratchpad, not kept.

| engine | at once | wall | CPU | threads used | machine busy |
|---|---|---|---|---|---|
| old | 1 | 691 s | 6,287 s | 9.1 | 42% |
| old | 2 | 452 s | 6,321 s | 14.0 | 62% |
| new | 1 | 305 s, 318 s | 4,040 s, 4,095 s | 13 | 58% |
| new | 2 | 219 s | 4,074 s | 18.6 | 82% |
| new | 3 | 211 s | 4,356 s | 20.6 | 90% |
| new, ParallelGC | 1 | 307 s | 3,935 s | 12.8 | 57% |

All seven runs give the same snapshots.

- **The speed-up is 2.2 times like for like** (691 s to about 311 s), and 3.2 times with two engines against the
  old way of running one. CPU fell by a third; the rest is threads that used to sit idle.
- **"CPU is the limit, running more buys nothing" was wrong for the old engine.** A second engine took it from 691 s
  to 452 s. The 520 s against 522 s of 2026-11-06 compared different work.
- **Run two engines, not three.** The second gives 1.4 times, the third 4%: at 90% of 24 threads on 12 cores, CPU
  really is the limit.
- **2.25 s per million nodes**, against 5.4 measured on 15 cells: about 2.4 times, and a planet of 10-11 billion
  nodes in 6.1 to 6.9 hours on this machine. On paper a daily world count fits here: diffs 2 h, count 6.5 h, publish
  1 h, about 9.5 hours. These runs were 4 minutes; a laptop chip holding speed for 6 hours is still untested.
- **ParallelGC buys nothing:** the same wall time, 3% less CPU, 35 to 75% more peak heap. G1 stays.
- **Large areas gained most:** column 1 (31.4M nodes) fell from 278 s to 109 s, a
  bigger gain than column 4's 68 s to 33 s. Its peak heap is 19.5 GB, from 27.3 GB.
