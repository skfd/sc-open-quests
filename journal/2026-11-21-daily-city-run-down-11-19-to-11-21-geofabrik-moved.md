## Daily city run: down 11-19 to 11-21, Geofabrik moved regions (fixed 2026-11-21, 13:10)

- **The 12:15 run failed three days in a row** at its download step (11-19 Quebec, 11-20 and 11-21 Ontario), so
  the pilot cities' newest count is 11-18 and nothing was pushed since 11-19. Geofabrik moved the Canadian
  provinces and Berlin, Hamburg and Bremen into folders of their own (`north-america/canada/ontario/ontario-latest.osm.pbf`);
  the old URLs redirect to a 404.
- **Fixed in `../osm-extracts`** (its REGIONS table; and `fetch` now answers a Geofabrik 404 by asking
  `index-v1-nogeom.json` where the region is and warns that REGIONS is stale). The run was restarted by hand
  11-21 13:10; the missed days 11-19 and 11-20 are not backfilled (the extracts are only today's).
