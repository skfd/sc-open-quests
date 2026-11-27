## The level quests: a grid per mall, and one ordered queue (2026-11-07)

Next by the CheckExistence profile. AddLevel and AddLevelThing have no age test, so each runs once; what made
them slow was SC's `getMultiLevelMallGeometries()` (`LevelUtils.kt`): for every mall it walks every element
with a level tag and looks up its geometry again. Moscow has thousands of stations (`public_transport =
station`) and many elements with a level tag. `openquests/fast/FastLevel.kt`:

- **The level points once per map data** (`LEVEL_POINTS`, logged `(shared) level points`, about 2 s in Moscow):
  each element with a level tag, its center and level, in a 0.002-degree grid. A mall looks only at the points
  its bounds contain, which are the only ones SC's loop gets past its own bounds check; the answer (two
  different levels inside) does not depend on the order. The shops and things inside the malls come from a
  grid the same way, and SC's `isPlace()`/`isThing()` is asked only of a node inside a mall, in SC's order.
  Mall filters copied verbatim; a test pins `LevelUtils.kt` too (`helperSha256`), since the twins copy it.
- **One ordered queue.** With the level twins among the runs that need a shared search, Istanbul's area pass
  got 4 s slower: those runs started only after every other run had finished. `parallelInOrder` starts a
  city's runs strictly in order from one queue: the shared searches, the runs that need none (age quests
  first, which `parallelMap`'s range split had not kept), then the runs that need a search, once all others
  have started.
- **Same counts.** europe-msk 2026-11-07: snapshot and `quests.json` equal in all seven runs. Berlin
  (2026-11-06) and europe-west (2026-11-07) with grid and parts equal the kerb session's outputs, which equal the
  published ones. `-Dopenquests.verifyFast=true` passed on Berlin (8 map data runs, 25 min) and europe-msk (22,
  87 min). 71 engine tests pass, SnapshotReproductionTest included.
- **Speed**, europe-msk, old engine (22a2f470) and new alternating; another project's job used about one core
  throughout:

  | engine | Moscow area pass | Istanbul area pass | pass |
  |---|---|---|---|
  | old | 56.3 s, 67.0 s | 23.1 s, 21.7 s | 129.3 s, 138.8 s |
  | level twins, old two phases | 29.2 s, 29.3 s | 25.6 s, 27.3 s | 105.1 s, 109.6 s |
  | level twins, one queue | 27.4 s, 23.8 s | 23.7 s, 23.8 s | 102.4 s, 97.6 s |

  Old AddLevelThing and AddLevel in Moscow: 51-54 s and 43-49 s. New, neither is among the city's slowest three
  (the third was 13 s). Moscow's slowest are now AddChargingStationSocket, CheckExistence and AddHousenumber,
  13-17 s each. **London is unchanged** (78.9 s against 78.6 s): AddHousenumber's one long run still sets its floor.
- **Not run:** `--area-unit tiles` (there the first level twin of a tile gathers the points and the other
  reuses them). `.scratch/prof-level/` (scripts, logs, outputs) can be deleted.
- **Next:** AddHousenumber, the floor in London; now that the queue keeps its order, starting it first is
  a cheap test. AddChargingStationSocket leads Istanbul and Moscow.
