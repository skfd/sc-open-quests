## World vs the daily run's cities: they agree (2026-11-19, late evening; side session)

`tools/world_compare.py` (read-only, ~15 s) held the world's `osm-<city>` counts and each city's name-layer place
against the published snapshots for 11-02 to 11-06; report in `.scratch/world-compare/report.md` (verdict on top,
from `findings.md`). Aligned on the clock (Europe's snapshot D = world D; Canada/Germany's D ~21:21Z = world D+1),
473 pairs: median 0.000%, p90 0.003%, +2,591 of 138.3 M, 289 exact. Gaps: 11-02 Europe was SC v64.0 (+0.6%,
AddAcceptsCards); 2.6 h of edits for Canada/Germany (Sarnia 11-05 +2.1%, 289 buildings); notes off by 1-11 in 5
pairs. Overture places differ from the OSM outlines (Bratislava -13%, Halifax -2.4%, Cape Breton -2.2%), so
counted cities keep `osm-<city>`. **The world can stand in for the daily run's numbers** once the owner picks a
clock (midnight UTC, or cut the world at the extract time). Rerun after 11-07 lands for 11-06's Canadian cities. `--measure agedOnly` (11-20, `report-aged.md`): 434 of 473 exact,
net +13 on 4.2 M. **Rerun 11-21 for 11-02 to 11-13** (`.scratch/world-compare/to-1113/`, the first report left as
it was): 1,419 aligned pairs, median 0.000%, p90 0.004%, 850 exact, the worst still Sarnia 11-05; days 11-07 to
11-13 each within ±0.003% summed; `agedOnly` 1,284 of 1,419 exact. No Canadian snapshot for 11-04 and 11-09. DESIGN.md now says counted cities take `osm-<city>`, never the Overture place.
**Clock decided (owner, 11-20): midnight UTC**, the world's own; recorded in DESIGN.md next to that rule. Nothing
changes in the daily run until the world replaces it.
