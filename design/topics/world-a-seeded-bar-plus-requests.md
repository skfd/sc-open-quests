## World: a seeded bar plus requests (2026-10-30)

The owner's answers to "are we ready to build all the places in the world":

- **Both roads.** The biggest cities of some countries are counted up front, chosen by a bar, and
  any other place is counted when a player asks for it. This replaces "only requested places get
  counted" from 2026-10-24. The bar and the countries are still open.
- **Any place with a polygon can be requested:** a town, a village or a county. No population floor.
- **The first planet-counted places are actively mapped European cities.**
- **Current numbers come from the daily planet diffs.** The history file is still rewritten once a
  month, but the daily diffs are downloaded every day and used for the current counts. How to do that
  cheaply is still being discussed (below).
- **Not built yet:** nothing turns a place id from the request form into a counted region.
  `add_city.py` needs a Geofabrik extract id, country codes and a time zone typed by hand.

**Proposal for the current counts (under discussion).** Once a month, right after the history
rewrite, cut a *current clip* from the new history file: its last state inside the counted places'
envelopes, padded, with `-s smart` so multipolygons keep far members. Every day, apply that day's
diff to the clip (`osmium apply-changes`, no `-H`), re-clip it to the envelopes (the diff carries the
whole world's edits), and count. Ontario's 1.98 GB clip took 66 s with two diffs, so a European
city set should take a few minutes a day. The next month's cut from the history file throws the clip
away, so errors last a month at most.
The risk is the clip's edge. Say a diff moves a way inside our envelope and the way uses a node that
lies outside the clip and was not edited. The diff does not carry that node, so we lack its
position. `osmium check-refs` counts such missing nodes each day. Berlin, Hamburg and Bremen are
already counted daily from Geofabrik, so a week of both side by side gives exact answers to check
against.

**The owner's second answers (2026-10-30, early morning):**
- **Test the clip-plus-diffs plan before building on it.**
- **osm-extracts owns it:** a daily planet-diff fetch, and a current clip of given boxes kept up to
  date by those diffs, as a store product. Other projects can use it. Only osm-extracts downloads into
  the store, as before.
- **Choose the European cities by StreetComplete edits:** rank them by StreetComplete changesets in
  the last 12 months, from the changeset dump (every changeset carries `created_by` and
  `StreetComplete:quest_type`). Show the owner the top 10-20 before counting.
- **The seeded bar waits for the European pilot:** pick it from what a city really costs on disk, in
  time and on the site.

**The test, replayed rather than waited for.** The history file holds the true state of every past
day, so a week need not pass in real time:
1. Clip `history-261029` around Berlin, Hamburg and Bremen in one planet pass. Pad the clip about
   20 km, so a padded `-s smart` cut taken from it equals a cut taken from the planet.
2. Take the state at 2026-10-05T00:00Z from that clip and cut it to the counted places' padded
   envelopes. That is the starting clip.
3. No download: each day's diff is derived from the history clip itself (`osmium derive-changes`
   between the slices of day D-1 and day D). The owner's point: the history file already holds
   every version. Like a real diff, a derived diff carries only what changed, so the clip's edge is
   tested the same way. It lacks edits more than 20 km out, which cannot reach the counted area.
   Real diffs are first used when this goes live, and are checked against Geofabrik then.
4. For each day, apply its diff to the clip, re-clip, run `osmium check-refs`, and count. Compare
   each day with the true slice of the history clip at the same moment.
That gives 24 days of drift, close to the month a clip lives, and it can be done in one unattended
run. The Geofabrik dailies of the same cities are a second check.

**The test's result (2026-10-30, 04:30 to 12:02).** Berlin, Hamburg and Bremen, 24 days each
(2026-10-05 to 10-29). Each day's diff was derived from the history file and applied to the clip, and
the clip was compared with a fresh cut of the true state at the same moment
(`.scratch/diff-replay/replay.py`, results in `data/backfill/replay/results.jsonl`):

- **Every count matched, every day:** 72 region-days, all city × quest counts and denominators equal.
  That is about 1.11M open quests in Berlin, 569k in Hamburg and 324k in Bremen.
- **Objects:** Berlin (11.88M) and Bremen (4.26M) matched exactly on every day. Hamburg is the one
  edge case. On 2026-10-06 at 23:33 an untagged way, 1125039855 (94 nodes, likely a multipolygon
  member), was edited so that 17 of its nodes lay outside the clip. Those nodes were not edited
  themselves, so the diff did not carry them. From 10-07 on, the clip lacked those 17 nodes; `check-refs`
  reported "Nodes in ways missing: 17", the fresh cut had 0, and no count moved. The gap did not
  grow over the next 22 days. It was fixed at the next monthly cut.
- **So:** the plan holds. The one failure is rare, `check-refs` reports it, and it clears at the
  monthly re-cut. To close it sooner, a day with missing nodes can fetch exactly those nodes
  (`/api/0.6/nodes?nodes=...`, a handful), or the clip can keep a wider ring than it counts. Not built.
- **Costs measured:** the planet pass took **3.2 hours** (11,608 s; three bbox clips `--with-history -s
  complete_ways` of the 159 GB file), not the hour estimated. So cutting clips for requested places
  must be batched, preferably with the monthly rewrite. Clips: Berlin 146 MB, Hamburg 159 MB, Bremen
  49 MB. The derived diffs were only 0.3-0.7 MB a day, because they cover the 20 km ring only. A real
  daily planet diff is about 100 MB of the whole world. Applying it to a small clip is unmeasured;
  Ontario's 1.98 GB clip took 66 s with two diffs.
