## AddHousenumber: one removeAll, not one per area (2026-11-08)

Next by the level session. London's area pass was 67.9 s in the 11-08 daily run, AddHousenumber alone 57.6 s of
it, one run (no age test). Starting it first in the queue would have saved about 5 s, so it was profiled first:
JFR on London alone, 11-08 clip (`.scratch/prof-hn/`).

- **77% of its samples were one line of step 5:** `buildings.removeAll(buildingsInArea)`, once for every area
  with an address that holds a candidate building. Each call scans every remaining candidate and hashes the
  whole `Way` (its node list, boxed, and its tags) to ask the set. The twin already skipped the call when the
  set was empty; London still has enough non-empty ones.
- **The change** (`FastAddHousenumber.kt`): gather the buildings of every area into one set by identity, and
  remove them once at the end. Exact: an area's `buildingsInArea` comes from `buildingPositions` and
  `buildingsByCenterPosition`, which step 5 never changes, and its elements are the very objects in
  `buildings`, so removing the union once leaves the same list in the same order.
- **The rest** (23%, about 13 s without JFR) is step 5's sort of every area by measured size and the
  address-node consume that follows, which depends on that order. Left alone: AddHousenumber is no longer among
  London's slowest three.
- **Speed**, europe-west 11-08, the daily run (old engine) against the new one with the same flags (grid and
  parts), and once without them:

  | | old (daily run) | new | new, no grid |
  |---|---|---|---|
  | London area pass | 67.9 s | 32.8 s | 31.1 s |
  | AddHousenumber, London | 57.6 s | not among the slowest three (third: 24.6 s) | same (25.2 s) |
  | pass | 124.4 s | 96.4 s | 91.4 s |

  London's slowest three now: AddKerbHeight 27.9 s, AddTactilePavingKerb 24.7 s, AddChargingStationSocket 24.6 s,
  each a sum of four runs; the shared kerb search, 16.4 s, is logged apart.
- **Same counts.** The new snapshot equals the published 11-08 one apart from `engineCommit`; its grid equals
  `data/grid/europe-west/2026-11-08.json.gz` byte for byte.
- **AddChargingStationSocket, read off the same London profile: nothing to fix in it.** It is an age quest
  (four runs), and each run filters every node of the map data twice (charge points, then its filter): 81% of
  its samples are `ElementFilterExpression.matches`, 47% the fast reject itself. It is a scan, not a pathology,
  and it is not a city's floor: in Moscow and London the kerb twins lead, and the log's figures are sums of
  four runs that go on different threads.
- **Next, proposed, not built:** candidates by key once per map data. Most area quests' filters require a key
  (`amenity`, `building`, `highway`), and every run of every quest scans the whole map data to find the few
  elements that hold it. An index from key to elements per map data, built once, would let `mapData.filter`
  walk only the elements holding a clause's required key, in map data order (SC's results depend on order),
  for every quest at once. Worth a profile of the whole area pass's CPU first: London's area pass is 25 s of
  quests on 24 threads now, so it may be CPU-bound rather than held by one run.
- `.scratch/prof-hn/` (scripts, recording, outputs) can be deleted.
- **verifyFast on London passed (2026-11-08, late):** the fast twins, the new AddHousenumber included, matched
  their ports on all 8 map data runs. It took 9 h of wall time: SC's AddMaxHeight port (all against all) logged
  32,921 s on one thread but used only about 6,400 s of CPU, close to the 6,710 s the last London verify took in
  all. The rest is the laptop sleeping or throttling the JVM while the owner was away, not the port.
