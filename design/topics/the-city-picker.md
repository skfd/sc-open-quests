## The city picker (2026-11-06)

A dropdown stopped working once the list was the world's: 147 cities in 37 groups that mixed provinces
with countries, Moscow only under "Москва", and no way to the 4,200 counted neighbourhoods or to anything
uncounted. The owner chose a search sheet over an inline type-ahead box.

- **The control.** A button naming the city and where it is; it opens a sheet, full screen on a phone.
  Before typing: recent cities, then counted cities by country, a country listing its cities under its
  provinces. While typing: counted cities, a name match above a place match, a place matching only from a
  word's start ("ber" is Berlin, not all of Alberta). `?city=` is unchanged.
- **Only counted cities are searched here.** The name layer is 1.08M rows, 17 MB gzipped as a flat list and
  8.8 MB for localities alone, so no typing box can hold it. The last row carries the query to the Places
  search, inside the country browsed or else the current city's, because that search has no towns without
  a country. The owner chose this over a site-wide index (about 29 MB more in `docs/`, split by first letters).
- **Names are English, the owner's word.** A city's `name` is its English one (Vienna, Moscow, Krakow); the
  local name stays as an `aka`, because `fold()` strips accents and does not transliterate, so "wien" still
  finds it. Ids stay, so `?city=wien` still works. Quebec's French names (Lévis, Trois-Rivières) are their
  English names too. The 18 are by hand: Overture's `en` has 21 of the 147, some raw ("Copenhagen
  Municipality"), Göteborg none. `add_city.py` takes `name:en` when the relation has one.
- **The Places tab shows `en` first too**, the local name only where there is no English one, and searches
  both. `places/index.json` gained `en` for countries and regions, sorted by it; it was patched from the
  shards, and `places.py build` writes the same.
- **Cyrillic with no English name is romanized**, the owner's choice: 184,099 of the 1.08M names (17%) were
  in another script with no `en`, about 147,000 of them Cyrillic, 116,517 in Russia. `places.py romanize`
  puts them in `en`, by BGN/PCGN letters per country (Г is G in Russia, H in Ukraine); spelled, not
  translated, so "сельское поселение" stays "selskoye poseleniye". The shards were patched with the same
  function. Other scripts stay local: Japanese readings and Arabic vowels cannot be derived from the name.
- **The first city is Guelph, the owner's choice**, for the flavour of it; it was Toronto. A link's city wins,
  then the last city seen on this browser (localStorage). A bare link to the site now shows Guelph.
- **Not done.** Compare still lists every city; the owner put its country filter off. `cities.json` costs
  2.3 KB a city and loads on every page, about 100 bytes of it for the picker: at some thousands of cities
  the picker wants its own slim file. No map picker: no map library, no city centres in the data.
