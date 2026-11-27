## The stream: probed, and the plan (2026-11-09, near midnight)

The owner wants to pursue counting from diffs, perhaps as a stream that takes changesets one at a time. The
aim, in the owner's words: an efficient way to reach daily world processing; this is one strategic idea,
there can be others. It lifts two listed non-goals (real-time updates, solved quests from changesets) as far
as a test goes. Nothing built.

**Probed at 04:31Z on 2026-11-10** (`curl`, a generic client name):
- **Minute diffs are live, about a minute behind** (sequence 7366220, 04:30:50Z). One file: 45 KB, 761 element
  versions of 27 changesets. So the unit to apply is a minute file; a changeset is what a flip is credited
  to, and it can span files. Not yet checked: object order inside a file.
- **The changeset feed is live too** (sequence 7261488): 19 changesets in one minute, 4 by StreetComplete,
  carrying `StreetComplete:quest_type` (AddParkingCharge; SurfaceOverlay, which is an overlay, not a quest).
- **No public before/after source to lean on.** Overpass's augmented diffs answered "at capacity" (502), and
  OSMCha's real-changesets bucket gave 404 for two changesets (one just made, one about a day old). The state
  before an edit is ours to hold.

**Tiers, from the day already measured** (europe-west, the 11-09 dump):

| tier | quests | matches | flips that day |
|---|---|---|---|
| 1: decided from the element alone (filters, 12 hand-ported custom quests) | 153 | 3,236,635 (70%) | 941 (72%) |
| 2: the 40 area quests, which read their surroundings | 40 | 1,387,710 (30%) | 358 (28%; AddHousenumber 175, AddRoofShape 145) |

**What this suggests for the world.** A planet day is 3.9M nodes, 705k ways and 39k relations against 10-11
billion nodes scanned: about two thousand times less to look at.
- **Tier 1 needs no old versions.** The state is the set of open (quest, element) with its position.
  A changed element is evaluated in its new version and its entries replaced; a deleted one loses them. What
  it does need: node positions for a changed way (a location store, about 80 GB flat for the planet, or the
  region files), country and place by position, and a due date per element for the date quests, written by
  the full count, since ageing has no event (a quarter of the measured flips).
- **Tier 2 needs surroundings**, so a store that answers "what lies around this element", or a recount of
  only the cells an edit touched. One neighbour flip in 1,299 says the radius is small; one day does not
  settle it.
- **A full count stays the check**, weekly. Notes: 4 flips of 1,299; whether they have a feed is unchecked.

**Plan, in order.** Each step is checked against the full count of the same day.
1. **Replay 11-08's minute files** (the sequence range from the state files) through tier 1 for europe-west:
   seed from the 11-08 clip, emit (minute, changeset, quest, element, opened or closed). Pass: net events per
   (quest, element) equal the 941 measured tier-1 flips less ageing and notes. Report the surplus (opened and
   closed within the day), which is what a stream shows and a daily diff does not. New engine code: an
   "evaluate these elements" command.
2. **The changeset feed as a second check:** for StreetComplete changesets with a `quest_type`, does the stream
   show that quest closing on the edited element?
3. **Due dates** for the date quests, checked against the 339 aged flips.
4. **Tier 2:** dirty cells or a neighbourhood store, flip for flip against the full count.
5. **Then the world's cost:** state size, the location store, and one planet day through tier 1.

**Other routes to a daily world, not ruled out:** recounting only the cells a day's diff touched (measured
2026-11-06 as tiles: 8.5% of Ontario's nodes, 64% of Hamburg's); an own Overpass instance, which keeps a
planet with augmented diffs (HARDWARE.md: fits 64 GB and 300 GB); a faster scan, now the larger half of a pass.
