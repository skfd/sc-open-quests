# The world day off power throttling: a switch and its readings (2026-11-28; owner via osmium-windows-fast: "go ahead and set it up")

A trial, not yet a decision: whether the world day runs faster when Windows does not power-throttle (EcoQoS) its
processes. Brief: `~/Code/osmium-windows-fast/journal/2026-11-28-sc-open-quests-throttling-brief.md`; background its
README, "Cause 3" (fast cores 0-7, slow 8-23; a headless process is the likely one to be throttled; the opt-out is
not inherited).

- **The switch:** `SCOQ_QOS` in the environment, else `data/qos.txt` (gitignored): `<YYYY-MM-DD> <mode>` for the run
  started that local date, a bare `<mode>` otherwise; no file is `default`. `high` = every process of the day
  opted out of throttling (`SetProcessInformation(ProcessPowerThrottling, Control 1, State 0)`) and BELOW_NORMAL;
  `default` = nothing set, everything still recorded; `off` = no watcher. The way back is a word in that file.
- **Priority is meant not to be part of the trial:** the task has no `<Priority>`, so Task Scheduler's default (7,
  BELOW_NORMAL) is expected to apply to the day and its children, and `high` then changes the throttling flag only.
  Expected, not yet observed: 11-28's procs.csv settles it (python.exe's row). If it reads `normal`, the `high` days
  change priority too, and the judging has to say so.
- **How:** one daemon thread (`tools/stream/qos.py`, started by `planet_store_day.main`) walks this process's
  descendants every 3 s, every 0.1 s for 6 s after an engine's launcher starts (`engine_room.in_room` tells it);
  sets each the first time it sees it, after checking it was made no earlier than its parent (a reused parent pid
  is not ours: never set, not walked); keeps a handle so an ended process's CPU seconds can still be read.
  A real notes engine's java.exe was set 109 ms after it started (probe of 11-28, 0.1 s poll; 260 ms at 0.25 s).
- **Readings:** `logs/qos/<run>-procs.csv` (a row per process: ControlMask, StateMask, priority, error, ms after
  start), `logs/qos/<run>-cores.csv` and `W/days/<D>/cores.csv` (every 15 s: fast mean, slow mean, each CPU),
  `W/days/<D>/qos.json` (written after the day's `== day D done` line in `store_tail`, so a resumed day has it; mode, processes seen/set/failed for the day, core means), each engine's tree CPU seconds
  in `cpu.json` beside its log, read into `engines.json` as `"cpu s"`, `"qos"`, and per phase `"cpu s"`. The
  "engine over ... in N s" line names the engine (`(t1/f12)`, `(f12/old)`).
- **Never a stop:** every call caught; a failed set is a row with its error; the import itself is guarded in
  `planet_store_day`.
- **Judging:** per engine key and per step against the kept days, at least two days each way; slow cores show as
  more CPU seconds for the same work, and as the slow cores' share in cores.csv. Alternating within a day was not
  done (the watcher sets whole trees; a per-engine choice would leave the Python steps ambiguous).
