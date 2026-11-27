## Country rules and time zone by position: built, checked on Europe (2026-11-09)

DESIGN "The whole world", item 3. The Germany prototype had one country and one zone; a world run's cell
crosses both.

- **Country gating by position** (engine 92cc9ab0, `Gating.kt`). A city without `countryCodes` is gated as
  the app gates: OsmQuestController skips a quest type whose countries do not meet the downloaded bbox, then
  `mayCreateQuest` asks `isInAny(position, enabledInCountries)` of each quest. The engine asks the city's bbox
  first (a region holding the whole box, or none touching it, settles the quest for the city) and the
  quest's position only where the box cannot decide, in the main pass, the area pass and for notes. SC's
  `getContainingIds` is conservative in a raster cell that a border crosses, so a box near a border is asked
  per position even when it lies in one country: a lookup, not a count. Typed `countryCodes` mean what they
  meant; the 147 configured cities keep them.
- **A time zone per city** (the `zone` patch on SC's ktx date helpers, `EngineZone`). SC reads "the system
  default timezone" for `today` and for the start of a day; the patch takes a thread's override first, and
  the engine sets each city's zone in both passes. A region run (JVM in its zone) overrides nothing.
  Cities that overlap must share a zone; `--area-unit tiles` needs one. The snapshot's date stays asOf in the
  JVM's zone (UTC for a world run).
- **Cells** (`tools/world_cells.py`): no `countryCodes`; the zone that holds most of the cell's nodes
  (timezonefinder at each 0.05° square of the node grid); a notes clip per file in one pass over the dump;
  the baseline one run per zone, as the daily regions; `plan --cities` for a check without Overture places.
- **The production runs are unchanged:** the four baselines are the daily Europe regions' configuration
  (typed codes, the JVM in the region's zone) on the same extract (same sha256) as the archived 11-08
  snapshots, and all 32 cities equal them in every quest entry and denominator.
- **Tests:** GatingTest (a cell across the Dutch-German border at Enschede and Gronau: AddHousenumber counts
  the German house only, AddAcceptsCash the Dutch bakery only, as two small cells do; typed codes still gate
  the whole city) and ZoneTest (a filter under an override equals a JVM started in that zone, for Auckland,
  Los Angeles and Moscow; two cities in two zones in one run equal each counted alone in its zone). 79 engine
  tests, SnapshotReproductionTest unchanged. ZoneTest sets
  the JVM's default zone while it runs, so the suite must stay sequential in one JVM (it is).

**The check: the Europe clip as cells.** `europe-2026-11-08` (127.8M nodes, the 32 European cities' 20 km
rings, asOf 2026-11-08T00:00Z), `.scratch/world-eu/` (gitignored, about 6 GB with the cut and the clips;
can be deleted). 16 cells of 6.8-9.2M nodes in 2 files, 11 zone names. Cut 2 min, notes clips 5 min,
cells 228 and 231 s (one engine at a time: two at 30 GB each failed on Windows' page file this time, with
49 GB of commit free; the Germany run had managed it), baselines 180 + 71 + 88 + 87 s.

- **Every city within 0.004% of its whole-city count** (app default quests), 18 of 32 exact: far inside the
  owner's 0.1%. In all quests together, 11 cities differ by 1 to 4.
- **What differs:** 1-2 elements of a quest, most of them area quests (AddHousenumber in Barcelona, Budapest,
  Dublin, London, München; AddMaxHeight, AddCrossing, AddBarrierOnRoad, AddBarrierOnPath, AddPathSurface): a
  cell's edge, as Germany's check supposed, or the part's copy of the city polygon, as Athens shows below;
  not dumped one by one. **Bratislava +4 AddCycleway is the gate at work:** the quest is on in Austria and
  Hungary, not Slovakia, and four cycleways inside Bratislava's polygon (Petržalka, Jarovce, Devínska Nová Ves)
  lie where SC's boundary data says Austria; the app shows them there, the typed `["SK"]` city does not count
  them. Athens +1 on three road quests is the check's own polygon copy: dumped, both runs match the same
  13,374 elements inside the city's polygon, and the part's GeoJSON copy of it holds one road more.
- **The zone shows nothing here.** 14% of the clip's nodes lie in a zone whose UTC offset differs from their
  cell's (Toulouse in a London-zone cell, Athens and Sofia in an Istanbul one), yet no difference traces to
  it: at 00:00Z every European zone has the same date, so the cell's zone only moves the hour at which a day
  starts, and with it the few elements last edited in that hour N years ago. A run at another hour, or
  zones a day apart (the Pacific), would show more; cutting a cell along zone lines (the minority zone's
  squares as their own "city") is the remedy if it ever matters.

Next, the owner's: a larger country or a continent stage. Per-file notes clips are large where a file's box
is (f0: 2.3M notes, 1 GB, western Europe's box); clipping to the cells' squares rather than the box would cut that.
