## The Map tab redesign (2026-11-27, morning)

The owner, 10:20 EST: "i think map page is not up to date anymore. how do we redesign it".

**What was found (read only).** The Map tab (`?view=map`, `renderMap`/`buildMap` in `docs/app.js`) draws the 147 city
boundaries of `docs/data/coverage.json` (built 2026-11-06) and says "The coloured areas are counted: ... The rest of the
world is not counted yet; find a place to ask for it." Since release 1 every place in the world (about 1M) is counted
daily on sc-data, so the sentence is false and "where we count" no longer tells anything apart: the 147 cities differ
only by their history back to 2017 and their parts. The popups' numbers are current (sc-data's `cities.json` overlays
`open`). Published for world places: names, kinds, the chain and a bounding box per place (the name layer,
`docs/places/`), and per-quest counts (`place/`, `children/`). Not published: outlines, land area, a file of the
countries' own numbers (there is no world parent file).

**Proposed, 10:30:** a map shaded by open quests per km² that drills country > region > place page (the settled
design's children map), in three steps: the sentence now, countries and regions from one static outline file, every
level as PMTiles after the 12-01 Overture switch.

**The owner's answers, 10:34:**
- The map's job: "map should be a tool to find a region down to some level of accuracy, but idea of visualizing stats
  should be explored later write it down. whats a reasonable way to do make it a navigation tool?"
- The false sentence: "Wait for redesign" (left as it is).
- Shading: "not doing stats /shaded design will take a step back".

So the stats map is parked (BACKLOG.md) and the tab becomes a navigation tool; how, to be proposed next.

**Proposed, 10:40:** bounding boxes now (the name layer's, overlapping near borders) or real outlines as one PMTiles
file after the 12-01 switch; depth; a "Near me" button. Reverse geocoding ruled out (an outside service handed readers'
positions; OSM boundaries are not Overture places).

**The owner, 10:45:** "Real outlines, after 12-01 (Recommended)", "Down to cities (Recommended)", "Near me": "Not now".
Settled in design/topics/the-map-tab-a-navigation-tool.md; HANDOFF Next item 7.
