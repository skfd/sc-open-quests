## Countries in the place index: decided, not built (owner, 2026-11-10, evening)

The owner asked whether the regional division is controversial. It was Overture's default view as
shipped (Western Sahara wholly Moroccan, no Palestine, stateless places dropped). Decided: countries
come from SC's own `boundaries.ser`, every country it names at a place (Crimea under both UA and RU),
the top level named as SC names countries (the platform's CLDR names, in the browser `Intl.DisplayNames`), except that `PS` is named "Palestine" (CLDR's short form); borders are always SC's; a disputed place (SC names two countries, or SC and Overture disagree) goes under every one of them, inside its Overture region each time; names are OSM's `name` tag; English names only from sources (Overture `en`, then Wikidata), no home-made romanisation; places SC files under no country are left out; never flags; a note says the site files places where StreetComplete
applies a country's rules and takes no position on borders. DESIGN.md, "Countries in the place index:
StreetComplete's, not ours", has the probe results and the build steps. Next: build it, measuring first
how many places move.
- **Owner's answers (2026-11-10, late evening):** per-place images, yes (rendering is local, serving
  static assets is free); **regenerated monthly**, on the 1st with the monthly history point, and the
  page's text tags on the same day so title and picture never disagree (both say "as of 1 Nov").
  **Readable addresses** (`/toronto/agincourt-north/`, slug frozen). The file budget against the archive
  was explained; packing the archive per region and month (16 files a month, not a day) would let both fit.
- **Next session (the owner, 2026-11-10):** neighbourhood statistics. Settle there how the archive is
  published (bundled per region and month or otherwise), since neighbourhood series, the neighbourhood
  cards' trend line and the widget all read it; then the share previews follow.
