## Candidates by key: built (2026-11-08, late)

Proposal 3 of "The whole area pass profiled", at the owner's word. 30% of the area pass's CPU was the fast
reject saying no, and much of the filter tree's share was the same walk: every scan of the map data asked every
element "is this you?". Now a scan walks only the elements that hold a key its filter cannot match without.

- **How** (`engine/src/main/kotlin/openquests/KeyIndex.kt`; engine/README.md, under `fastreject`). Each map
  data keeps a `KeyIndex` per list (nodes, ways, relations): tag key to the ascending positions of the elements
  holding it, built the first time a quest asks. `mapData.candidates(list, expr)` takes `expr`'s clauses (the
  key sets `KeyReject` already works out: an element `expr` matches holds a key of every clause), picks the
  clause with the fewest elements, and returns those elements in `list`'s order. The caller's predicate still
  runs on each one, so `candidates(list, f).filter { f.matches(it) && ... }` equals `list.filter { ... }`: the
  elements left out could not match, and the order and any side effects in the predicate are unchanged. An
  expression with no clause, or any other map data, gives the whole list.
- **Where:** `port_area_quests.py` rewrites the ports' scans by one regex, `CANDIDATES`, the only change it
  makes to their kept code, for 40 regenerated ports. The rewrite catches `mapData.nodes`, `ways` or `relations`
  followed by `.filter { f.matches(it)` (also after `.asSequence()`, or after an `it.id in set &&`). Rerunning the
  script before the change reproduced every port exactly, so the diff is the rewrite alone. The fast twins call it
  directly, including a whole-map-data `candidates(expr)` (nodes, then ways, then relations, the map data's own
  iteration order) for AddHousenumber's buildings, AddIsAmenityIndoor, AddAddressStreet and FastLevel's
  `mapData.filter(expr)`. Not touched: the hand-ported custom quests whose `getApplicableElements` is
  `mapData.filter { isApplicableTo(it) }`, and SC's own `MapData.filter(expr)` (an SC patch would be needed).
- **Same counts.** europe-west and europe-msk (six cities) equal the published 11-08 snapshots. europe-west with
  grid and parts: snapshot equal as text, grid equal byte for byte. Bremen and Bremerhaven (Geofabrik, 11-07)
  equal their published snapshot. verifyFast on Dublin and Lisboa passed (16 runs), though both sides now use
  `candidates`, so the snapshots from the older engine are the check that matters here. A new `KeyIndexTest`
  runs every quest filter of v64.1 (and a few edge cases) over random nodes, ways and relations, a third untagged,
  and checks that `candidates(list, f).filter(f::matches)` equals `list.filter(f::matches)`, order included, per
  list and for the whole map data. 73 engine tests pass. Peak heap is unchanged within noise (europe-west 30.9 to
  28.1 GB, europe-msk 27.4 to 29.3). Not run: `--area-unit tiles`, where each tile builds its own index.
- **Run CPU down by a quarter to a third**, run phase down less (the long runs still set it):

  | city | run CPU before | after | run phase before | after |
  |---|---|---|---|---|
  | London | 241 s | 162 s | 24.0 s | 19.6 s |
  | Moscow | 161 s | 121 s | 18.1 s | 17.2 s |
  | Istanbul | 91 s | 67 s | 10.8 s | 9.7 s |
  | Minsk | 40 s | 27 s | 3.7 s | 3.3 s |

  Area pass with map data: London 31.1 s to 26.2, Moscow 23.1 to 22.2; the europe-west pass 94.5 s to 79.7, the
  europe-msk pass 87.7 to 86.3. One run each, so a second or two either way is noise.
- **For a world run**, where two engines keep the CPU full, the run CPU is what counts: about 1.3-1.5 times on
  the area pass, as proposed. Not measured with two engines.
- **Left:** the hand-ported custom quests' per-element scans (CheckShopExistence, AddPlaceName, AddOpeningHours
  and others: `mapData.filter { isApplicableTo(it) }`), which would need their first filter named; and the long
  runs' own work. A JFR run of the new engine would show what leads now.
