## Neighbourhood statistics: what exists, and the questions put (2026-11-10, evening; nothing built)

- **The data:** 4,214 parts in 81 cities (no parts in the four `europe-*` regions). The archive carries
  per-part, per-quest `open` at resurvey x1 since 2026-10-28 (10 dated snapshots by 11-08; 11-04
  missing). No aged split, no area, zero counts left out. A part page today shows only the newest
  count per quest. Toronto over 10-28..11-08: median part total 8,746, median change 9, largest 1,353.
- **The archive need not be published for this.** The card generator is a local `run.py` step and can
  read `data/archive/` directly; the widget wants its own small cacheable file. Only the page needs
  bytes over the wire, so the decision is which derived series file to publish, not how to publish
  the archive.
- **Measured shapes (Toronto, 10 days):** one part's per-quest series 4.2 KB raw, 1.0 KB gzip; all of
  Toronto's parts in one file 932 KB raw, 101 KB gzip (about 10 KB gzip more each day); totals only
  (no per-quest split) 4.9 KB gzip, but then the trend ignores the quest ticks that `partTotal` applies to
  the table. Files against the 20,000 cap, with previews at about 13,560: per-part files +4,214
  (about 17,800); per-city files +81; region-month bundles of the raw archive +16 a month. The real
  format must tell 0 apart from "not counted" (a missing day, a part added later).
- **Aged split for parts:** cheap in the engine (the mask is at hand where `countParts` is called; a
  second array next to `partOpen`). Backfilling it to 10-28 needs those days' extracts, and the
  store keeps 14 days: 10-27 and 10-28 are still in `~/Code/.osm-data/<region>/` on 11-10 and go
  at the next fetch or two unless pinned (`pins.json`).
- **Longer history:** the regions' `.osh` history files (monthly points since 2017 for cities) could
  give parts monthly points too. That is a recount of the monthly snapshots with parts on, not measured.
- Questions put to the owner: what a part page adds first; how far back the series goes; whether
  the trend follows the quest ticks; whether the raw archive is published at all.
- **Owner, 2026-11-10 late evening: "assume design for final product where we have full world data".**
  The design is in DESIGN.md, "Place statistics for the whole world: the final product". In short: one
  page for every level; place data on an R2 public bucket on its own subdomain; three cacheable
  requests per page. That replaces the per-part-files idea above. Its open questions are the
  owner's: R2 or static assets, the per-km² divisor, freshness.
