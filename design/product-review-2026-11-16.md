# What the site shows: a product review (2026-11-16)

The owner asked: "let's discuss the information we display as product designers. Anything we should
change? Where are we moving?" This review is based on the real `docs/data` served locally: Toronto
(desktop and 390 px phone), Compare, Places, Map and one neighbourhood page (Parkdale, **Calgary**).
Nothing has been changed.

## The gap in one line

The owner's direction (DESIGN.md, "Planet coverage: the owner's direction") is that the site is for
players asking "how is my place doing?". The city page still answers an analyst's question: five
tiles, a nine-year chart, and a table of about 190 rows. The neighbourhood page answers neither. It is
the thinnest page on the site, and it is the template for about a million place pages to come.

## 1. Decided, but not on screen yet

- **One page for every level** (DESIGN.md, "A neighbourhood is a place"). Today a city and a
  neighbourhood are two different pages under two tabs ("One city" and "Places"). The part page has
  no chart and no aged split. It says "Parts have no aged split or history yet" (`app.js:1506`).
  That stopped being true this morning: the 35-day part series (`docs/data/history/<city>/<part>.json`)
  is merged and publishes with today's run, but the site does not read it. Only the widget does.
- **Notes on import steps** (HANDOFF, "Deeper history": "worth a note on the site"). Toronto's chart is
  shaped by two AddHousenumber imports, +293k in 2019-01 and −277k in 2026-05. Nothing on the chart
  says so, so a player reads them as a collapse and a heroic cleanup.
- **The density tiles are prototype, not agreed design** (DESIGN.md, the owner's correction of
  2026-11-10). "Per km² of land" and "Per km of road" still take two of the five tiles on every city
  page. Comparison belongs in Compare, and that is the only place it was agreed.
- **"Invite, never shame"** (share-preview tone). Compare ranks 147 cities by density. That is fine, but it is the only
  voice the site has about a city's standing, and a ranking is the shaming voice.

## 2. Proposals

Ordered by value to a player against cost.

1. **Build the unified place page now, on the 147 cities and 4,214 parts.** It has the header chain,
   the big number with its change, the stacked map/resurvey chart, the quest table and the children.
   Use the owner's later answers: no rank, no divisor, nothing below a city compared. The data already
   exists (city history, and part series from today). This is the page the world count will multiply,
   so it should be right before the planet store feeds it. *Recommended first.*
2. **Default the chart to recent time.** A player's question is "this month", and nine years at
   ~900 px puts the last 30 days into a few pixels. The −293 since yesterday is invisible. Proposal:
   open on 90 days, with an "All since 2017" toggle that the link remembers. Mark import steps with a
   one-line note, the way release pins are marked.
3. **Say "net change", and in words.** "−293 since 2026-11-13" mixes edits, aging and new OSM data
   (new buildings bring new quests). The site cannot count solves; changesets are a non-goal. So label
   it honestly ("293 fewer than yesterday"), and split the 4-week change into map and resurvey, which
   the data has. Relative dates ("yesterday", "4 weeks") read better on a phone than ISO dates.
4. **Fix the quest table for players.**
   - Sort ticked quests first. Toronto's table opens on two unticked, off-by-default rows (roof shape
     367k, building levels 347k) that are larger than the total above them.
   - Fold the zero rows into one line ("15 quest types done here" in Toronto). That line is the most
     encouraging fact on the page, and today it is 15 rows of "0 ±0 —" at the bottom.
   - Move the class name (`AddRoofShape`) into a tooltip or the quest page. It is developer detail on
     every row.
   - On a phone the question text is clipped at the card's right edge ("What basic shape does this
     bui"). That is a bug, not a design choice.
5. **Replace the two density tiles** with numbers a player acts on: the 4-week change (map vs
   resurvey), and the quest type with the most open here.
6. **Shorter header on a phone.** Today the first screen is the title and the tiles, and the chart
   starts below the fold.
7. **Navigation, once the page is unified.** Search → place page, Map, Compare. "One city" and
   "Places" collapse into one.

**Not proposed:** solved-this-week, streaks, per-user numbers. The data cannot support them, and per-user
stats are a non-goal.

## 3. Where we are moving

Documented direction: every place on Earth named; places counted daily (the stream); one page per
place on an R2 data subdomain; share cards per place, monthly; the native widget; Compare stays
city-level.

What the commits say: since 2026-11-06 almost all work has gone into the engine and the planet tile
store. The visible site moved twice: the city picker and map (11-06), and the chart's hoverable ends
(today). The pipeline is heading toward a million places. The page those places will land on is the
weakest one we have. Products usually stumble on that order: infrastructure ready, page unready.

## 4. Open, for the owner

- Unified place page first, or keep the planet store going and design the page in parallel?
- Chart default range: 90 days, 1 year, or keep all since 2017?
- Remove the density tiles from the city page (they stay in Compare)?
- Zero-open quest types: folded into "N done here", or hidden?
