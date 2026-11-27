## The cell test: passed (2026-11-06)

Do cells change the numbers? Tiles as the engine's "cities", each real city a part inside every tile it
touches, on the same extract, notes clip and quests file as each region's archived snapshot. No engine
patch: a city's membership is by the element's centre in both passes, so nothing crosses twice and city
numbers do not lose border elements. Harness and results in `.scratch/world-spike/cell-test/` (`REPORT.txt`).

| cell | cities | every quest | app-default total | over 0.1% | worst city (default) |
|---|---|---|---|---|---|
| z10 | all 147 | 39,695,236 to 39,695,249 | 11,367,386 to 11,367,397 | 0 | Orangeville +0.0124% |
| z12 | 115 (not Europe; out of time) | 20,436,529 to 20,436,513 | 5,788,935 to 5,788,920 | 0 | Saguenay -0.0405% |

- **The owner's bar of 0.1% holds at both sizes.** 114 of the 147 cities are equal in every quest at z10.
- **What moves:** AddHousenumber (44 quests in all at z10, 34 at z12; a building must lie wholly inside the map
  data), then AddMaxHeight and AddBarrierOnPath by 3 each.
- **The harness can see an edge:** Bremen as bare z16 tiles with no ring is -0.66%. The 1 km ring removes that.
- **The four filter quests that moved are the test's, explained 2026-11-07.** Each pair is one way whose centre
  lies exactly on the city boundary: Burlington's way 401631538 (0.0 m from relation 2407513), Athens' way
  901806046. The even-odd test gives a point on an edge either answer depending on the order of the
  segment's ends, and the test's stitched rings reverse some of them (`.scratch/cleanup/pip.py` replays
  `Polygon.contains` on both). For the world count it is real all the same: roads often are the boundary, so a
  centre on the edge between two places can land in both or neither. Rare, and worth one rule (half-open edges)
  in the place lookup.
- **Cost:** z10 passes 3,727 s against 2,525 s whole-city, most of the gap one cell: Paris's AddAddressStreet
  1,434 s against 582 s, on a machine shared with the re-cut at the end. It wants a fast twin first. z12 was 3 times
  slower (Alberta 4,721 mostly empty cells): empty tiles are expensive as cities, so cells should be sized by
  nodes, not by zoom.
- **Not tested:** a ring other than 1 km; a file cut to a region's edge (every run read the whole extract);
  land outside counted cities; country rules and time zone by position.
