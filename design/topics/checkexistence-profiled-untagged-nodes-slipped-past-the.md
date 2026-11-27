## CheckExistence profiled: untagged nodes slipped past the fast reject (2026-11-07)

Direction 2 above. JFR (`settings=profile`) on europe-msk 2026-11-07, the day's slowest CheckExistence (Istanbul
36 s), run as the daily run does but without grid and parts. Script and recordings in `.scratch/prof-ce/`.

- **The feature lookup is not the cost.** `ScFeatures::getFeature` is about 4% of CheckExistence's samples. The lock
  around it was waited on for 14.6 s of thread time in the run, mostly by CheckShopExistence and AddPlaceName, not
  CheckExistence. Caching features per element would not help.
- **The cost was evaluating its filter on untagged nodes.** 74% of its samples sit in `AnyOf`/`AllOf.matches`, only
  5% in `TagMap.get`. AreaPass gives an untagged element `emptyMap()`, not a `TagMap`, and `KeyReject` let anything
  that is not a `TagMap` through. SC's own check for untagged elements did not stop them either: its table says
  `key ~ regex` may hold with no tags, so CheckExistence's whole tree (about 40 leaves) ran on every one of
  Istanbul's 7M untagged nodes, four times. The fix is one line in `KeyReject.mayMatch`: an element with no tags
  fails every clause. It is exact for the same reason as the rest of the fast reject.
- **Same counts.** europe-msk: snapshot and `quests.json` equal before and after, apart from `runSeconds`. Berlin
  2026-11-06 with grid and parts: snapshot and grid equal the published ones.
- **Speed**, one run each, back to back:

  | | before | after |
  |---|---|---|
  | CheckExistence, Istanbul | 36.5 s | 6.9 s |
  | CheckExistence, Moscow | 47.0 s | 15.8 s |
  | area pass Istanbul, Minsk, Moscow | 19.9, 5.6, 60.7 s | 18.4, 4.4, 51.0 s |
  | pass | 132.1 s | 117.0 s |
  | JVM CPU (JFR's CPU load, rough) | about 1,120 s | about 1,065 s |

  CheckExistence fell from 6.1% to 1.1% of samples. CPU fell by about that much, so few other quests were caught
  the same way. Unlike the kerbs, wall time moved too: Moscow's area pass was waiting on CheckExistence among others.
- **Next by the same profile: AddLevel and AddLevelThing, 22% of samples together** (Moscow 39-55 s each, which
  the log's slowest three hide in the sums above). Both start from `getMultiLevelMallGeometries()`, which asks for
  the geometry of every candidate (`LongIndex.get` is half their time), in every run. As with the kerbs: twins that
  share one result per map data, if the function reads no clock.
