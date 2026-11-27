## Engine heap: what the machine can spare (2026-10-24)

- **The owner's rule:** as much heap as the machine can spare, and run when memory is not busy. No fixed
  cap. `run.py engine_env(heap=True)`, used by `count` and `backfill_history.py`, reads Windows'
  `GlobalMemoryStatusEx` at each engine start and passes `-Xmx` = the smaller of free physical memory and
  free commit charge, less 8 GB, at most 75% of physical memory. An explicit `-Xmx` in `JAVA_OPTS` wins;
  the build's `-Xmx40g` stays as the default off Windows.
- **The commit charge is the real limit here.** On 2026-10-24 at 22:55: 50 GB of RAM free, but only 28 GB
  of commit charge left (the paging file is 27.8 GB, and something holds committed memory it does not
  touch). That is what killed the 2026-10-17 run: a 5.3 GB commit failed with physical memory to spare.
  Spare heap at that moment: 19 GB.
- **Busy memory waits, then skips.** Under 12 GB spare (Ontario counts in 12-16 GB), the engine waits and
  re-reads every minute, up to 60 minutes (`SCOQ_HEAP_WAIT_MINUTES`), then the run stops with a clear
  error. A skipped count is not lost: the next run goes over every stored extract.
- **A region may need more than 12 (2026-11-23).** `"minHeapGb"` in `config/regions.json`
  (`run.region_min_heap_gb`): the engine for that region waits for that much, not for `HEAP_MIN_GB`, with a
  line every 5 minutes (`HEAP_LOG_MINUTES`) and the same 60-minute bound (`HEAP_WAIT_MINUTES`), then raises
  `run.MemoryBusy`. Only europe-central has one, 27: on 11-21's Europe clip its engine died of
  `OutOfMemoryError` at 14 g and counted at 27 g. The other regions have none, as before. The city run ends
  with that error as its `ERROR:` line, naming the heap the machine could spare and the heap needed. The
  world loop's gate (`world_gate.clip_side`) ends the run with no STOPPED and the next run resumes the day
  at its gate ("The world day on the planet").
- **The heap is a metric.** The city run logs `engine heap, <region>: -Xmx<N>g ...` before each engine,
  and the engine's last line gives the peak. The gate logs `gate heap: <region> given N MB, peak M MB` for
  each region and keeps both in `gate.json` (`"clip heap"`), read off the engine's log
  (`run.engine_heap_of`). The peak follows the heap given (28,251 MB of 28,672 and 27,189 of 27,648 for
  europe-central): it says a heap was enough, not how little would be.
- **Same counts.** Bremen 2026-10-23 with `-Xmx19g` equals the archived snapshot. A smaller heap is a
  little slower (Ontario 260 s at 16 GB against 188 s at 40 GB), not different.
