## Planet history kept current with diffs: measured (2026-10-24)

- **It works.** `osmium apply-changes -H` takes the history file plus daily diffs
  (`replication/day/000/005/NNN.osc.gz`, sequence 5137 is the first after the 2026-10-05 dump; 5136 +
  days since 2026-10-05) and writes a new history file. Re-applying a diff changes nothing, and
  apply-changes sorts the diffs itself. Never use `merge-changes --simplify` on history: it keeps only
  the last version.
- **Always pass `-H`.** The store's file is named `.osm.pbf`, not `.osh.pbf`; without `-H` osmium exits
  0 and silently collapses the history (Ontario: 232.9M node versions to 184.7M).
- **The cost is the rewrite, not the diffs.** Ontario's 1.98 GB clip plus two diffs: 66 s, the same as a
  plain `osmium cat`; memory about 3.4 GB plus 0.85 GB per daily diff (a week is about 10 GB). For the
  163 GB planet that predicts about 1-1.5 h a week, plus about 1 h to clip the counted places' envelopes,
  and a week of diffs is 0.75 GB to download (1-2 minutes here).
- **Disk decides it.** The update cannot work in place: it needs a full second copy, about 165 GB free.
  C: has 150 GB. The history file also has a second hard link (`name-ru-repair\data\planet\`), so the
  old copy frees no space until both links go. A weekly `planet-latest.osm.pbf` download (about 85 GB,
  about 4 h) fits today, but the history then stays frozen at 2026-10-05.
- **What tips it:** whether a place first requested later (say 2027-06) must get monthly points from
  2026-11 on. If so the history has to stay current (weekly, or monthly plus a weekly planet). Disk is
  the owner's (see the owner's direction above).

**Spike result (2026-10-24, night).** Overture release 2026-10-21.0, read straight from S3 with DuckDB 2.0
(`tools/overture_pull.py RELEASE CC...`; Canada and Germany: 141,000 divisions in 39 s, 52,789 areas, 430 MB,
in 5 min; data in `data/overture/`, not committed; the measuring scripts in `.scratch/overture/`).

- **Places per subtype**, with a polygon / with an OSM relation as source:

  | | Canada | with polygon | OSM relation | Germany | with polygon | OSM relation |
  |---|---|---|---|---|---|---|
  | region | 13 | 13 | 13 | 16 | 16 | 16 |
  | county | 1,537 | 1,537 | 1,537 | 399 | 399 | 399 |
  | locality | 13,001 | 5,830 | 5,623 | 89,341 | 23,237 | 21,774 |
  | macrohood | 1,058 | 502 | 493 | 7,239 | 2,823 | 2,676 |
  | neighborhood | 6,623 | 4,022 | 3,632 | 14,293 | 9,327 | 8,540 |
  | microhood | 679 | 303 | 160 | 6,799 | 4,717 | 587 |

  Overture has no `localadmin` in either country. A place without a polygon is an OSM `place` node, so
  it can be named but not counted.
- **Our cities: 113 of 115 are found by their relation id**, every one with a polygon, as `locality`,
  `county` (Toronto, admin_level 6) or `region` (Berlin, Hamburg). The two misses show the link is not
  always the admin boundary: Laval's Overture locality cites relation 1438336, not our 3532125
  (admin_level 5), and Markham's cites a way (w1499781347), not relation 324213. The fallback is
  wikidata, then name plus containment, and a city keeps the relation it is counted on.
- **Neighbourhoods inside a city** (descendants in `hierarchies`, with a polygon): Toronto 176 of 446
  neighborhoods, 37 of 55 microhoods; Berlin 96 of 105 macrohoods (the Ortsteile), 55 of 364
  neighborhoods, 297 of 549 microhoods; Hamburg 102 of 106 macrohoods; Montreal 19 macrohoods, 16
  neighborhoods; Vancouver 22 macrohoods, 4 neighborhoods. With OSM only, a city gets the polygons
  OSM has, and Toronto has 176, not the city's 158 official ones.
- **The world:** 4.70M divisions in 272 countries, **1.08M with a polygon** (556k localities, 325k
  neighborhoods, 89k microhoods, 47k macrohoods, 39k counties, 22k localadmin, 3.9k regions). The most
  are Russia 144k, India 62k, US 60k, France 57k, Ireland 52k, Germany 41k, Brazil 40k, China 40k; India,
  China, Nigeria, Egypt, Pakistan and Bangladesh together 118k. Coverage there is better than the
  Wikidata city list suggested (DESIGN.md, "Planet coverage: what was measured").
- **The name layer's size.** Id, name, subtype, parent, OSM id, wikidata, bbox and population as
  compact JSON: Canada 22,912 places 3.8 MB (1.2 MB gzipped), Germany 118,088 places 19.1 MB (6.1 MB).
  About 160 bytes a place, so the 1.08M places with a polygon are about 175 MB raw: too much for
  `docs/` under the Pages cap, and too much for one download. **Proposal:** name only the places with a
  polygon (a point cannot be counted), shard by region (a file per country listing its regions, a file per
  region listing what is inside it), and keep the files out of `docs/` with the archive, or trim the
  record to id, name, parent and bbox (about half the size).
- **The owner chose it (2026-10-24, later that night):** the history file is kept current weekly with
  diffs, so a place requested later still gets monthly points without a gap; the owner is preparing the
  disk (about 165 GB free beyond today's files). The updater is `osm-extracts fetch planet-history`
  (only osm-extracts downloads into the store); sc-open-quests' weekly job slices and counts.
