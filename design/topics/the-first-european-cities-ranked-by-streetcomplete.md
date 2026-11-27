## The first European cities: ranked by StreetComplete changesets (2026-10-31)

`tools/rank_sc_cities.py` over the changeset dump of 2026-10-26 (`osm-extracts fetch changesets`,
8.9 GB). In the 12 months to 2026-10-26 it found 3.76M StreetComplete changesets worldwide by 41,287
mappers (715k of them from the StreetComplete_ee fork, counted in), 2.93M (78%) in Europe by 29,316.
A changeset is counted where its bbox centre lies inside the city's land polygon (Overture 2026-10-21.0,
a county or region where the city is only a point; London is OSM r175342, Greater London is no Overture
division). The top 40 are exact for the 1,583 European cities and towns of 50,000 and over. The result
is in `data/rank/sc-cities-europe-261026.md` and `.csv`. The top 10: Berlin 36,804 (counted), London
30,709, Hamburg 24,788 (counted), München 20,189, Paris 19,599, Wien 19,510, Praha 17,455, Budapest
15,325, Warszawa 13,942, Kraków 13,565. Bremen is 51st. Caveats: Albacete (21st) is 4 mappers, most of
it the fork; Kyiv, Riga, Salzburg and Moscow have few mappers per changeset. Russia counts west of
60°E and Turkey Istanbul plus Thrace; whether Russia and Belarus belong on the list is the owner's call.
Scanning the dump takes 86 s: it is sorted by id, so a binary search finds the window's start and
only the last 10% is decompressed, in 22 processes.

**The owner's pick (2026-10-31): spread by country, all 32.** The busiest city of each of the
ranking's 28 countries (München for Germany, after Berlin and Hamburg), plus the four second cities
in the top 40: Toulouse, Salzburg, Kraków and Stockholm. Albacete is skipped: 4 mappers. Russia and
Belarus are eligible like anywhere else. They are on branch `europe` (worktree
`../sc-open-quests-europe`, b249b76), kept off main until they count and the site shows them right:
the 13:15 update downloads every region's extract, and `fetch europe` fails until the clip is cut.
- **Four regions, one per time zone, one clip:** `europe-west` (Europe/London: London, Lisboa,
  Dublin), `europe-central` (Europe/Berlin: 20 cities), `europe-east` (Europe/Helsinki: Helsinki,
  Rīga, Kyiv, Sofia, Vilnius, Athens), `europe-msk` (Europe/Moscow: Moscow, Minsk, Istanbul). Each
  group has kept one offset all along since 2017-01, the first month counted: the EU's summer-time
  rules apply alike in each of the first three; Moscow has been UTC+3 since 2014, Minsk since 2011 and
  Istanbul since 2016-09. So a monthly slice is dated the same day in every city of a region.
- **Relations:** the ranking's, except Moscow, whose ranking area is a `place=city` multipolygon. It
  is counted on its administrative boundary r102269 (2,563 km², with New Moscow). Istanbul's province
  boundary is 11,283 km² as drawn (the sea included). Moscow and Istanbul are the biggest areas
  counted yet; if one fails the engine, it is dropped and the rest go on. Oslo's and Athens'
  populations were the metro area's; they are the municipality's now.
- **Country codes** from CountriesTest: Antwerpen `BE-VLG, BE`, Barcelona `ES-CT, ES`, London
  `GB-ENG, GB`; the rest the country alone.
- **The clip:** `tools/clip_polygon.py europe` writes `config/europe.geojson` (the 32 boxes padded
  2 km, unioned: 32 parts, 6.8 square degrees) and each region's `.poly`. Registered as osm-extracts
  clip `europe`; its first `recut` started 2026-10-31 20:10 (log `logs/recut-europe.log`).
