## Germany as cells: the world prototype (2026-11-09, night)

DESIGN "The whole world", items 1-2, on one country. `tools/world_cells.py`, output in `.scratch/world-de/`
(gitignored), Geofabrik `germany-2026-11-07` (4.6 GB, 442.6M nodes). Nothing published, no pipeline change.

- **Steps and costs:** `nodegrid` (new engine command, nodes per 0.05° square) 36 s; Overture places 109 s;
  cells cut k-d by node count into 4 files of about 110M nodes and 34 cells of 7-15M; one `osmium extract`
  (smart, 2 km padding, the input's replication header copied: the engine refuses a file without it) 475 s;
  notes clip 362 s; count with two engines at once (30 GB heap each) **1,007 s**, about 2.3 s per million
  nodes, each file 475-532 s, peak heap 34-38 GB. The places: 40,520 Overture divisions of Germany with an
  area and an OSM relation or way as their own source (add_parts.py's rule), land area, 495 MB of GeoJSON,
  each a part of every cell its bbox meets (9-13k part entries a file).
- **The check passes:** the five counted German cities, their own OSM polygons as parts, against a whole-city
  count of the same file, notes clip and quests: Berlin, Bremen and München differ by one AddHousenumber each
  (at most 0.002%), Hamburg and Bremerhaven not at all. As Overture places they are within 0.015% (Hamburg's
  land polygon). Germany: 20.09M open quests in the app's defaults, 75.7M of every kind; the 16 states sum
  to it within 0.007% (their borders overlap). 39,446 places have a number; the rest are squares and plazas
  with nothing open.
- **Found: the summit quests.** AddSummitRegister and AddSummitCross asked every peak of every hiking path,
  all against all: 1,114 s summed in one Alpine cell, f1 1,164 s of the first run's 1,433. Now a fast twin
  (`FastSummit.kt`, segments gridded once per map data, SC's own distanceToArc asked of nearby ones): the
  same snapshots in all four files, SummitTest against SC's loop, 74 engine tests. The slowest cell's area
  pass is now 62 s.
- **Not exercised:** country rules and time zone by position (one country); a file cut at Germany's border
  has no ring beyond it (as the baseline); stray nodes in the extract stretch the box to lon -20..28, so edge
  cells are large and the notes clip holds 2.09M notes (955 MB): a world run clips notes per file. Publishing
  and R2 untouched; `.scratch/world-de/` (about 7 GB with the cut) can be deleted.
