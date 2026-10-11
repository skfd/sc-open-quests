# Handoff: StreetComplete open-quest statistics per city

## Goal
Build a public website that graphs **open StreetComplete quests per city over time, broken down by quest type**. As far as we know, nothing like it exists. jmizv's sc-quest-stats on Codeberg is a static, single-city Markdown snapshot. Pilot city: **Toronto**.

## What the site should answer
- How many quests of each type are open in city X right now?
- How has that changed over time? Which types are being solved, which are piling up?
- How do cities compare, normalized so size doesn't dominate?
- Where in the city is a given quest type concentrated? (stretch goal: map/heatmap)

## High-level goals
1. **Reuse StreetComplete's own quest definitions.** Don't hand-write Overpass queries. Most quest types declare an element filter string in their Kotlin source (`streetcomplete/StreetComplete`, `quests/**`). Extract and parse those so the tool stays in sync with app releases. Pin the app version used for each data run.
2. **Be honest about coverage.** Some quests aren't pure tag filters: resurvey intervals based on `check_date` age, country-specific enablement, geometry or nearby-feature checks. Classify each quest type as *supported*, *approximated* or *unsupported*, and show that classification on the site.
3. **Daily snapshot pipeline.** Pull a regional extract (Geofabrik Ontario to start), evaluate the filters, count per city boundary (`admin_level=8` or equivalent) per quest type, and append to a time-series store. The pipeline must be idempotent and cheap enough to run on a schedule.
4. **Normalize.** Store raw counts plus denominators (km of road, element counts) so cities can be compared fairly.
5. **Separate the "aging" signal from the "mapping" signal.** Resurvey quests reopen without any edit. Track them separately so the graphs don't mislead.
6. **Simple static frontend.** Charts per city and per quest type, with a city selector and a quest-type filter. Static hosting is preferred: generate JSON and serve from GitHub Pages or similar.
7. **Designed to scale out.** Adding a city or region should be configuration, not code.

## Non-goals (for now)
- Counting *solved* quests from changesets (possible later via the `StreetComplete:quest_type` changeset tag)
- Per-user stats or leaderboards
- Real-time updates

## Suggested first milestone
Toronto only, about 10 common quest types whose filters are simple, a few weeks of daily snapshots, and one chart page. Then extend to the full quest list and more Ontario cities.

## Context
- Owner is an experienced OSM contributor with existing Toronto/Ontario OSM tooling in sibling folders (e.g. ../toronto-streets-layer, ../toronto-addresses-layer, ../toronto-buildings-3d, ../osm-mayflies). Reuse conventions (Python + .venv, README/DESIGN/PRIOR-ART docs) and boundary data where it makes sense.
- Open questions for the owner: preferred stack (Python/osmium vs PostGIS vs Java), hosting, and whether to coordinate with jmizv or the StreetComplete developers early.
