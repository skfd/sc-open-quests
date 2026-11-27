## Regions: the rest of Canada (2026-10-21)

- **Why and what.** The owner asked for the whole of Canada. The rule is one that holds everywhere:
  **every municipality of 50,000 or more in the 2021 census** (Wikipedia's list of the 100 largest,
  parsed from the wikitext). 63 cities joined: 58 in eight new regions, and the five Ontario ones the
  farmland list lacked (Clarington, Caledon, Norfolk County, Halton Hills, Aurora); the 11 Ontario cities
  under 50k stay, their history exists. The territories are out: no municipality clears the bar, and
  Nunavut's extract is 1.4 GB for Iqaluit's 7,000 people.
- **A province is a region.** Geofabrik cuts Canada by province, so `config/regions.json` has one entry
  and one `.poly` per province, with its time zone (Quebec counts in America/Toronto, Saskatchewan in
  America/Regina, Newfoundland in America/St_Johns). `~/Code/osm-extracts` knows the eight URLs. The site
  groups the city list by region group, so every province is its own group, Ontario as before.
- **Relations.** Wikidata's P402 (OSM relation id) for each article; 37 of 42 Ontario rows resolved to a
  relation already in config, which checks the method. Five had no P402 (Levis, Repentigny, Saint-Jerome,
  Saint-Hyacinthe, Halton Hills) and came from Nominatim. `tools/add_city.py` fetched each boundary and
  checked it against the province's `.poly`. Populations are StatCan 2021 (`populationSource`); North
  Vancouver is two cities, the city (`north-vancouver`) and the district (`north-vancouver-district`).
- **Country metadata.** SC ships a `CA-<province>.yml` for all 13 provinces and territories, and its
  boundaries give a Montreal position `CA-QC`, `CA`, so `sync-sc.ps1` now bundles all 13 (it had CA-ON
  only); the engine's tests cover Montreal (`officialLanguages: [fr]`, `hasBicycleBoulevard`) and
  Vancouver, and accept `CA-<province>` and `CA` for every city. Montreal's quest gating equals
  Toronto's: none of the 14 quests the app withholds in Ontario distinguishes provinces. German counts
  did not move by a single quest from bundling the files.
- **Cost, measured** (v63.4 engine, 40 GB heap, 24 threads): Ontario with 53 cities 305 s and a 41 GB
  peak (was 196 s, 33 GB with 48; the four large rural municipalities are most of it), Quebec 19 cities
  109 s / 29 GB, British Columbia 20 cities 90 s / 24 GB, Alberta 10 cities 63 s / 23 GB, the five
  small provinces 10 to 22 s each. A full count of the twelve regions is about 13 minutes; the eight
  new extracts are 3.4 GB a day (about 10 minutes to download here) and about 48 GB in the store at the
  14-day retention. The planet history was clipped to all eight provinces in one osmium pass (1 h 4 min;
  Quebec 1.6 GB, British Columbia 1.7 GB, the rest 0.1 to 0.3 GB each). `backfill_history.py`'s quiet
  window around the 13:15 run is now 12:55 to 13:50.
- **History.** The overnight job (`.scratch/canada-backfill.sh`) counts the eight provinces' months
  2017-01 to 2026-10 and recounts Ontario's and Germany's published snapshots, all with v64.0 (merged the
  same evening), so one registry holds everywhere and the chart needs no "+8 types" break. Ontario
  dailies whose extract is gone and that lie after the history file's end (2026-10-06) keep their 48-city
  counts; the five new Ontario cities have monthly points to 2026-10-01 and dailies from 2026-10-07.
