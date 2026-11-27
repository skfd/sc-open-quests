## Engine: ready for any country (2026-10-24)

Three of the engine limits listed in "Planet coverage: what was measured", lifted; the
one-time-zone-per-run limit stays.

- **All of SC's country metadata.** `sync-sc.ps1` bundles every `country_metadata/*.yml` SC v64.0 ships,
  515 files (1.2 MB; was 16), and writes their codes to `sc/country_metadata.index`. A region SC has no
  file for is skipped, as in the app; a file SC ships that the bundle lacks now fails the run instead of
  falling back to `default.yml`. A test compares the bundle with the SC checkout byte for byte and
  decodes all 515; Tokyo reads `JP.yml` (left-hand traffic), Sydney `AU-NSW`, `AU`, Houston `US-TX`, `US`.
  The 16 old files are unchanged, so a Canadian or German position reads nothing new.
- **Any number of cities per run.** The area pass kept city membership in a 64-bit mask; it is now the
  id of an interned set of cities (an Int, 0 for none, c + 1 for city c alone). A grid of at most
  512 x 512 cells over the cities' boxes finds the candidate cities of a point, in the area pass and in
  the main pass's `citiesAt` (it tested all 53 Ontario boxes per tagged element). A test runs 80
  synthetic cities and gets each city's counts equal to two runs of 40.
- **Ontario unchanged.** The 2026-10-23 extract recounted with the arguments of the published run gives
  the same 53 cities x 179 quests (9,487 counts, all fields), denominators, notes and tile grid. Under
  `-Xmx16g` the pass took 261-271 s, the old engine under the same heap 282 s, the published run under
  `-Xmx40g` 188 s: the small heap costs about 80 s of collection, the grid and the set ids nothing
  (area pass ways 6.4-7.1 s vs 6.8, nodes 3.7-4.0 s vs 3.9; Toronto 38-46 s vs 50).
- **City ids in any script.** `add_city.py` drops accents (Montréal → `montreal`, Łódź → `lodz`); a name
  that does not transliterate (Москва, 東京都) or a slug another relation holds gets `r<relation>`;
  re-adding a relation keeps its id. Country codes and time zone are still typed by hand.
