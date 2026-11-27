## Optimisation directions after the speed-up (2026-11-07)

Read off the 11-07 daily run (`logs/scheduler.log`, engine with the speed-up and the AddAddressStreet twin): 16
passes 1,100 s, against 2,468 s on 11-06. The log names each city's three slowest quests, so these sums are a floor:

| quest | summed over cities | worst |
|---|---|---|
| CheckExistence | 866 s | Istanbul 36 s |
| AddKerbHeight | 768 s | London 67 s |
| AddTactilePavingKerb | 725 s | London 70 s |
| AddHousenumber | 80 s | London 55 s |

Proposed, none built, in order:
1. **Kerbs once per map data.** AddKerbHeight and AddTactilePavingKerb both start from SC's
   `findAllKerbNodes()` (`sc/.../osm/kerb/KerbUtil.kt`), which reads no clock, and both are age quests run four
   times: eight identical searches per map data. Twins that share one result per map data give the same
   counts. Guess 1.2-1.4 times on the area pass; check with verifyFast on Berlin and London.
2. **Profile CheckExistence** (an age quest, four runs). If its feature lookup (`ScFeatures::getFeature`) is the
   cost, cache it per element across the four runs.
3. **One walk for the age quests, four evaluations** ("A rewrite in a systems language", not done there).
4. **For a world run:** two engines, largest file first, many cells in one JVM (about 6 s start-up a run), cells
   sized by nodes (z12 Alberta, 4,721 mostly empty cells, was 3 times slower).
5. **Owner's call, less work:** world places at resurvey x1 only, counted cities keep the 0.5 and 2 variants;
   and a daily world that recounts only cells a diff touched plus cells where a quest's check date ages out that
   day (computable ahead), which needs per-cell results kept.
6. **Not worth it now:** a rewrite, a native pbf reader (17% of CPU, at most 1.2 times), ParallelGC, a third engine.
   To measure, not code: whether this laptop holds speed through a 6-hour run.
