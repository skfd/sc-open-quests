## Questions on the 12-01 switch, old daily data and the 64-day horizon (2026-11-27, evening; a talk, nothing built)

- The owner asked again what happens on the 1st and why (the 12-01 switch to Overture 11-18.0), then why the switch is
  monthly, then what happens to daily data more than a month old. Found: nothing; no retention rule exists anywhere
  (publisher, backup, switch, design). The 28-day window is only the children files' comparison and the 4-week tile.
  **Owner: "let's keep daily data i dont mind."** Written into design/topics/storage-facts-serving-working-state.md.
- **The 64 days** (`AREA_DUE_DAYS`, `engine/src/main/kotlin/openquests/AreaPass.kt:44`): picked 11-13 with no reason
  written down. The owner: "since it is not a completely explained number. 64. lets brainstorm". Brainstormed:
  - Raising it buys slack for a late or skipped switch, at one halving per doubling (dating is about 5 s of a 71 s
    engine pass on europe-west, so cost does not decide it); against: more exposure to the design's unchecked
    assumption (a quest that opens and closes again within the horizon), little gain while each StreetComplete release
    reseeds anyway, and 64 is the only value validated (`AreaDatesTest`, `europe-area.sh`, `areacheck.py`).
  - Lowering it saves nothing real, and under 31 a switch on every 1st cannot keep up.
  - Numbers: 31 (longest month), 32, 60 (Overture keeps a release 60 days), **62 (two longest months in a row: a monthly
    switch with one skipped)**, 64 (the smallest power of two over 62), 92 (three months; the 11-24 quarterly proposal),
    128 (the same 7 halvings as 92; covers three skipped switches, the longest four months being 123 days), 366.
  - No tool checks the horizon (grep of tools/ for `areaDueDays`, `horizon`: nothing): past it, counts drift low
    silently.
  - Proposed and **agreed by the owner ("agree")**: keep 64 through 12-01; a guard after the switch (warn 7 days
    before, refuse to publish past it); decide 64 or 128 after two or three monthly switches; the "one skipped month"
    reason written into design/topics/area-quests-dates.md. Both items in BACKLOG.md.
- Then: "you said each new version of streetcomplete makes us recount. why? can we do it only in some cases?" Answered
  in the session (the state's rows are one quests file's; only touched elements are recounted daily); options in
  the session's reply, nothing decided.
