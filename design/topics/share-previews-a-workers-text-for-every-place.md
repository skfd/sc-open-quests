## Share previews: a Worker's text for every place (2026-11-23; owner: "build it", text only, $5 a month agreed)

Built on branch `share-previews`, not live. This replaces "Share previews: proposed architecture" (static
pages per place): `docs/` holds 9,339 of its 20,000 files and the world has about 1M places, so a page
per place cannot be a file.

**What a pasted link shows.** A network's crawler fetches the page and never runs `app.js`, but it does
send the query. So the page's head is written per request: `og:title` and `og:description` say the
place's number, e.g. "3,398 open StreetComplete quests in Agincourt North,
Toronto" and "Down 35 since Oct 27. Most open: path surface 687, tactile paving kerb 387, tactile paving
crosswalk 287. As of Nov 22, 2026." The picture is one site-wide card, `docs/img/share-card.png`
(1200x630; the owner's pick of 2026-11-25: the world total with its date, the six largest types; source
`design/project-card.svg` by `design/project_card.py` from sc-data, drawn by `design/render_share_card.py`, which
also writes `?v=` and the alt text. It does not redraw itself). A link with no place, or one the site has no numbers for, keeps the
static head in `docs/index.html`, which now carries the `og:` tags and `twitter:card` itself.

**No addresses were frozen.** Today's links work as they are (`?city=`, `&part=`, `?place=&in=`, and the
selection `base`/`on`/`off`), so the choice between `/toronto/agincourt-north/` and
`/<country>/.../<slug>/` is still open. There is no `og:url`: every view shares one file, and a network
that reads `og:url` files the link under the address it names.

**The script** is `cloudflare/src/site.js` with the arithmetic in `cloudflare/src/preview.js`
(`cloudflare/wrangler.jsonc`, which the daily run deploys; live since 2026-11-27, the script-less site kept as
`wrangler.static.jsonc`, the way back). A city's numbers are its history file joined with the world's days of it,
a part's the world's file first, as the page reads them (`app.js` `cityHistory`, `worldPart`): the history files
ended on 2026-11-25 with the city run, and the first deploy, which read them alone, said 11-25 (rolled back).
`run_worker_first` names `/` and `/index.html` only, so every data file, icon and script is still a
static asset served without it. A path that matches no file reaches the script, which hands it to the
assets for their 404.

- **It can only add.** No place in the link, a file missing, the world host down or slow (1.5 s for the
  whole preview), any exception, in the preview or in the rewrite: the request goes to the assets as it came, so the page is the asset
  byte for byte and `cloud_publish.py --check` still holds.
- **The number is the page's.** `preview.js` follows `app.js` function by function: the selection
  (`resolveSelection`), the total (`totalSeries`), 4 weeks back or the first count (`renderTiles`), the
  change over quests counted on both dates (`likeForLike`), a world place's change points clipped at
  `latest.date` (`worldSeries`, `pointAt`). A `?place=` link to a counted city or part says the daily
  count, as the page rewrites such a link to `?city=`: the name layer's `counted` column names it, and
  without `?in=` the cities' own `place` ids do.
- **Names:** a city's from its history, a part's `en` or `name` with its city, a world place's from its
  name-layer row (English where the layer has it) with its parent's, else the place file's `name` and the
  country (CLDR, Palestine by the short form). They are OpenStreetMap's text and go in through the
  rewriter as text and attribute values only, with `& < >` escaped for the attributes.
- **Words:** "Down N" for a fall; "Up N, mostly resurveys coming due" when more than half the rise is
  aged; "since <first count>" for a series younger than 4 weeks; quests by their class name ("bench
  backrest"), not the app's question. "Almost done: 14 quests left" only for a place under 50 that is
  also falling: a hamlet with 14 quests nobody touched is small, not almost done (an interpretation of
  the 11-10 note "under a few dozen").
- **A rewritten page is not the asset:** it goes out without the asset's `ETag` and `Last-Modified`, so
  a reader's revalidation cannot answer 304 onto an older number, and with the asset's own
  `Cache-Control` (`max-age=0, must-revalidate`), so the page is still asked for every time and a new
  `index.html` never runs against an old `app.js`.
- **`<title>` and `description` are left alone.** `app.js` never sets the title, so a rewritten one would
  stay on the tab, the history entry and the bookmark after the reader moves to another place. Networks
  read the `og:` tags.

**Checked (2026-11-23), all on `wrangler dev`:**
- `node cloudflare/test/parity.mjs`: for all 147 cities, `?city=<id>` and `?place=<its place id>` say
  `cities.json`'s `open` (293 of 293 links; London, GB has no place id).
- `cloudflare/test/browser_parity.py` (Playwright; the world host refuses a localhost origin, so the
  browser runs with web security off): the page's hero tile and 4-week tile against the card for a city,
  a part, two selections, a world place, and a counted city and part under their place ids. 7 of 7.
- `/` and `/index.html` with no place, and `?city=nowhere`: byte-equal to `docs/index.html`. A missing
  data file: 404. A revalidation of `/` with the asset's ETag: 304; of `/?city=toronto`: 200.
- A place named `</title><script>...` comes out escaped in the attributes.
- 19 node tests (`tests/test_preview_worker.py` runs them and the parity script on the fixtures).

**Not checked, and cannot be before it is live:** the comentality.com zone's rewrite rule ("Serve
index.html for folder paths") in front of the script. The script answers `/index.html?city=...` because
that is what the rule should hand it, but `wrangler dev` does not run the rule, and its interplay with
the assets broke the home page once (11-11). The go-live steps in `cloudflare/README.md` test it first.

**Cost.** Workers Paid: $5 a month with 10M requests and 30M CPU-ms included (looked up 2026-11-23).
One request a page view (a
reader's page writes `?city=` into its address, so nearly every reload takes the script's path). CPU
measured in node on this machine: `quests.json` (742 KB) parses in about 6 ms, once per isolate every
10 minutes; a city's history (190 KB) in about 1.5 ms; a name-layer file in about 1 ms (two are over
1 MB, India's 3.6 MB). That is past Workers Free's 10 ms, which is why it must not be deployed before the
upgrade. `tools/spend_breaker.py` prices R2 only and does not see this.

**Later, not built:** a picture per place, rendered in the script on demand and kept in R2, once a card
for a world place is designed. A small file with only the quests' names and defaults would take the
6 ms out, if the CPU ever matters.
