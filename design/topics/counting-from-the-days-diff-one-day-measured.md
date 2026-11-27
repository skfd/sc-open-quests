## Counting from the day's diff: one day measured (2026-11-09, late evening)

The owner asked whether the daily diffs, far narrower than a recount, can drive the count: look only at what
each changeset touched. This is the finer form of "recounting only changed tiles" above (2026-11-06): changed
elements, not z14 tiles with a ring. Nothing built. Scripts and output in `.scratch/diff-flips/` (gitignored,
about 900 MB of match dumps; can be deleted).

**The measurement.** europe-west (London, Dublin, Lisboa) counted on `europe-2026-11-08` and `-11-09` with
every match dumped (`--dump-matches`, all 193 quests, the same quests file and notes clip; 106 s and 97 s).
A flip is a quest on an element that is in one dump and not the other. Each flip was held against planet day
diff 5171 (3.9M nodes, 705k ways, 39k relations).

| what explains the flip | opened | closed | share |
|---|---|---|---|
| the element itself is in the diff | 699 | 256 | 73.5% |
| ageing: opened as agedOnly, element untouched | 339 | 0 | 26.1% |
| a note at the element's exact position: 5320352 closed that day (three quests of one shop), 5622513 opened (CheckShopType, way 218331258) | 3 | 1 | 0.3% |
| a changed element within 20 m, not the element itself (AddIsAmenityIndoor, node 302134936; which neighbour was not looked up) | 0 | 1 | 0.1% |
| not explained | 0 | 0 | 0% |

- **4,623,562 matches became 4,624,345; 1,299 flipped, on 742 elements.** 0.03% of the state moved in a day,
  and the full count reads all 128M nodes to find it.
- **Neighbours barely matter, on this day.** The custom quests hold 36% of the matches and 721 of the 1,299
  flips (AddBuildingLevels 212, AddHousenumber 175, AddRoofShape 145), yet all but one were on an element in
  the diff. No flipped way had only a changed node, and no relation flipped.
- **Ageing is a quarter of the flips** and needs no diff: CheckShopExistence alone 322.

**So: yes, as the daily step between full counts.** What it takes:
1. **State:** yesterday's matches per element. The dump is 95 bytes a match as text; about 1.5 billion open
   quests in the world is 15 to 30 GB packed.
2. **Edits:** re-evaluate every element in the diff and what lies within a small radius of its old and new
   place (the one neighbour flip was within 20 m; the radius is not settled by one day). A moved node does not
   re-version its ways, so parents come from the file, not the diff. An engine mode "these elements only, with
   the map data around them" does not exist; SC's `isApplicableTo` returns null for most custom quests.
3. **Ageing:** a main-pass re-evaluation of the 52 date quests, or a due date stored per element.
4. **Notes:** the two dumps compared by exact position (`Notes.hides`).
5. **A full count stays the oracle**, weekly, to reset drift and to catch what this misses; a repin or a
   changed polygon is a full count too.

**The floor.** Since the engine speed-ups, reading is the larger half: of the 85 s pass on 11-09, the scans
of the file took 48 s (member scan, nodes, ways, relations, and the area pass's three) and the cities' area
runs 37 s. A daily step that still scans every region file gains under 2 times; the gain the 0.03% promises
needs a store that finds an element and its surroundings without the scan.

**A byproduct, and a listed non-goal:** every "self" flip names an element version, so a changeset: quests
solved per day, by StreetComplete or by another editor. `changeset` is stripped today (line 54).

**Not shown by one day:** a day with a building or address import; a rural region; a moved node flipping its
way; an element whose position moved across a city or part boundary (still open, counted elsewhere: not a
flip here); denominators; the note quest itself, which the dump leaves out. The diff's ids were taken planet-wide, positions only inside the clip.

**Next, if wanted:** the same comparison over the stored week of clips and all four Europe regions (about 2
minutes a region-day), to settle the radius and the unexplained share. Then a prototype of step 2 on one
region, checked flip for flip against the full count.
