## Current clips in osm-extracts (2026-10-31)

**Real diffs, measured.** Daily planet diffs 5161 and 5162 (117 and 108 MB, the whole world)
applied to Berlin's replay clip of 2026-10-29 (146 MB): `apply-changes` (without `-H`) 31-105 s at
about 0.85 GB peak per diff (1.4 GB for both at once); the result 182 MB; the `-s smart` re-cut back
to the envelope 20-101 s at about 4 GB peak, giving a 138 MB clip with about 3,000 more nodes a day
(the smaller file is just compression; objects were counted). `check-refs`: no nodes in ways
missing. The spread in seconds is machine load. So a day costs a few minutes, and memory follows
the clip's size, not the diff's.

**The design**, which an agent builds in osm-extracts:
- **A clip is a store folder with a `clip.json`:** its polygon (GeoJSON, copied into the folder),
  the history file it was cut from, and the last diff applied. `osm_extracts.py clip <name>
  --polygon FILE` registers it. `fetch <name>` sees `clip.json` and brings the clip up to date. It
  never downloads a file of its own.
- **The output follows the store's conventions:** `<name>-YYYY-MM-DD.osm.pbf`, dated by its
  replication timestamp, with a meta (sha256, replication timestamp and sequence, `check-refs`
  result), `latest.json`, prune. Both replication headers are written into the file, because the
  engine refuses a file without them. sc-open-quests counts a clip like a Geofabrik extract
  (`"extract": "<name>"` in `config/regions.json`), with no new code path.
- **Diffs:** `fetch planet-diffs` downloads every daily diff after the history file into
  `planet/diffs/`, which the monthly rewrite already reads. A clip fetch takes any diff it lacks the
  same way and never deletes one. The rewrite deletes a diff only once every clip is past it.
- **The monthly re-cut** (`recut`): one planet pass for all clips, each cut to its polygon's
  bounding box padded 20 km. Each cut is kept as `<name>-history-YYMMDD.osh.pbf`, which also gives the
  clip's monthly points since 2017, so the 3.2 h pass is paid once a month, not twice. A slice at the
  history file's timestamp is then cut to the polygon with `-s smart`, and diffs are applied from
  there. A daily fetch never re-cuts. It applies diffs, re-downloading any that are gone (the planet
  site keeps them all).
- **The `"cadence": "weekly"` key becomes unused:** a planet-counted region is daily from its clip.
  Left in place until the first clip region runs.

**Built (osm-extracts 5c898c2, 2026-10-31):** `fetch planet-diffs`, `clip NAME --polygon`, `recut`,
`fetch NAME` for a clip, and a rule that the monthly rewrite keeps every diff a clip still needs
(the osm-extracts README). Tested on a Bremen clip from the replay's history cut: the recut equals the
replay's cut object for object (4,257,302 same, 0 different); the fetch applied the real diffs
5161-5162 in about 2 minutes, with no nodes in ways missing. Two changes from the plan:
- **History cuts use `-s complete_ways`.** osmium 1.18 does not support `-s simple` on history files.
- **A planet pass holds about 4 GB per clip** (8.1 GB for one, 12.1 GB for two). So a pass takes at
  most 7 clips in docker's 43 GB, and each further group is another 3-hour read of the planet.
  **So cities are not one clip each:** one clip's polygon holds every counted city's padded box, a
  MultiPolygon, and the regions of `config/regions.json` share it (`"extract"`), one region per time
  zone as now. One clip, one pass a month, however many cities.
