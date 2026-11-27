## AddMaxHeight and the queue: built (2026-11-08, late)

The first two proposals above, at the owner's word. Same counts: europe-west and europe-msk (all six cities)
give snapshots equal to the published 11-08 ones. europe-west with the daily run's grid and parts gives a
snapshot equal as text (parts included) and a grid equal byte for byte. `-Dopenquests.verifyFast=true` on
Dublin and Lisboa (16 map data runs, 144 s) found every twin equal to its port, the new AddMaxHeight
included. 71 engine tests pass. All timings are clean runs with the task trace on, the machine otherwise idle.

- **AddMaxHeight** (`FastAddMaxHeight.kt`): the tag filter before the node id sets, as proposed. That alone
  took London's run from 14.1 to 11.8 s of CPU, not the 42% the profile suggested. A second JFR run, by source
  line, put about half of what was left in the bridge loop: for every road and bridge pair it built the
  bridge's node set again (`toSet()`, boxed), looked up its geometry and parsed its layer. Each bridge now
  carries its geometry, layer and node set, worked out once. The bounds test that SC's `intersects` starts with
  also moved ahead of the node set test. All of these are pure tests joined by `&&`, so the result is the same.
  London's run: 17.2 s wall and 14.1 s CPU before, 12.7 s and 10.5 s after.
- **The queue** (`AreaPass.countCity`, `parallelWhenReady` replacing `parallelInOrder`). The shared searches
  start first, then the runs in `LONG_RUNS` (AddHousenumber, AddLevelThing, AddMaxHeight), then the age quests'
  runs, then the rest. A free thread takes the first run that is *ready*: one that needs a shared search is
  ready once that search is done. The kerb runs no longer hold threads idle (0.1 s each instead of 8 s
  waiting), and AddLevelThing starts once the level points are in (0.5-2.6 s) instead of after every other run
  (8-12 s). Order cannot change counts: each run is independent.
- **Run phase**, before tonight, then after each step:

  | city | before | AddMaxHeight | + queue |
  |---|---|---|---|
  | London | 26.7 s | 24.4 s | 24.0 s |
  | Moscow | 20.7 s | | 18.1 s |
  | Istanbul | 10.9 s | | 10.8 s |
  | Minsk | 4.6 s | | 3.7 s |

  London's last two columns are not like for like: London alone, then London after Dublin and Lisboa in one
  JVM, so its 0.4 s is noise. Moscow's is the like-for-like gain from the queue.
  Area pass with map data: London 35.7 s to 31.1, Moscow 26.6 to 23.1, Istanbul 15.3 to 14.4, Minsk 6.0 to 4.9;
  the europe-msk pass 93.8 s to 87.7.
- **What is left: the long runs themselves.** Starting them at 0 means they run while all 24 threads are busy,
  at about half a core each. London's AddHousenumber now takes 23.4 s of wall time for 18.6 s of CPU, against
  20.7 s for 17.2 s when it started at 6 s. The floor is the slowest of AddHousenumber (London 18.6 s CPU),
  AddLevelThing (14.0 s) and AddMaxHeight (11.6 s), running alongside everything else. A shorter pass needs one
  of these faster, or split across threads, not reordered. A world run, where two engines keep the CPU full,
  gains nothing from the queue; candidates by key (proposal 3) is still the saving for that.
- `LONG_RUNS` is a fixed list from these traces. If another quest turns out long in some city, the trace
  (`-Dopenquests.taskTrace`) shows it as a run still going alone at the end.
