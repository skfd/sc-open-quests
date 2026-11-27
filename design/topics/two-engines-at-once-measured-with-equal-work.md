## Two engines at once: measured with equal work (2026-11-07)

The same five Czechia column files (`.scratch/world-spike/par.py`), each engine at 20 GB heap, on the engine
after the 2026-11-06 speed-up and the AddAddressStreet twin, the machine otherwise idle:

| engines at once | wall | each file |
|---|---|---|
| 1 | 342 s | 30-126 s |
| 2 | 248 s | 39-178 s, about 1.4 times slower each |

- **One engine does not fill the machine: two give 1.38 times the throughput.** The first measurement compared
  different work. So a world run counts two cells at once, about 20 GB of heap each.
- **The rate is now about 2.5 s per million nodes with two engines** (3.4 alone; 5.4 on 2026-11-06 before the
  speed-up). The planet's count is then about 7 hours, not 15-17, close to the 6.5 the speed-up session found.
  Not measured: three engines, which memory allows only at a smaller heap.
