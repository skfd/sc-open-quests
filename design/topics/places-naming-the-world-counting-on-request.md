## Places: naming the world, counting on request (proposal, 2026-10-24)

Proposal from the breakdown session; nothing built. Sources are in the session's two research reports
(Wandrer.earth; world boundary datasets), the URLs repeated here where a choice rests on them.

- **Wandrer cannot be the data source; it is the model.** No API, no export, region pages behind a
  login, "All Rights Reserved" (wandrer.earth/terms). Its regions are OSM boundaries plus neighbourhoods
  patched in one city at a time from 38 municipal open-data sources, each credited on its terms page, and
  added when a user emails the source (wandrer.earth/faq). It rebuilds from one planet file about monthly.
  Copy that: OSM as the backbone, neighbourhoods patched per request from open data, a data-licences
  page, requests that bring their source.
- **Names from Overture Maps `divisions`.** ODbL like our output; one world hierarchy with
  `parent_division_id`, normalised `subtype` (country, region, county, localadmin, locality, borough,
  macrohood, neighborhood, microhood), local names, wikidata, monthly releases (latest 2026-10-21.0),
  6.4 GB for the world, downloadable per bbox (docs.overturemaps.org/guides/divisions). Each feature
  names its OSM source (`sources[].record_id` such as `r166560@15`, plus bridge files). Raw OSM
  `admin_level` cannot be the hierarchy: its meaning changes per country. Who's On First (sporadic, 42 GB,
  CC-BY parts), geoBoundaries (no parents, mixed licences) and GADM (no redistribution) are out.
- **Two layers, two ids.** The *name layer* is every Overture division: id, name, parent, subtype, bbox,
  centroid, OSM relation. No polygons, nothing counted. The *count layer* is the places someone asked
  for, counted on OSM geometry by relation id as `add_city.py` does today, so the boundary and the counts
  come from the same data. The public id is a readable path (`ca/on/toronto/the-annex`, Unicode-safe),
  mapped to the GERS id; GERS ids survive Overture's conflation but subtypes move with OSM tagging
  (Czechia and Slovakia, 2026-06 release), so a monthly diff flags places whose subtype or parent moved.
- **Three kinds of counted place.**
  - *Run place*: today's city. Its own map data, so the area quests stay exact (DESIGN.md, "Area unit").
  - *Sub-place*: a neighbourhood or borough inside a run place. Counted from quest positions inside
    its polygon, in the run place's pass: the engine already counts one element towards several
    overlapping places (`Engine.kt` `offer`, the `cityIdx` loop), so a sub-place is one more polygon in
    the index with no map data of its own. Its numbers are the city's numbers split by position, which is
    what a player there sees. Lifting the 64-place mask (taken by the measuring session) is the one
    engine prerequisite.
  - *Roll-up*: a region or country. Only the sum of its counted children, labelled "N of M places
    counted". Never a number that looks like full coverage.
- **Land outside cities** then has an answer that costs nothing to decide later: it is a county or
  localadmin in the name layer, and counting it means requesting it as a run place. Neighbourhoods
  never cover what their city does not, and children are not promised to add up to the parent
  (OSM neighbourhood polygons overlap and leave gaps).
- **What it costs before anyone asks.** A name shard per country, loaded when the reader opens that
  country, and per city for its neighbourhoods. Size unmeasured; with the Pages cap (DESIGN.md,
  "Planet coverage: what was measured") it must stay well under 100 MB for the world or live outside
  `docs/` like the archive.
- **The request.** The site's search finds any place. An uncounted place shows its hierarchy and an
  "Ask for this place" link: a GitHub issue form, prefilled with the place id, where a 👍 is a vote and
  a reply can name an open neighbourhood source. Adding a requested place stays a reviewed commit.
- **Where Overture is thin.** Neighbourhoods are spotty below county (Overture's own docs); some
  features come from geoBoundaries with no OSM relation, and those count on Overture's polygon or not at
  all. Fill neighbourhoods from OSM (`admin_level` 9-11, `place=suburb|quarter|neighbourhood` areas,
  `boundary=place`) attached under the Overture parent by containment, then municipal open data per
  request (Toronto's 158 neighbourhoods are OGL-Toronto, which Wandrer already uses).
- **Disputed areas** (Kashmir, Crimea, ...): Overture carries perspectives; pick one policy before the
  first such country. Decided 2026-11-10: countries come from SC's own boundary data, below,
  "Countries in the place index: StreetComplete's, not ours".

**The owner's answers (2026-10-24, late evening):** names from Overture `divisions`, counting on OSM
geometry, as proposed. Neighbourhoods from **OSM only**: where neither OSM nor Overture has one, the
city has none; no municipal open data, so no per-source licence checks. Requests through a **GitHub
issue form** (players without an account cannot ask; accepted). The spike below runs that night.

**Next, a spike before any building:** pull Overture divisions for Canada and Germany with DuckDB (not
installed; `pip install duckdb` in the .venv) and measure: features per subtype, the share with an OSM
relation, whether the 115 counted cities are found by relation id, neighbourhoods inside Toronto and
Berlin, and the size of a name shard per country, extrapolated to the world.
