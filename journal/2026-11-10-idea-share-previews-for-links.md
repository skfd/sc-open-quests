## Idea: share previews for links (owner, 2026-11-10)

Not planned and nothing built. The site has only a `<title>` and a `description`; no `og:`/`twitter:`
tags and no image, so a shared link shows a bare title. The owner pictures people posting their
neighbourhood's link. A design, ignoring how it gets built, with a mockup in `design/og-card-mockup.svg`
(and `.png`; numbers invented):

- **One card per place, 1200x630**: the place's name and its city; one big number (open quests); a
  change chip for 30 days, green when it falls; a 90-day stacked sparkline, to map (indigo) under to
  resurvey (orange), so aging is not read as neglect; the place's own outline with dots where the quests
  are (locals know their shape); the three biggest quest types; "as of <date>" in the band, because
  networks cache a preview for days.
- **The words do half the work**: og:title "1,284 open StreetComplete quests in Agincourt North,
  Toronto"; description with the change and the top three types; og:image:alt says the same.
- **Tone follows the trend**: falling, a cheer; rising mostly by aging, "+120, mostly resurveys coming
  due"; under a few dozen, "almost done: 14 left". Invite, never shame.
- **Other views** get a variant of the same frame: one quest in a place (its icon big), compare (top
  five places by quests per km²), the map (the outline, larger).
- **Survives a thumbnail**: name and number sit in the left half, so a square crop (WhatsApp, Slack)
  keeps them; SC's indigo band reads on light and dark feeds.

Owner's answers (2026-11-10): **English only** for now. **The card shows current numbers**: a plain
link is undated, and its card is whatever was newest when the network fetched it (networks cache for days,
which the "as of" date in the band makes honest). **Tentative, if cheap**: a button that copies a link
pinned to the data date, whose card stays fixed ("Agincourt North on 8 Nov"); it needs a new query key,
since `at` and `on` are taken. Otherwise no share button: networks read the preview from the link's own
tags, so a pasted address is enough.
Constraint for whoever builds it: crawlers fetch the page without running `app.js`, so each place needs
its own static page or a Worker that rewrites the head; the state is in the query, which crawlers see.

### Share previews: proposed architecture (2026-11-10, evening; nothing built)

- **Static pages at path URLs, no Worker.** Crawlers ignore `app.js`, and static assets ignore the query,
  so each previewable view gets its own folder: `/<cityId>/` and `/<cityId>/<slug>/` (147 cities, 4,214
  parts). The slug is frozen in `config/parts` when a part is added (the 12-hex GERS id stays the key; a
  rename must not break a posted link). `app.js` reads the path and writes it for city and part views, so
  the address bar is the share link; old `?city=`/`?place=` links still open. The rest of the state stays
  in the query. Rejected: a Worker rewriting the head, because it brings back the request cap the
  assets switch removed.
- **Generator, a new `run.py` step after history and before the cloud publish:** per place,
  `docs/<cityId>[/<slug>]/index.html` = `index.html` with the head replaced (title, description, `og:*`,
  `twitter:card` summary_large_image, canonical, `<base href="/">` so relative paths survive the depth)
  and `docs/cards/...png`. `og:image` carries `?v=<asOfDate>` so networks refetch it when the data
  moves. Gitignored: the cloud sync uploads them, git never sees them. Byte-stable like the rest.
- **Rendering:** an SVG template filled in Python, made into a PNG by resvg (`resvg_py` wheel). Measured
  on the mockup: 0.30 s and 61 KB per card, with system fonts loaded each call; 4,361 cards is about
  22 min on one core. Not measured: a bundled font file and a process pool, which should cut it a lot.
- **What the data supports:** cities, everything in the mockup (history with `agedOnly`, per-quest counts,
  the outline, the z14 grid as dots). Parts: per-quest counts only, no aged split (one-colour
  sparkline), a series only since 10-28 in `data/archive` (11-04 missing; the chip says "since 28 Oct"
  until 30 days exist), and z14 tiles (2.2 x 1.6 km) are too coarse for dots inside a neighbourhood:
  the panel becomes a locator, the city's outline with the part filled.
- **Budget:** 4,836 + 2 x 4,361 = about 13,560 of the 20,000 asset files, which competes with publishing
  the archive (2,145 + 16 a day). Every PNG changes daily (the date), about 265 MB uploaded a day.
- **Dated-link button: parked.** It needs a page and an image per place per day, so it needs a script on
  its own route. Rendering takes about 300 ms against Workers Free's 10 ms CPU limit.
- **Phases:** (1) per-place pages with text tags plus one site-wide image: no renderer, half the files.
  (2) per-place PNGs. Sequencing: `cloudflare/` stays untouched until the flip and the `assets-switch`
  merge; the generator can be built and checked on `wrangler dev` before that.

### Share cards are in release 1 (owner, 2026-11-24, 04:10: "we will design and implement share cards by release day")

- Release day is about 12-01 (11-30 gated that evening, published 12-01 15:30). This replaces "per-place pictures
  after release" under "decided (owner, 2026-11-23)" below: place cards are now release work. Text previews stand.
- What the owner has said of the design is in `design/share-previews.md` on `share-previews`; its "Questions for the
  next review" are the open ones. Not built: the place card, the new general card, the batch. Renders and builds go
  in gaps of the loop only.
- **Risk to settle before go-live:** the $5 Workers limit blocks every Worker past it, and then the home page fails
  (error 1103). A render on demand spends from that same limit; a batch made here does not.
- **Owner, 11-24: the design is done in a fresh session; nothing was designed or decided here.** Claude's proposal to
  start from, not agreed: mockups of both cards first (real data), design frozen about 11-25, built 11-26 to 11-27,
  cards made and merged 11-28, Worker live 11-29. Place card: name, parent, top three quest types, no totals. General
  card: the world total, rounded and dated, once its overlaps are checked. Cards for countries, regions and the 147
  cities (about 4,350); Latin, Cyrillic and Greek names; the general card for the rest; no rendering on demand at
  release. Also the owner's: what happens at the Workers limit, and the wording "Canada and Europe".

**MERGED INTO MAIN 2026-11-26 05:26 (owner, wizard: "merge into main today", not on release day; 4c052008).** The card is
the one drawn on 11-25; it goes live with the next daily run. Still open of the list below: 2 (the release-day redraw, now on
main), 4 (the monthly redraw) and 5 (the Worker's deploy). Branch and worktree `../sc-open-quests-previews` removed.

### General card: the world's numbers (2026-11-25, 13:31; settled by the owner; merged 11-26, see above)

- `design/project-card.svg` and `.png` (2400x1260), written by `design/project_card.py` from the published files on
  sc-data: 576,650,884 open on 2026-11-24 (28,599,114 resurvey), 159 types, 248 countries and dependencies, the six
  largest types, +1,568,038 since 11-01, a strip of the total per day. The table and the 248 series agree. The
  PNG is a headless Edge screenshot, taken with no loop and no city run.
- **Owner, 11-24 and 11-25:** statistics on it; **no world map** ("world stock image"); B's and C's data together;
  **the world, not 147 cities**. The 147-city card is in git at `2b8ac4bb`, mockups A, B and C at `84057012`.
- **The overlaps of the world total, measured:** the land outlines of the 248 (one each, 248 codes) overlap in 11 pairs,
  about 1,993 km2, 1,867 of it CL and AR (the icefield), then HR and RS 108. So about 125 km2 elsewhere; its quests were not
  counted. Rounded to a million the total stands. Gaps (land in no outline) not measured.
- The first world day is 11-01, so the world has no 2017 line and the strip is flat. Owner, 11-25: ok, "at least
  it looks nice" (taken as: keep it; the version with a bar per day is in git at `f03d87c9`).
- **Owner, 11-25: "we should use this one yes".** On `share-previews`: `docs/img/share-card.png` is this card, its `?v=`
  and alt text follow it (`python design/project_card.py && python design/render_share_card.py`, in a gap). The three
  tests of `tests/test_preview_worker.py` pass there; the rest of the suite was not run. **Not merged: merging publishes.**
- **Decided (owner, 11-25):** redrawn **monthly** and on release day; the title is **"Open StreetComplete quests around
  the world"** (title, `og:title`, the page's heading; the descriptions say "places around the world", Claude's words), on
  the branch; **merged on release day, after that day's redraw**, so not before.
- **To do, for the next session (owner, 11-25: "we will pick up in next session"), in this order.** 1 to 3 in a gap of
  the world loop:
  1. Run the branch's tests: none were run since the title change (`55cdd007`; the loop was running), and before it only
     the three of `tests/test_preview_worker.py`.
  2. Release day (about 12-01): on the branch, `python design/project_card.py && python design/render_share_card.py`,
     look at `docs/img/share-card.png`, commit.
  3. Merge `share-previews` into main (the owner's yes of 11-25 is for release day, after the redraw; merging publishes
     the tags and the card with the next daily run). It was 88 commits behind on 11-25; `docs/index.html`, HANDOFF and
     DESIGN change on both sides, and `design/project-card.*` and `project_card.py` are on both.
  4. After the merge: write what redraws the card monthly, in a loop gap. Nothing does yet.
  5. The Worker's deploy is separate and needs the owner's go (with the $5 limit question above).
- **Owner's, if wanted:** the descriptions' wording (Claude's words); "248 countries and territories" counts every Overture
  country and dependency entry, possibly its placeholders too. **Known limits, left as they are:** at 360 px wide the small
  labels do not read; a centre square crop loses "577".

### Share previews: built on `share-previews`, merged 11-26 (the Worker not deployed) (2026-11-23, afternoon; owner: "build it, i will upgrade account later")

- **Workers Paid: the owner says subscribed; Workers spending limit $5 set (2026-11-23, by Claude in the owner's Chrome).**
  Billing, Spend limits: blocks all Workers on the account past $5 of usage in a billing period (Nov 10 to Dec 9 now),
  with an email to the owner. Past it the home page fails (error 1103) once the Worker is live; the plan's $5 is extra.
  Durable Objects has no limit (the site uses none). **Left: the owner's ok on the card, then merge and go live.**
- **Under review (11-23, evening):** `design/share-previews.md` on the branch (`736d7529`) has the requirements, the
  design, measurements and open questions. Owner: no outlines; the general card needs statistics. **The Worker
  render benchmark (`cloudflare/bench/run.py`) is written, not run:** it needs a gap in the world loop.
- **Correction:** four wrangler processes from the checks were left running from 13:19 and 13:25 until about 21:30
  (stopped; about 270 MB), so "check servers are stopped" below was wrong, and the test suite and browser checks of
  13:00 to 13:30 ran without looking for the loop. Not shown to have caused the 15:20 stop, nor ruled out.
- **Where:** branch `share-previews`, worktree `../sc-open-quests-previews`, two commits: `bab3d69a` (the
  page's `og:` tags and the site card `docs/img/share-card.png`) and `06bf2326` (the Worker). Its DESIGN.md
  section, "Share previews: a Worker's text for every place", has what it does and what was checked;
  `cloudflare/README.md`, "Share previews", has the go-live steps. 213 tests pass there.
- **Nothing on main or on the live site changed.** The Worker is `cloudflare/wrangler.previews.jsonc`;
  the daily run deploys `wrangler.jsonc`, which is untouched, so merging the branch puts only the tags
  and the card live.
- **Waiting on the owner, two things:** (1) a look at the card (`docs/img/share-card.png` in the worktree; the session could not send the file) before the branch
  is merged, since merging publishes it with the next daily run; (2) **Workers Paid** before the Worker
  is deployed. It must not go out on Free: about 6 ms to parse `quests.json` plus a city's history is
  past Free's 10 ms of CPU, and a failed page view is a broken page.
- **Checked locally:** all 147 cities' previews say `cities.json`'s number (293 of 293 links); seven
  links in a browser, page against card (city, part, selections, a world place, counted places under
  their place ids); the home page byte-equal; 404s; revalidation; a hostile name escaped.
- **Not checkable before live:** the zone's folder rewrite rule in front of the script. The go-live
  steps deploy by hand, test at once, and say how to put the script-less site back.
- **The site's title and description still say "Canada and Europe"** (page, `og:` tags and the card's
  alt text). Left as is: the wording for the world is the owner's, at release 1.
- **Local check servers are stopped** (ports 8791, 8792). `C:/tmp/pv-fix` and `C:/tmp/pv-check` are
  scratch and can go.

### Share previews for release 1: decided (owner, 2026-11-23)

The 11-10 architecture above is stale: `docs/` is 9,339 files (pages plus PNGs for cities and parts would
reach about 18,060 of 20,000), and about 1M world places can never be static pages. Decided instead:

- **Every place gets a text preview on release day, through a Worker.** It runs on the page request only
  (`app.js`, icons and JSON stay plain static assets), reads `?place=<id>` (crawlers send the query), fetches
  that place's file from `sc-data` and rewrites the head: title "N open StreetComplete quests in <place>",
  description with the 4-week change. Today's `?place=` links work as they are, so **no slugs are frozen**
  and the address scheme (`/toronto/agincourt-north/` against `/<country>/.../<slug>/`) stays open.
- **The picture is one site-wide card on day one** (the mockup's frame, no numbers, no date). The home page
  gets `og:`/`twitter:` tags and that image; its title and description still say "Canada and Europe".
- **Owner: Workers Paid, $5 a month, agreed** (no 100,000-a-day cap on page loads; under the $50 breaker).
  The owner upgrades the plan; not done yet.
- **After release:** per-place pictures rendered on demand in the Worker and kept in R2 (about 300 ms CPU a
  card, which is why Paid), once a card for a world place is designed.
- **To check while building:** the Worker's number must be the page's (same default-on quests summed); what
  the zone's folder rewrite rule and `html_handling: none` do with a Worker in front (`wrangler dev` does not
  reproduce the rule; that interplay broke the home page once); it goes live with or after the world
  publish merge, since it reads the same place files.

### The Worker deployed and rolled back (2026-11-27, evening)

- **Owner, 18:35:** the deploy "is decided"; asked when (wizard): "Now, tonight". Before it: `preview.test.mjs` 19 of 19,
  `parity.mjs` 293 of 293 links say `cities.json`'s number.
- **18:45 deployed** `wrangler.previews.jsonc` (version c1d8eee9). Live, all as the README asks: Toronto's `og:title` on `/`
  and `/index.html` (371,884), Blind River from `sc-data` (1,712, "As of Nov 27, 2026"), plain `/` the site's own title,
  `Cache-Control: public, max-age=0, must-revalidate`, `/data/nothing.json` 404, `cloud_publish.py --check` 8,926 of
  8,926 equal.
- **`browser_parity.py` on the live site: 5 of 7.** MISS `?city=toronto&off=AddHousenumber,AddPathSurface` (page 304,526,
  card 304,518) and `?city=berlin&base=all` (page 1,116,040, card 1,115,886). Cause, recomputed by hand: the card sums
  `docs/data/history/<city>.json`'s last day, 11-25 (the city run's files end there, it was deleted 11-26); the page joins
  the world's days onto that file (`app.js` `worldCity`, `joinWorld`) and shows 11-27: the world's `city/<id>.json` at
  day 26 gives exactly the page's numbers, at day 24 exactly the card's. Toronto's default selection happens not to have
  moved between 11-25 and 11-27, so that link matched. Berlin's description said "As of Nov 25, 2026". Every city and part
  preview would have stayed at 11-25 and drifted daily; the local check of 11-23 could not see it (the world join came later).
- **19:05 rolled back** with plain `npx wrangler deploy` (version c7d9d6ea), as the README's rule says: `og:title` is the
  site's own again, 404 still 404. Step 4 was not done, so nothing scheduled deploys the Worker.
- **Found on the way:** the zone answers 403 to Python's `urllib` user agent on every path (static files too), so
  `browser_parity.py` against the live site needs a browser user agent (run here through a wrapper that installs one);
  and its output needs `PYTHONIOENCODING=utf-8` on Windows (a U+2212 minus).
- **To do (HANDOFF Next 5):** the Worker joins the world's city and part files as the page does; the parity test checks
  against the world's numbers, not `cities.json`; then deploy again.
- **Owner, 19:15: "build it now?"** Built (b/c of the above): `preview.js` ports `app.js` `worldSeries` and `joinWorld`;
  a city is its history file joined with the world's `city/<id>.json` over `quests.json`'s counted quests for it; a
  part is the world's `place/<sh>/<id>.json` (a part in `city-parts/<city>.json`'s `noFile` is all 0), named from
  `data/parts/<city>.json`, else its history file as before. The registry now carries each quest's `status`.
  `preview.test.mjs` 22 of 22 (three new tests). `parity.mjs` takes the world host as a second argument and checks
  every city link against `city-quests.json` and every part link against `city-parts/`: **4,091 of 4,091 on 11-27**
  (293 city, 3,798 part); the old code against the same check 3,162 (929 misses), so the check sees the bug.
- **Deployed again** (be3c3f21): browser parity on the live site 7 of 7 (both earlier misses now say the page's
  1,116,040 and 304,526), previews in 0.19-0.39 s, cache header and 404 as before, `cloud_publish.py --check` 8,926 of
  8,926 equal. **Step 4 done:** `wrangler.previews.jsonc` is now `wrangler.jsonc` (what `cloud_publish.py`'s plain
  `wrangler deploy` deploys), the script-less one `wrangler.static.jsonc`; deployed with the plain command
  (a823b8d4): Berlin 221,268, the world's 11-27 number. README's section and two design topics say so.
