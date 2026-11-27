## City neighbourhoods on the world's counts, and places with nothing open (2026-11-24, evening; nothing built)

- **The 41 neighbourhoods absent from the world's `counts.json` are in its plan; they have no quests.** That list holds
  only places some quest row falls in (50,859 of 1,069,532 world places are absent the same way). The city run has 0 for
  them in all 1,804 entries, 10-27 to 11-23. **The other 4,173 match:** city D against world D+1 (2.6 h; no part is in
  Europe's four, so no same-clock day), seven days 11-02 to 11-22, 93.4 to 94.3% equal in every quest, sums +0.002 to
  +0.008%. 166 have a steady difference (788 quests in all): 35 reach past the city line (Winnipeg's Mathers +2.1%, the
  largest), up to 21 have another outline, 112 neither (nearly all `AddHousenumber` by 1 or 2; in the four cities that
  showed it, of five checked, the city total has it too; cause not traced).
- **Owner's answers:** neighbourhoods show **the world's number as is** (no clipping at the city line); a series starts
  **2026-11-01, world only** (10-27 to 10-31 not glued on). The 41 were left "for another session after discussion";
  then the owner accepted the empty-place design below, where they are state 1.
- **For the builder of the city pages:** take the parts from `config/parts`, 0 for any the world does not list; `run.py`'s
  part series skips a part that is in no snapshot and starts one at its first listed day, so give it every registered part.
  `tools/add_parts.py` cuts outlines from the Canadian and German extracts: it needs another source once those stop.
- **Places with nothing open: the design (owner: "this looks good, we go ahead with it").** Zero has five meanings:
  1. *Nothing to ask* (never had a quest): "No open quests. None on any count since <first>." No tick, tiles or chart.
  2. *All clear* (had some): "✓ No open quests. The last 3 closed on 23 Nov", the quests, and the chart. "Closed", never
     "completed": the counts cannot tell a solve from a deletion or an app change.
  3. *All clear, more due*: state 2 plus "Some come back as they age"; the published files do not carry it yet.
  4. *Your ticks hide the rest*: "0 of your selected quest types, 14 open in all", Select all.
  5. *Not counted*: only where nothing counts the place.
  Table: "N quest types done here" becomes a ✓ fold for types that had some and a plain fold for the others. Lists: a plain
  0 at the bottom, ✓ for state 2 only. The world publisher writes a small file for each absent place, from 11-01 (read
  from the code, not checked live: a place with no row has no file, so its page says "Not counted yet").
- **Measured:** world, 11-03 to 11-23: 51 places went from open to 0, 40 listed ones from 0 to open. Parts at 0 now: 87, one
  of which had any in its window.
- **Trap found while looking at the widgets:** a part's series lists only quests open on some date of its 35 days, so state
  2 would turn into state 1 after 35 days. The files must carry the last open count and its date (per quest, since the
  ticks choose the total).
- Mockups and scripts: `.scratch/parts-vs-world/` (`mock/empty-places.html`, `mock/empty-widgets.html`; not in git).
- **Widgets: the owner adopted the design for both (Android and Scriptable), 2026-11-24** ("adopt"; nothing built,
  `~/Code/sc-open-quests-widget` unchanged). The same states:
  1. *Nothing to ask*: grey "0" and "No open quests" (medium: "on any count since <first>"). No chip, line, tick or section.
  2. *All clear*: green "✓ 0", the chip stays, the line ends on a baseline at 0, "last 3 closed 11-23"; large: "Last to close"
     with "3 → 0" in place of "Most open". The same for one quest type in a city (191 city × quest pairs are there now).
  3. *More due*: waits for data. 4. *Quests off by default hide the rest* (widgets have no ticks): "0", "9 more open in quests
     off by default" (159 parts now). *Data over 3 days old*: red date as now, and no tick.
  - Lock screen (iPhone): "✓ 0", a bare ✓ in the circle; "0" for state 1.
  - Fix with it: 0 instead of the "No quest" error for a quest the city counts but the part never had (Scriptable); the zero
    line floating at mid-height; the empty "Most open · a quiet week" on large; and the last open count and its date from the
    files (the trap above).
  - Every product in one commit with its `features.json` rows, and shared fixtures for the model tests.
- **Squares as neighbourhoods: being discussed, nothing decided or built (2026-11-24).** 36 of the 41 are OSM `place=square`,
  which Overture calls microhood (`local_type` "square" in `division.parquet`: an exact mark for all 469 squares among our
  4,214 parts). Berlin 272 of 461 parts, Hamburg 66 of 188, Montreal 25 of 61. World: 70,684 of 1,069,532 places (Italy
  19,684), none the parent of another place. Open on 11-23: median 5, 38,803 have 5 or fewer, 17,631 have 0 (16,352 unlisted,
  of the 50,859), 949 have 100+, the largest 1,504; our 469: the largest is Alexanderplatz, 272. Some large ones are housing
  estates tagged as squares (Indonesia; Superilla del Poblenou).
  If dropped from the name layer: the lists, search and publisher lose them (the publisher goes by `docs/places`); the counts
  keep them, so it can be undone. 93.5 MB of name files lose 6.3 MB; an old link says "a place the site cannot find".
  **Traps:** the bucket's files for them are over `MAX_DELETE` (2,000), and the changed parents' lists may be past `DAY_CAP`;
  `add_parts.py` and `world_cities.py` read the registry, so it must lose them too.
- **Areas of the places, measured (2026-11-24, owner: "5000 m2 is too small"; nothing changed):** Overture publishes no area
  statistics (no area column; release notes give only feature counts and churn per type). Ours, every outline of 2026-10-21.0,
  within 0.03% of the geodesic area: `.scratch/parts-vs-world/areas.py` (areas.npz, 17 MB), `areas2.py`, `areas3.py`.
  - Squares are tiny: median 1,063 m² (Italy 19,684 of them, 94.5% under 5,000). Under 5,000 m²: 61,880 of 70,684 squares
    (87.5%), median 4 open quests, 16,262 with 0, 495,221 of the squares' 835,530 open on 11-23. 38 of the 41 are under it.
  - Not only squares: 9,157 other places are under 5,000 m² (6,404 neighbourhoods, 2,375 localities, 89 macrohoods, 275
    other microhoods, 14 counties), from a sample of 24 mostly real: RT blocks in Indonesia, farms and hamlets; 4 places are under 1 m² (degenerate outlines, one of them a square). Registry: 334 of 469 squares, and 3 others.
  - A cutoff for squares alone (not for other subtypes) is what the numbers point to; 8,804 squares are 5,000 m² or more
    (Alexanderplatz 78,656; the largest, in Uzbekistan, 7.8 km²). 324 are 50,000 m² or more.
  - Toronto: 12 of 218 parts are squares, 5 under 5,000 m² (Corner Commons, Piazza, Hart House Quad, Olive Square Park, Art
    Centre Square; 64 open quests). Each lies wholly in a neighbourhood. Of the registry's 334: 320 lie wholly inside another
    part of their city that is not a square (any type), 14 in none (one each in 14 cities; only the city page has them).
    `areas_to.py`, `cover.py`.
  - Owner asked for a more aggressive cutoff on Toronto and Guelph (discussion, nothing decided): Toronto's 12 smallest of 218
    are its squares (1,132 to 31,666 m²), the next is Distillery District (51,678); Guelph's 2 squares are 5,444 and 6,889
    m², so a 5,000 cutoff keeps both, 10,000 drops both and 10 of Toronto's 12. Guelph's next is 508,675. Squares under
    10,000 m² in the registry: 407, of which 20 lie in no other part. Proposal: 10,000 m² for squares, no size rule for
    other types (88 non-squares in the registry are under 50,000). Near-duplicates (overlap over 80%): 19 pairs of 4,214,
    6 of them in Guelph, where 18 of 40 parts are "Neighbourhood Group" and the like. `tg.py`, `dups.py`.
  - **Owner (2026-11-24): drop squares under 10,000 m² (67,106 of 70,684), but only if another place covers them; nothing
    built.** Checked against every countable non-square outline (`cover_world.py`, `cover_rep.py`, result
    `cover_world.pkl`): 13,601 lie in a neighbourhood-level place (neighbourhood, macrohood, microhood), 50,199 only in a
    locality or localadmin, 3,297 only in a county, region or country, 9 in nothing (5 Norway, 1 each MX, GI, KR, PH). County
    and above were tested by a point inside the square, the rest by outline (over 95%). Ours: of the 407, 20 are in no
    neighbourhood-level place (Garden Square, Veterans Square and so on), 13 of them in a locality, 7 in a county
    (Kingston, London and others are counties in Overture). Their own city page counts all 20. **Owner (wizard): a
    city or smaller (neighbourhood-level, locality or localadmin) must cover it**, so 63,800 are dropped and 3,306 stay
    (3,297 only in a county or larger, 9 in nothing); ours: 400 of 407 dropped, 7 stay. Not built; the traps above
    (`MAX_DELETE`, `DAY_CAP`, the registry) come first, and the owner's go. **Owner, 2026-11-24: not yet, handoff only.**
  - **Merged into main 2026-11-25, dae1a357 (not pushed):** main's renamed `config/parts` minus 416 parts (400 squares, 16
    twins), ids of `dropped-places.json` translated, whole suite 313 passed, 1 skipped. The name layer, history and publisher
    are the place-ids session's rebuild after it (told; it asked that nobody else runs them). Worktree
    `../sc-open-quests-dropped` can go.
  - **Owner, 2026-11-25: drop the small squares, no review, by a rule in code; the duplicates merge; OSM is left as is**
    (cowork closed: `~/Code/cowork/osm-duplicate-neighbourhoods/FOLLOW-UP.md`). Built on branch `dropped-places`
    (worktree `../sc-open-quests-dropped`, main merged in at 14426bf8): `tools/small_squares.py` (`build`: 63,800 of 81,372
    squares in 1 min 51 s; `prune`: every left-out place out of `config/parts` by GERS id), `config/small-squares.json`,
    `run.left_out_places` (both lists by GERS id) read by `places.py` and `add_parts.py`, DATA-FORMAT "Small squares".
    The registry loses 400 squares in 41 cities (Berlin 219 of 461, Hamburg 62, Montreal 24, Vancouver 11, Toronto 10) and the 16
    twins. 45 tests pass (dropped, parts, places, place_ids; the rename tests now use a temp dropped list).
    **Merge, coordinated with the place-ids session (it asked to wait until its rename is committed and checked):** take main's
    renamed `config/parts`, run `small_squares.py prune`, translate `dropped-places.json`'s `id` and `keeps.id` through
    `data/place-ids/registry.tsv.gz` (old id = first 12 hex of `gers`), whole suite, then the name layer once
    (`places.py build`: about 63,800 places fewer) and the publisher (`--max-delete`).
  - **Duplicate parts, a proposal (owner asked; nothing built).** 19 pairs overlap over 80%. 16 are the same place (overlap 94%
    or more, open counts within 10%); 3 are real neighbours and stay: Bremen-Mitte and Häfen (91%, 16,017 and 4,154 open),
    Bremerhaven Mitte and Mitte-Süd (83%), Shearwater and CFB Shearwater (82%). `dups2.py` lists all 19 with tags.
    Which one to keep, in this order: the parent if one is the other's parent (4 pairs: Cantley Village, Windsor Park,
    Willow Park, Bassins du Nouveau Havre); the one with a wikidata id (Bayview Woods-Steeles, r17311556); the shorter name
    (the other 11: in Guelph the plain name over "Neighbourhood Group" in all 6; Centennial, CFAD Bedford, Dockyard
    Annex, Lawlor Island, Osborne Head). How: one checked-in list of dropped ids with the reason, read by
    `places.py`, `add_parts.py` and the registry's readers, for the squares too; the rule is run once to make the list and the
    list is reviewed, so a later Overture release cannot drop a place by itself. Counts are unchanged. World-wide pairs
    were not measured. Guelph's other 12 groups have an outline of their own (6 share a plain place's name, such as
    Clairfields: 1.3 against 9.1 km²) and stay.
  - **Why there are two (owner's question, 2026-11-24): the pairs are two live objects in OSM, not an old version.** For all 38
    objects the version Overture records equals OSM's at its cutoff (2026-10-13), and all 38 exist in OSM today
    (`osmhist.py`, `osmhist2.py`; OSM API histories). The kinds: Guelph's plain names are one changeset of 2026-08-22 ("Localities
    of Guelph (not to be confused with BIAs created earlier)", City of Guelph Open Data) beside the neighbourhood groups
    of 2025-02-12 (and 2026-08-03); Halifax's military sites drawn in 2019 and again in 2023, 2024 or 2026; Windsor Park and
    Willow Park: a place=suburb multipolygon of 2024-04-05 over a 2019 boundary; Bayview Woods-Steeles in 2024-03 and 2025-02;
    Centennial a 2011 relation and a 2016 way; Cantley Village a 2012 CanVec import and a 2024 boundary; Les
    Bassins du Nouveau Havre in 2017 and 2024. Overture seems to make one division per OSM object (an inference; not documented
    where I looked). Correction: Guelph's plain names are the owner's own edit
    (changeset 187822521, user skfd, from ~/Code/guelph-boundaries), whose README already says the group relations should lose
    `place=neighbourhood`.
  - **Owner (2026-11-24): fix OSM where it should be fixed, in cowork; here, do the proposal.** The OSM side is handed
    to a session in ~/Code/cowork (`osm-duplicate-neighbourhoods/BRIEF.md`; nothing edited in OSM). Here: branch
    `dropped-places` (worktree `../sc-open-quests-dropped`, sparse: config, tools, tests), commit fbd81524, **not merged; its
    own tests and test_parts and test_places pass (27, 2026-11-24 22:41, in the loop's gap); the whole suite and the real
    name-layer build with the list have not been run**: `config/dropped-places.json` (16), the registry without them, `run.dropped_places`, readers in
    `add_parts.py` and `places.py`, `tests/test_dropped_places.py`, DATA-FORMAT "Dropped places". Left: the owner's look at the list, the whole suite at merge, then merge, before `place-ids`, rebuild the name
    layer, publish (16 deletions). Merging makes the next
    daily run stop the series of the 16 and drop their files; the archive keeps the old counts. The squares can use the same file later (`why` is
    `duplicate` now, and the file's checks must learn the new reason).
- **Squares, safety check (owner leans to drop, wants a check so a place like Superilla del Poblenou is not lost; not decided).**
  Size alone fails: median 1,064 m2, 87 are 10 ha or more, among them Tiananmen and empty plazas. Two checks on every square:
  OSM says residential (19 of the 8,892 whose tags were read: 0.5 ha+, or 20+ building quests, or 100+ open) or building
  quests are 20+ and at least half (34); with one that OSM now tags suburb, 46 squares, none in our cities; about 23 look like
  places people live (a guess from names, tags and numbers). Proposed: a list of kept ids, reviewed once by the owner, checked
  again only when the Overture release changes. Blind spot: an estate with neither the tag nor open building quests.
  Superilla: residential, 15.1 ha, 1,345 open (578 tree leaf type); 83% in el Parc i la Llacuna del Poblenou, 17% in el Poblenou (both counted).
  Scripts and pages: `.scratch/parts-vs-world/` (`area.py`, `check.py`, `keep_page.py`, `keep.html`).
- **Squares: left by the owner for another session (2026-11-24). Open there:** drop them everywhere (the owner leans to), the
  safety check and its kept list (`keep.html` has the 46 with maps), Superilla kept or not (proposed: kept), where old links
  go (proposed: the place around). Also open: when to build the five empty-place states (proposed: after the city pages land).
- Name in the mockups: "Appellplatz" was the real OSM name of a square in Berlin (w26443399, beside the defence ministry),
  one of the 41. A bad example; the mockups use Meyerinckplatz now. The place and its data are unchanged.
