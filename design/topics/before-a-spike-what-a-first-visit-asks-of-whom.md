## Before a spike: what a first visit asks of whom (2026-11-10)

The owner's goal is that the site survives being posted. Three things were done on main, and the
third parties were looked up; nothing here touches the engine or the Worker.

- **No CDN.** uPlot 1.6.31 and Leaflet 1.9.4 are served from `docs/vendor/` (the npm `dist` files,
  byte-equal to what jsdelivr served: the SRI hashes the page pinned match, `docs/vendor/README.md`).
  jsdelivr states no limits, so this removes a dependency, not a known cap. On today's Worker the two
  uPlot files are two more requests of a first view (71 to 73) at `max-age=300`; as static assets
  they are free.
- **`cities.json` is 8 KB gzipped, from 124.** `trendAll` (59 KB) was read by nothing and is gone.
  Each city's `trend` (57 KB) is only Compare's sparkline column, so it moved to `data/trends.json`,
  which the page asks for when Compare first opens. A page reading older data with `trend` in
  `cities.json` still draws the column.
- **Checked headless on the real data, from a local server only:** Toronto, Compare (147 sparklines)
  and Map load with no page errors and no failed request; the only other hosts asked are `gc.zgo.at`
  and, on Map, `tile.openstreetmap.org`. Not yet served by the Worker or by Pages: a hand sync to the
  live bucket was refused to Claude (a production deploy), so the 12:15 run of 11-11 is the first.
  Pages builds `legacy` with `docs/.nojekyll`, so `vendor/` is served as it is. The vendored bytes
  survive git (a checkout's `leaflet.js` has the pinned hash).
- **The archive has a second copy.** `tools/archive_backup.py` copies `data/archive/` to the private
  R2 bucket `sc-open-quests-archive` under `archive/`: 2,161 files, 467 MiB, 79 s the first time,
  checked equal by checksum. It never deletes, and a file a rerun rewrote keeps its old version under
  `replaced/<date>/`, so it guards against a dead disk, a wrong delete and a bad rerun. `run.py
  update` and `planet` run it last, after the site sync; a failure is logged "archive backup FAILED"
  and the run goes on. The per-region `quests.json` files change every count, about 1.6 MB a day
  into `replaced/` (0.6 GB a year against R2's 10 GB free); prune old `replaced/` dates by hand if
  it matters. `data/grid/` (2,145 files, 316 MB, the z14 tile grids) goes to the same bucket under
  `grid/` at the owner's word, checked equal too; `data/notes/` (255 MB) is not in it, as the clips
  can be cut again from the notes dumps.
- **Third parties (looked up 2026-11-10 by an agent through a summarising fetch; re-read a sentence
  before relying on it):**
  - *tile.openstreetmap.org*: the tile policy gives no number. It asks for visible attribution, a
    valid Referer (the page sets no Referrer-Policy) and normal caching, and says access may be
    blocked without notice if use degrades the service. Tiles load only when Map is opened. With the
    tile host blocked in a headless browser the Map tab still draws all 147 boundaries, on an empty
    ground, with no page error; the rest of the site doesn't use tiles.
    The durable fix, if wanted, is a self-hosted PMTiles basemap on R2. Keyed free tiers (Stadia
    200,000 credits a month, MapTiler 100,000 requests a month, then paused) turn a possible block
    into a certain stop on a spike day. The owner chose to stay on OSM's tiles (2026-11-10).
  - *GoatCounter*: free "for reasonable public usage", no stated monthly cap; "millions of pageviews
    a day" is what it names as too much. The script is `async`, so it doesn't block parsing or
    drawing (a hanging host can still delay the `load` event); with its host blocked the views load
    with no page error.
  - *jsdelivr*: no bandwidth limits stated; no longer used.
