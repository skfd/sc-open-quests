## Blog draft: how StreetComplete quests age (owner, 2026-11-17, late evening)

- Owner: "write an article ... it will go into our future blog". Draft at `blog/how-streetcomplete-quests-age.md`
  (front matter `status: draft`). It covers which quests age, the intervals (from SC's quest filters, counted in
  the `StreetComplete-fast` checkout; the Temp `sc-v64.0` checkout has no sources left), how "older" is decided
  (`ElementFilter.kt` `CompareTagAge`), what an answer writes (`ResurveyUtils.kt` `updateWithCheckDate`), and why
  the site splits resurvey from mapping. No blog exists on the site yet; nothing links to it.
- Owner: "should reference sources in that cool wikipedia way". Now 32 GFM footnotes under "References", each a
  line-pinned link into SC's **v64.0** tag (sources fetched sparse to Temp `sc-v64.0-src`; every link checked to
  land on the cited line). Counts redone on v64.0: 67 of 192 quest types age. Cash and cards aging is on SC's
  unreleased main only (cited at c994ef37) and sits in a "Coming next" note. The draft's numbers are no longer from
  `StreetComplete-fast`, which is main plus the owner's fork.
