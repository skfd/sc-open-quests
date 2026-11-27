## Kerbs once per map data: built (2026-11-07)

Direction 1 above. `openquests/fast/FastKerbs.kt`: twins of AddKerbHeight and AddTactilePavingKerb that take the
kerb nodes from one call of SC's own `findAllKerbNodes()` per map data (`PerMapData`) instead of a search in each
of their four runs. The quests' own filters are copied verbatim, and KerbUtil is called, not copied. In a city
AreaPass runs the search next to the quests that need none and the eight kerb runs after it, so no thread waits
for it; the log names it `(shared) kerb nodes` (London 13-16 s, Berlin 5-8 s, once).

- **Same counts.** London (europe-west 2026-11-07) and Berlin (2026-11-06), run as the 11-07 daily run did, give
  snapshots equal to the published ones in every field apart from run time and commit.
  `-Dopenquests.verifyFast=true` passed on Berlin (6 map data runs, 29 min) and on europe-west (Dublin, Lisboa,
  London: 18 runs, 1 h 55 min; London alone 6,710 s, because the ports' all-against-all code runs too).
  verifyFast compares only the asOf run with the port. The other three runs are the same by argument: the search
  reads no clock, and the filter applied to it is SC's own, run under each clock as before.
- **CPU: 9% less on europe-west, wall time unchanged.** Old engine (58506f45) and new alternating, idle machine,
  process CPU sampled every 0.5 s:

  | engine | CPU | London area pass | pass |
  |---|---|---|---|
  | old | 1,492 s, 1,496 s | 85.4 s, 83.3 s | 141.1 s, 138.2 s |
  | new | 1,358 s, 1,361 s | 79.7 s, 84.0 s | 135.9 s, 138.3 s |

  Berlin alone (two runs each): area pass 27.5 s both old runs, 26.7 and 27.7 s new.
- **The guess of 1.2-1.4 times on the area pass was wrong for one engine.** A city's area pass lasts as long as its
  longest single task, not its total work: London waits on AddHousenumber, one run of about 62 s (no age test, so
  one task), and the pass cannot end before about 70 s however much else is saved. The saving shows only where CPU is
  the limit: two engines at once in a world run (not measured).
- **What would shorten London's area pass:** AddHousenumber's one 62 s task, already a twin. It comes after every
  age quest's runs in the task order (age quests first); started first it would at least not start late, and only a
  faster AddHousenumber lowers the floor. CheckExistence is about 62 s over its four runs, about 16 s each: it costs
  CPU, but it does not set the floor.
- **Not shown:** whether running the search ahead of the kerb runs gains anything over letting seven threads wait
  for it; with AddHousenumber setting the floor, these runs cannot tell. `--area-unit tiles` was not run (there the
  first kerb run of a tile searches and the other seven reuse it).
