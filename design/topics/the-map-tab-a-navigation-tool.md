## The Map tab: a navigation tool (2026-11-27; owner: "map should be a tool to find a region down to some level of accuracy")

**Status: decided, not built; to be built after the 12-01 switch to Overture 11-18.0.** Replaces the job of "The
coverage map" (2026-11-06): since release 1 every place is counted, so "where we count" tells nothing apart.

- **The job:** find a place by where it is. A tap (or zoom) on a spot gives the places that hold it, as a chain
  (Canada › Ontario › Toronto), each a link to its page. No statistics on the map: shading by open quests is parked
  (BACKLOG.md, "Statistics on a map"; owner: "shaded design will take a step back").
- **Real outlines, not bounding boxes** (owner, 10:45). The name layer's boxes overlap, so a tap near a border would list
  the neighbours and draw rectangles. The outlines are Overture's division areas, built into **one PMTiles file on
  sc-data** (read with range requests, no tile server), ids only, so the numbers never go stale in it. Rebuilt at
  each Overture switch, which is why it waits for 12-01: built before, it would be rebuilt four days later.
- **Down to cities first** (owner): countries, regions, counties, localities. Neighbourhoods and smaller later.
  Each level appears at the zooms where it is legible; hover names and highlights a place.
- **The map library moves to MapLibre** (Leaflet does not read vector tiles well); the basemap stays OSM's.
- **Not now:** a "Near me" button (owner: "Not now"); a reverse-geocoding service (an outside dependency handed readers'
  positions, and OSM boundaries do not map one to one onto Overture places).
- **Left as it is until then** (owner: "Wait for redesign"): the tab's sentence "The rest of the world is not counted
  yet; find a place to ask for it", which has been false since release 1.

**Weight, measured 2026-11-27 (gzip -9):** today's tab loads Leaflet 1.9.4 (42 KB + 4 KB CSS) and `coverage.json`
(151 KB), about 197 KB; MapLibre 6.19.0 is 276 KB + 10 KB CSS and `pmtiles.js` 8 KB, about 294 KB, plus the outline tiles
in view (estimated, not measured: tens of KB at world zoom, 100-400 KB for a dense city view) and the PMTiles directory
(about 16 KB, then leaf directories). Only the Map tab loads any of it; OSM's raster tiles are the same in both. To check
before building: Cloudflare caches a file only up to a size limit (512 MB on the free plan, as remembered), so if the
PMTiles file is bigger, every range read is an R2 read.

Open, for when it is built: the tile build's tool (tippecanoe in Docker, as osmium runs, or DuckDB spatial's MVT), the
file's size at city depth, and whether the 147 cities' own OSM outlines (`coverage.json`) stay beside Overture's.
[journal/2026-11-27-the-map-tab-redesign.md](../../journal/2026-11-27-the-map-tab-redesign.md)
