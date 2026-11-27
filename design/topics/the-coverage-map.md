## The coverage map (2026-11-06)

The owner asked to see what is covered and what is not, on a map. A fourth tab, Map (`?view=map`).

- **Covered means counted: the 147 city boundaries.** The extracts are not drawn: Ontario's reaches the
  whole province, and most of it is not counted, so drawing it would say the opposite. Neighbourhoods are
  not drawn either: they lie inside their cities and add no area.
- **`docs/data/coverage.json`, from `run.py history`,** so a new city appears with no extra step (DATA-FORMAT.md).
  547 KB, 151 KB gzipped, built in under a second; 186,000 boundary points become 29,000 at about 30 m. Only
  the map tab fetches it. It holds ids and shapes, not names or counts, or it would rewrite every day.
  Plain Python, not shapely as the tools use: the daily task runs `run.py` on the system Python, and a
  missing package must not stop a count for a picture. Neighbouring cities are simplified apart, so their
  shared edges can differ by up to the tolerance; it does not show until about zoom 14.
- **Leaflet 1.9.4 and OSM's standard tiles.** The site's second library, from jsdelivr with an SRI hash as
  uPlot was (both from `docs/vendor/` since 2026-11-10), loaded only when the tab opens, so the other pages pay nothing. Tiles are turned grey by a CSS
  filter so the indigo stands out (inverted in the dark theme). If traffic ever outgrows OSM's tile policy,
  the URL is one line.
- **Dots below zoom 9.** A city is a pixel or two at the zoom that holds both continents, so each has a dot at
  its bounding box's centre until its shape is big enough to see. Hover names a city; a click gives its
  name, where it is, its open quests and a link to its page.
- **The link holds the view:** `at=zoom/lat/lon` once the reader has moved the map; without it, every city fits.
- **Not done.** The map is not yet a city picker, though it now could be (the "Not done" of "The city picker"
  above). No per-quest heatmap: the z14 grids are still unpublished. Uncounted land has no click; the
  sentence over the map sends the reader to Places to ask for it.
