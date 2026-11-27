## Place statistics for the whole world: the final product (proposal, 2026-11-10, late evening)

The owner asked for neighbourhood statistics designed for the end state, with the whole world counted.
Nothing built. It takes as given what is decided: every Overture division with an OSM source and an area
gets per-quest counts; a quest counts once in every polygon holding its position, from country down to
microhood (DESIGN "The whole world"); a world count weekly, monthly points since 2017 from the history
file; the 147 cities keep their daily run.

**Scale, from the Germany prototype (`.scratch/world-de/`, 2026-11-09):** 40,520 places: 23,237
localities, 2,823 macrohoods, 9,327 neighbourhoods, 4,717 microhoods, 399 counties, 16 states, 1
country; 39,446 with a number; median 50 quest types with something open, at most 183. One snapshot of
every place: 47 MB raw, 6.3 MB gzip. The world is about 1M places, so about 25 times that: a weekly
snapshot of roughly 1.2 GB raw, 160 MB gzip.

### A neighbourhood is a place: one page for every level

There is no separate neighbourhood page. Every place, country to microhood, gets the same page, and a
level only changes which children it lists. A neighbourhood is one level among them, as today's
"parts" are.

1. **Header:** the name, and the chain above it as links (Canada > Ontario > Toronto > Agincourt
   North); a disputed place shows one chain per country (DESIGN "Countries in the place index"). Then
   one big number (open quests, ticked types), a change chip (4 weeks; green when it falls), quests
   per km² and "as of <date>".
2. **Trend chart:** stacked map (indigo) under resurvey (orange), the same as a city's: monthly since
   2017, weekly since the world count began, daily inside the 147 daily cities. App releases on the
   time axis. The two parts need the aged split per place (below).
3. **Among its neighbours:** the rank among siblings of the same subtype by quests per km² ("12th of
   158 neighbourhoods in Toronto"), and the place against its parent's average. Places with under 50
   quests are left out of ranks, so plazas and squares do not top them.
4. **Children:** a table (name, kind, open, per km², 4-week change), sortable, and the same children
   on a map shaded by per km². Children overlap and leave gaps; the existing note says so.
5. **Quest types:** the existing table, plus aged and 4-week change columns; each row links to that
   quest in this place.
6. **Out of the same files:** the share card (outline, number, sparkline) and the widget's small file.

### Hosting: place data on an R2 public bucket, not static assets

A million places is 50 times the static-asset cap of 20,000 files, and packing them into fewer files
makes one place's page download its neighbours' history. So the app stays on static assets, and place
data goes to an **R2 bucket served on its own subdomain** (for example `data.` beside the site), read
straight from the bucket with no Worker:

- **No Worker means no 100,000-a-day cap.** Cloudflare's cache in front of a custom-domain bucket
  answers repeat reads without touching R2 (to be verified with a test bucket; `r2.dev` URLs have no
  cache and are rate-limited). Uncached reads are 10M a month free, then $0.36 a million. There is no
  hard cap, so a spike costs a few dollars rather than taking the site down.
- **Writes set the cadence:** 1M free a month, then $4.50 a million. Rewriting every place weekly is
  about 4.3M writes a month, about $15. So the plan below rewrites each place monthly and writes only
  small per-parent files weekly.
- **Storage:** about 16 GB of place history (DESIGN "The whole world", item 5), about $0.10 a month
  past the free 10 GB.

### The files: three requests per place page, each cacheable for a week

| file | holds | written | count |
|---|---|---|---|
| `place/<id>.json` | name, subtype, chain, land area, outline bbox; series: dates and per-quest `open` and `aged` columns, 0 told apart from "not counted" | monthly (the 1st), weekly points since the last month folded in | about 1M |
| `latest/<parentId>.json` | the newest per-quest `open`/`aged` of every child of that parent | weekly; daily for children inside the 147 daily cities | about 100k (places with children) |
| `geo/` (PMTiles, one file) | every place's outline, id only, no numbers | when Overture's release changes | 1 |

- **A page reads** its own `place/` file, `latest/<self>` (its children, newest) and
  `latest/<parent>` (itself newest, plus its siblings, which is the rank). All three follow the quest
  ticks, because they keep the per-quest split. The children's map joins the PMTiles outlines with
  `latest/<self>` by id in the browser, so the tiles never go stale and the shading follows the ticks.
  PMTiles is read with HTTP range requests: one file, no tile server.
- **Writes a month:** 1M place files plus about 430k `latest` files, about 1.4M, roughly $2.
- **Sizes:** a place file is about 50 quests x 170 points (118 months, then weeks), about 40 KB raw
  and 10-15 KB gzip after a year; `latest/` files are tens of KB at most (a county with 300 children
  is about 60 KB raw).
- **Search** stays on the name layer's shards; a result links to `/<country>/.../<slug>/` (DESIGN
  "Share previews", readable addresses).

### What the engine and pipeline need

1. **The aged split per place:** a second array beside `partOpen`, filled where `countParts` is
   called (the mask is at hand there). Without it the chart is one colour and aging reads as neglect.
2. **Land area per place,** for per km²: the polygon's area less water, computed once per Overture
   release in the place build. Cities already use `landAreaKm2`.
3. **The world's weekly snapshot archived privately** (about 160 MB gzip a week, 8 GB a year) in the
   backup bucket. It is the source every `place/` and `latest/` file is rebuilt from. Publishing it
   as open data, one file a week, is cheap on R2 and the owner's call.
4. **The monthly history recount with places on,** once (DESIGN "The whole world", item 6: about 7
   weeks on this machine with per-cell cuts).

### Open, for the owner

- **R2 public bucket for place data** (unlimited files, Cloudflare's cache, billed past the free tier
  with no hard cap) or packing into static assets (free and capped, but a page downloads its
  neighbours too).
- **What "per km²" divides by:** land area (simple, fair across city and country) or mapped elements
  (open per 1,000 tagged things, which is closer to "how done is it", but harder to explain).
- **Freshness:** weekly for the world and daily only inside the 147 cities, or something else.

### The owner's answers (2026-11-10, late evening), and what daily changes

- **R2 public bucket for place data:** yes.
- **Freshness: daily for the world is the MVP goal,** not weekly. A daily world recount does not fit
  on this machine (a world count is about 24 hours), so daily comes from the stream (DESIGN "The
  stream", steps 1-5), not from recounting the planet every day.
- **Daily makes writes the cost to design around.** Ontario's 790 parts, 10-29 to 11-08: 87 to 197
  change on a given day (11-02: 435), so about 12-25% of places a day. Measured:

  | plan | R2 writes a month | about |
  |---|---|---|
  | every `place/` file daily | 30M | $130 |
  | only changed `place/` files daily, plus `latest/` per parent | 5-6M + 3M | $32 |
  | **`place/` monthly; `latest/<parentId>` daily holding its children's days since the 1st, as per-quest changes** | 1M + 3M | **$13.5** |

  Proposed: the last row. A page reads the same three files: its `place/` file (history to the 1st),
  `latest/<parent>` (its own days this month, and its siblings for rank) and `latest/<self>` (its
  children). Daily files are cached until the next publish; a tiny `latest.json` (the date) is cached
  for minutes.
- **The density divisor was explained in chat,** with no decision yet. The site already shows "per km²
  of land" and "per km of road" for cities (`app.js`, Compare and the city tiles).
- **Correction (owner):** the per-km² and per-km-of-road tiles came with the prototype; they are
  not agreed design. A divisor is needed only where places are compared (rank, shaded children map,
  "against the parent's average"). Proposed for the MVP: no comparison, so no divisor. A place page
  shows its raw count, change, trend, quest types and children by raw count, and the children's
  map shows clickable outlines without shading.
- **Owner, same evening:** the daily R2 plan (about $13.5 a month) is fine. Comparison stays where it
  is today, the Compare tab's city table (open, per km² of land, per km of road, per 1,000 people), and
  places below a city are not compared. So place pages carry no divisor, and the engine needs no area or
  road length per place. Open for later, at world scale: which places Compare lists once there is no
  fixed list of 147 (for example, cities over a population bar with a country filter).

### The R2 cache premise: checked (2026-11-17, 02:20)

- **JSON is not cached by default.** Cloudflare's docs (cache/concepts/default-cache-behavior): "The
  Cloudflare CDN does not cache HTML or JSON by default", and caching goes by file extension, not MIME
  type. Measured on the test bucket `sc-open-quests-cachetest` at `sc-r2-cachetest.comentality.com`:
  30 fetches each of a JSON with `Cache-Control: public, max-age=3600` and one without were all
  `cf-cache-status: DYNAMIC`, every one an R2 read.
- **A cache hit is not an R2 read.** The PNG beside them: 1 MISS, 29 HITs, and the bucket's GraphQL
  analytics (`r2OperationsAdaptiveGroups` by `objectName`) show exactly 1 GetObject for it. So
  Cloudflare's cache in front of a custom-domain bucket does answer repeat reads without R2, once a
  file is eligible for cache. (The script's own verdict line said otherwise; it counted bucket-wide
  reads, which included scanner bots, below.)
- **The zone's Browser Cache TTL is 4 hours** (comentality.com, `browser_cache_ttl` 14400) and it
  raises a lower origin `max-age`: the PNG uploaded with 3600 went out with 14400. A file meant to be
  cached for minutes (`latest.json`, the date) needs the rule below to respect origin TTL.
- **Scanners arrive within two minutes of a new hostname's certificate** (Certificate Transparency):
  about 30 GetObject probes for `.env`, `.ssh/id_rsa`, `backup.sql`, `wp-admin/...`. Each missing key
  is a Class B read (10M a month free), harmless, and a reason the data bucket holds only published
  files.
- **The place-data host is `sc-data.comentality.com`** on bucket `sc-open-quests-data` (ENAM, created
  2026-11-17; domain attached by the owner). Its Cache Rule "sc-data cache" is deployed on the zone
  (2026-11-17, the zone's first): `(http.host eq "sc-data.comentality.com")`; eligible for cache; Edge
  TTL "use cache-control header if present, bypass cache if not"; Browser TTL "respect origin TTL".
  Checked: a JSON uploaded with `max-age=120` went MISS, HIT, HIT and kept its 120 (no 4-hour
  rewrite). So each upload's `Cache-Control` sets both: a day for `place/` and `children/` files (each
  asked for under a new `?v=` address after every publish), five minutes for `latest.json` ("World places
  published: stable paths (schema 2)"). A file uploaded without one is not cached.
- **The test is cleaned up:** the test domain removed, the bucket `sc-open-quests-cachetest` and its
  three objects deleted. The script stays in `.scratch/r2-cachetest/`.
