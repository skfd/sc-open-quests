## The place page: one page for a city and each of its parts (2026-11-16, evening; owner: "the place page comes first")

**Status: preliminary (owner, 11-16 late evening).** Accepted and merged, but the design itself has not been reviewed by
the owner; the direction (one page per place, places processed down to neighbourhoods) is confirmed as right and
valuable, the details below are a first draft.

Built on branch `place-page` from the product review's answers (`design/product-review-2026-11-16.md`).
The city view is now the place page of "A neighbourhood is a place", for the 147 cities and their 4,214 parts.

- **One renderer, fed by a series.** A city reads `history/<city>.json`; a part reads its 35-day file
  (`history/<city>/<part>.json`) made whole on load: the city's `meta` on the same dates (so version breaks
  show on a part too) and every quest the city has, 0 where the city counted it and the part had none, null
  where the city did not count it. Ticks, pins, the table, "Only quests the app had then" work on both levels.
- **Links.** `?city=X` and `?city=X&part=<placeId>`. A `?place=<id>&in=` link to a counted place (the widget's,
  and the place browser's) opens the same page and is rewritten to `?city=`. Old hash links still work.
- **Head:** the chain from the name layer (`cities.json` now carries each city's `place` and `in`; a part's
  file has `in`), filled once the region file is in, so the page paints from the series alone. London, GB is
  the one city without a row: its chain stops at the country text.
- **Tiles:** open quests with the net change in words ("9 fewer than yesterday": edits, aging and new map
  data together, since solves are not counted); need mapping; aged; **the 4-week change split mapping vs
  resurvey** (a part, younger than 4 weeks, says "Since Oct 27"); **the quest type with most open**. The
  density tiles are gone from the page; density stays in Compare.
- **Chart:** opens on the last 90 days (`RECENT_DAYS`); "All since 2017" is `range=all`, hidden where the series
  is shorter (parts). The window is one slice of the series, so chart, sparklines, legend, breaks and gutters agree.
- **Steps:** one quest type moving by a tenth of the total or more (and at least 500) between two counts gets a
  faint band and a line under the chart saying size and quest; consecutive steps of one quest in one direction
  are one note; the largest four. What a step *is* is said only where known (`KNOWN_STEPS` in `app.js`: Toronto's
  2026-05 address import; the 2019 rise is not confirmed, so it is only sized). Across the 147 cities, 125 such
  steps exist, nearly all before the 90-day window, mostly house numbers in 2019 and power poles.
- **Table:** counted quests with nothing open fold into one line, "N quest types done here", opened on a click.
  On a phone the trend, aged share and class name give way and chips wrap, so the table fits from 320 px.
- **Children:** the city's parts from its newest snapshot (name, kind, open over the ticked quests), each a link
  to its page, the current one marked on a part's page; then the name layer's places inside. No per-child change:
  that would be a file per child (`latest/<parent>` does that, later). **Loaded when the reader nears them**: the
  snapshot is the region's (Ontario's is 2.4 MB, 249 KB gzipped, against Toronto's 37 KB history). The chain's
  region file loads at once (15-80 KB gzipped; the largest a counted city sits in, France's, 79 KB).
- **Wording:** "fewer than the day before", not "yesterday": the counts can land two days late. The 4-week tile
  says "across an app release" when a version break falls inside it.
- **Navigation:** three tabs, Places, Compare cities, Map. The place browser (countries, regions, the ask card)
  is reached from "All countries" in the chain and from the city sheet ("Every place, by country").

Checked with `.scratch/place-page/drive.py` (every link shape and level at 1200 and 390 px: no page errors, no
sideways scroll except Compare's table, which scrolls the same on main; city-states and a Berlin part included),
`clicks.py` (range, fold, ticks and pins on a part, crumbs, sheet, tabs, a widget link then Map's "find a place")
and `fixtures.py` (the test fixtures through `?data=`, one snapshot and no parts; dark mode). **Observed, not a page bug:** 1,715 of the 4,214 part series do not move
at all over their 17 days, Casa Loma's 1,105 among them; they are the small and quiet ones (200 of Toronto's
218 move, and every large one does).
