## Countries in the place index: built on branch `countries`, not merged (2026-11-11, overnight)

Built as decided above, measured, and left on the branch for the owner: it rewrites `docs/places/`, and
nothing that rewrites published files rides the first cloud-synced run before the flip.

- **Engine `regionids`** (`RegionIds.kt`): SC's region ids at each point, the same lookup that gates
  quests. 1,082,287 points in 4.5 s. `RegionIdsTest` pins the probed points (Toronto `CA-ON,CA`,
  Simferopol `UA-43,RU`, Laayoune `MA`, Tifariti `EH`, Ramallah `PS`, Senkaku nothing).
- **The point is Overture's label point:** a division's own `bbox` is its point rounded outwards to
  float32, so its centre is the point (checked against the `geometry` column pulled once from S3: the
  same answers). No polygons are needed.
- **`places.py`:** countries per place = SC's at its label point (a code's part before the hyphen) plus
  Overture's `country` unless a placeholder; a region, county and anything below also takes the
  countries of the places below it, so a chain is whole (Overture's "Western Sahara" region gains `EH`
  from Tifariti, the Crimea region `RU` from its towns); country and dependency roots take only their
  own. Filing under a country that is not the place's own: inside its own root when that root is
  under the country too (United States > Puerto Rico > San Juan; Palestine > Gaza Strip > Gaza; Russia >
  Kunashir), else inside its Overture region. Places neither source files are left out (12, the
  Spratly reefs among them). Romanisation is gone; Wikidata English labels and OSM `name` tags are not
  done yet (the planet extraction is its own job).
- **Site:** the country level is named by `Intl.DisplayNames` (Palestine by the short form), sorted by
  that name; the borders note beside the country list and in the footer. A country no Overture
  division heads opens by its code (`?place=ps`). Checked headless: 255 countries; Russia lists Crimea;
  Palestine, Western Sahara, the Canaries and Ceuta & Melilla open with their regions; Palestine > Gaza
  Strip and United States > Puerto Rico > San Juan open; no console errors.

**Measured (Overture 2026-10-21.0, 1,082,287 places):** 1,075,781 agree with Overture's country at
their own point; 6,846 are filed differently, 6,333 under two or more countries. 272 index countries
become 255: the 23 placeholders go, and `AC`, `EA`, `EH`, `IC`, `PS`, `TA` arrive. The big moves are the
decided ones: Crimea (1,176 places also under Russia), every dependency also under its sovereign as SC
names both (Puerto Rico 1,655 under the US, Curaçao 275 and Aruba 94 under the Netherlands, French
Polynesia 268 under France, the Faroes and Greenland under Denmark, Hong Kong 140 and Macau under China),
the Canaries under `IC` and Ceuta and Melilla under `EA` as well as Spain, the West Bank and Gaza under
Palestine, Golan under Israel, Kunashir and Iturup under Russia. `.scratch/countries/` has the full
lists (`measure-labelpoint.log`, `index-diff.txt`).

**Border noise: decided (Claude, with the owner's "do it all yourself", 2026-11-11 10:20).** The first
build showed about 150 regions under a neighbour with 1 to 18 places each (Canada > Maine, Ireland >
Northern Ireland, the UK > Donegal), where a label point sits on SC's simplified border. Its signature:
SC files the point only under other countries, yet files ground within 3 km under the place's own
Overture country. Such a place keeps its own country only (`on_the_line`, `RING_KM = 3`, 8 points; 360
places tested, 2,880 lookups). Real cases do not look like that: Tifariti has no Morocco near it, and SC
names both countries in Crimea, Puerto Rico and Gibraltar. Nothing loses its own country. After it,
6,238 places are filed differently and 5,725 under two or more countries; the noise entries are gone,
and about 15 entries of 2 to 5 places remain (Pando, Rivera, Omsk, Tuva, Amur: places more than 3 km
inside SC's line, unexamined).

**What SC's own data says and stays:** Gibraltar under Spain as well (`GI, ES-AN, GB`), Japan > Senkaku,
Korea > Liancourt, China > the Paracels, and **Matsu (Lienchiang, 27) and 4 Kinmen places under China**:
SC's boundaries give Nangan `CN-FJ, CN` (Kinmen town, Penghu and Taipei `TW`), so the app applies
China's rules on Matsu. That is an error in SC's data, not noise; a report for countryboundaries is
drafted in `.scratch/countries/upstream-matsu.md`, not posted (it would go out in the owner's name).
