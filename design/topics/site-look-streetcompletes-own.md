## Site look: StreetComplete's own (2026-10-13)

- **Colours from the app's theme** (`ui/theme/Color.kt`): indigo `#4141ba` for the header, the hero tile
  and "needs mapping"; orange `#D14000` (`#ff6600` dark) for "aged"; traffic-sign green and red for
  changes. Rounded white cards as in the app, and its white map pin as the motif.
- **Quest icons and titles.** `tools/sc_assets.py <sc-checkout>` follows each quest class's
  `override val icon` and `override val title` to `res/graphics/quest/*.svg` and the English
  `strings.xml`, writing `docs/icons/` (index.json, the SVGs, SC's graphics `authors.txt`). The table and
  charts name a quest by the question the app asks ("Does this bench have a backrest?"), class name below.
  Icons are CC-BY-SA 4.0, credited in the footer. Rerun on every SC version bump.
- **Releases on the timeline.** `tools/sc_releases.py` writes the stable GitHub releases to
  `docs/data/sc-releases.json`; run it by hand after a release (not in the daily run, to keep that free of
  another network dependency). Pins sit in a strip above each chart: over a long range only major
  versions, each labelled where its label fits and a dot otherwise; hovering one names it and its date.
  They are context only: every count uses the pinned version's quests whatever the date, which the chart
  says under the legend. They are kept apart from the break lines, which mark changes in *this site's*
  counting.
- Both files are optional; without them the site falls back to class names and hides the releases toggle.
- **The chart's ends from its gutters (2026-11-16).** The first and last snapshots sit on the plot's
  edges, and the latest days of daily counts share the last few pixels, so they were hard to hover. Level
  with the plot, the white beside it out to the card's edges (the y-axis and the card's padding on the
  left, the margin and padding on the right) reads out the first and the last snapshot, synced to the
  other charts like any hover; above or below the plot stays off. One document listener, finding the
  chart by its card, since a redraw replaces the charts. On a phone a tap does it 10px or more outside the
  plot; nearer, the browser's tap adjustment puts the tap on the plot itself. The idle legend's
  hold on the last index also kept uPlot from drawing the hover rings when the pointer arrived there;
  the cursor hook now clears it first.
