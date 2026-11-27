## The place page: merged (2026-11-16, evening; owner: "pick from handoff ui work", then "merge it now")

**Owner, 11-16 late evening: accepted, but the design is preliminary and not reviewed by the owner.** The direction
is right, and processing places (city down to neighbourhood) is genuinely valuable. So treat the layout, tiles,
wording and tab structure as a first draft open to change, not as decided design; build on the direction.


- **Merged into main from branch `place-page`; the next scheduled run publishes it.** DESIGN.md, "The place page".
  One page for a counted city and each of its parts, reading the part series; the chart opens on 90 days ("All since
  2017" in the link), steps marked (Toronto's 2026 import named), density tiles replaced by the 4-week change
  (mapping vs resurvey) and the most-open quest type, zero rows folded into "N quest types done here", the phone
  table fixed, `app.js:1506`'s stale line gone with the old part cards. Tabs: Places, Compare cities, Map (the owner
  approved the collapse). Widget links (`?place=&in=`, `?city=`, `&pin=`) all land on it. Checks:
  `.scratch/place-page/drive.py`, `clicks.py` (serve `docs/` on 8767), `fixtures.py` (serve the repo root on 8769).
- **Data:** `run.py history` now writes `place`/`in` on each city in `cities.json` (146 of 147; London, GB has no
  row). A full rebuild into `C:/tmp/pp` changed only `cities.json`. Not committed by hand: the first daily run after
  the merge writes it. Until then the page shows "Ontario, Canada" as text instead of the linked chain.
- **Left from the review, not done:** sort ticked quests first in the table (Toronto's opens on two unticked rows
  bigger than the total), the class name moved off each row, the shorter phone header, relative dates elsewhere.
  Compare's table scrolls sideways on a phone (it did before too). The 90-day chart's y axis starts at 0, so a
  city's month barely moves the line; worth revisiting if the change should be visible.
- **Repin rule: forward from the release date (11-16, evening; owner: "forward from release day agreed").** REPIN.md
  step 6: at a repin each region's snapshots from the release's publish date on are recounted
  (`backfill_history.py recount --region R --since DATE`, then `merge`), from the extracts the store keeps 14 days;
  nothing older changes, so the release shows as a step on its date. The repin issue now says "within 14 days".
  A full recount from history is the on-demand exception (a history download first). Found and fixed on the way:
  `backfill_history.py`'s count did not pass the parts registry, so a merged recount would have dropped every
  snapshot's parts; now it does (Bremen 11-14 and 11-15 recounted equal to the published, parts included).
