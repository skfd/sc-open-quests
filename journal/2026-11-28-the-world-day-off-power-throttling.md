# The world day off power throttling (2026-11-28, from 00:15)

Asked by the owner through the osmium-windows-fast session (00:20: "go ahead and set it up"); brief in
`~/Code/osmium-windows-fast/journal/2026-11-28-sc-open-quests-throttling-brief.md`: a trial behind a switch, it
must not be able to stop a day, nothing may need the owner 00:00-07:00, ready for 11-28's 14:45 day only if safe.

- Built `tools/stream/qos.py` (bc7d5e680): the watcher, the switch, cpu.json per engine, cores.csv, qos.json.
  Design: [design/topics/the-world-day-off-power-throttling.md](../design/topics/the-world-day-off-power-throttling.md).
- The task `kk-SCOpenQuests-planetstore` has no `<Priority>` in its XML: Task Scheduler's default 7 is
  BELOW_NORMAL, so the day already runs below normal. `high` adds only the throttling opt-out.
- Probe on a real notes engine (f0 of world-1101, `.scratch/qos-probe/probe.py`, loop idle): rows for python.exe,
  cmd.exe, java.exe all `control 1, state 0, below normal` under `high`, `0, 0` under `default`; cpu.json names
  cmd.exe and java.exe, 5-6 s CPU in a 1.6-2.9 s engine. java.exe set 260 ms after its start at a 0.25 s poll,
  109 ms at 0.1 s (kept).
- A review before committing caught the pid-reuse check running after the set (an unrelated process with a stale
  parent pid would have been set and walked); fixed, with a test.
- Schedule in `data/qos.txt`: 11-28 `default` (HANDOFF Next 2 wants 11-28 as the clean day to judge the 11-26
  speed-ups, and the trial needs baseline days with CPU seconds anyway), 11-29 and 11-30 `high`, 12-01 `default`
  (the cutover day as usual), bare `default` after.
- Full suite 473 passed, 1 skipped (00:25).
