## Parked, distant future: other validators' backlogs (owner, 2026-11-17, about 00:10: "an expansion sort of feature for distant future")

- **Idea:** chart other QA tools' open issues per city over time, the same way we chart open quests. Searched
  2026-11-17 and found nobody doing it. Details in PRIOR-ART.md, under "Validators charting their own counts
  over time".
- **Possible sources:** Osmose's daily count per check (`/en/issues/graph.json?item=&country=`; it splits by its
  own regions, so it would need its issue points clipped to our polygons instead); KeepRight's daily dump of
  open errors for the whole planet, downloaded every day (but KeepRight is unmaintained since April 2024);
  `fixme=*` and similar tags counted from our own extracts.
- **When:** not on any release's path. Pick it up only after open quests over time have shipped.
