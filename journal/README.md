# Journal

History, append-only and verbatim: findings, measurements, how decisions were reached, the owner's words.
Never required reading; [HANDOFF.md](../HANDOFF.md) holds what is live and links here.

Every `##` section of the old HANDOFF.md (at 9064d462e, 2026-11-27) moved here byte for byte, one file per
section, named by the date in its heading. Code comments citing `HANDOFF, "<heading or phrase>"` resolve with
`grep -rn '<phrase>' journal/`. The old headings, in the old file's order (which is not date order):

- [2026-10-11-the-brief.md](2026-10-11-the-brief.md): (the brief: the title line and the sections up to Corrections)
  - Goal
  - What the site should answer
  - High-level goals
  - Non-goals (for now)
  - Suggested first milestone
  - Context
  - Corrections (2026-10-11)
- [2026-10-13-status-and-next-steps.md](2026-10-13-status-and-next-steps.md): Status and next steps (2026-10-13)
- [2026-10-24-planet-coverage.md](2026-10-24-planet-coverage.md): Planet coverage (asked 2026-10-24)
- [2026-11-10-idea-a-phone-widget-for-daily-progress.md](2026-11-10-idea-a-phone-widget-for-daily-progress.md): Idea: a phone widget for daily progress (owner, 2026-11-10)
  - Widget: decided (owner, 2026-11-11, evening), its own repo `~/Code/sc-open-quests-widget`
- [2026-11-10-idea-share-previews-for-links.md](2026-11-10-idea-share-previews-for-links.md): Idea: share previews for links (owner, 2026-11-10)
  - Share previews: proposed architecture (2026-11-10, evening; nothing built)
  - Share cards are in release 1 (owner, 2026-11-24, 04:10: "we will design and implement share cards by release day")
  - General card: the world's numbers (2026-11-25, 13:31; settled by the owner; merged 11-26, see above)
  - Share previews: built on `share-previews`, merged 11-26 (the Worker not deployed) (2026-11-23, afternoon; owner: "build it, i will upgrade account later")
  - Share previews for release 1: decided (owner, 2026-11-23)
- [2026-11-10-countries-in-the-place-index-decided-not-built.md](2026-11-10-countries-in-the-place-index-decided-not-built.md): Countries in the place index: decided, not built (owner, 2026-11-10, evening)
- [2026-11-10-neighbourhood-statistics-what-exists-and-the-questions.md](2026-11-10-neighbourhood-statistics-what-exists-and-the-questions.md): Neighbourhood statistics: what exists, and the questions put (2026-11-10, evening; nothing built)
- [2026-11-10-overnight-work-into-11-11.md](2026-11-10-overnight-work-into-11-11.md): Overnight work, 2026-11-10 into 11-11 (the owner is away; "work all night, one task after another")
  - 2026-11-11, 10:25: the owner is away for a few days: "do it all yourself"
- [2026-11-16-neighbourhood-series-and-the-widgets-toronto-parkdale.md](2026-11-16-neighbourhood-series-and-the-widgets-toronto-parkdale.md): Neighbourhood series and the widget's "Toronto/Parkdale" (2026-11-16, 10:30-11:05; owner: "can we build it")
- [2026-11-16-chart-ends-hoverable-from-the-gutters.md](2026-11-16-chart-ends-hoverable-from-the-gutters.md): Chart ends hoverable from the gutters (2026-11-16, 11:25; owner: "hard to hover first and last point")
- [2026-11-16-what-the-site-shows-a-product-review.md](2026-11-16-what-the-site-shows-a-product-review.md): What the site shows: a product review (2026-11-16, 13:00; owner: "discuss information we display as product designers")
- [2026-11-16-pinned-chart-titles-in-sentence-case-again.md](2026-11-16-pinned-chart-titles-in-sentence-case-again.md): Pinned chart titles in sentence case again (2026-11-16, evening; owner: "was it always there?")
- [2026-11-16-rule-published-counts-cover-every-quest.md](2026-11-16-rule-published-counts-cover-every-quest.md): Rule: published counts cover every quest (owner, 2026-11-16, late evening)
- [2026-11-16-release-goals.md](2026-11-16-release-goals.md): Release goals (owner, 2026-11-16, late evening)
- [2026-11-19-spend-breaker-on-hosting-built.md](2026-11-19-spend-breaker-on-hosting-built.md): Spend breaker on hosting: built (2026-11-19, 10:00-10:45; owner: "make sure there is a spent breaker on hosting. 50 bucks a month max")
- [2026-11-19-world-vs-the-daily-runs-cities-they-agree.md](2026-11-19-world-vs-the-daily-runs-cities-they-agree.md): World vs the daily run's cities: they agree (2026-11-19, late evening; side session)
- [2026-11-21-daily-city-run-down-11-19-to-11-21-geofabrik-moved.md](2026-11-21-daily-city-run-down-11-19-to-11-21-geofabrik-moved.md): Daily city run: down 11-19 to 11-21, Geofabrik moved regions (fixed 2026-11-21, 13:10)
- [2026-11-19-world-places-publisher-built-not-merged.md](2026-11-19-world-places-publisher-built-not-merged.md): World places publisher: built, not merged (2026-11-19, night; owner: "when is it sane to publish world stuff?", then "Yes, build it")
- [2026-11-16-the-place-page-merged.md](2026-11-16-the-place-page-merged.md): The place page: merged (2026-11-16, evening; owner: "pick from handoff ui work", then "merge it now")
- [2026-11-17-r2-cache-test-done-place-data-host-sc-data-set-up.md](2026-11-17-r2-cache-test-done-place-data-host-sc-data-set-up.md): R2 cache test done; place-data host `sc-data` set up (2026-11-17, 02:30; owner at the desk)
- [2026-11-16-parked-retire-the-python-tile-store.md](2026-11-16-parked-retire-the-python-tile-store.md): Parked: retire the Python tile store (owner, 2026-11-16, about 22:25: "write down to return to this cleanup at some point")
- [2026-11-16-parked-benchmark-a-native-windows-osmium.md](2026-11-16-parked-benchmark-a-native-windows-osmium.md): Parked: benchmark a native Windows osmium (owner, 2026-11-16, about 22:30: "lets put benchmarking it into todo")
- [2026-11-17-blog-draft-how-streetcomplete-quests-age.md](2026-11-17-blog-draft-how-streetcomplete-quests-age.md): Blog draft: how StreetComplete quests age (owner, 2026-11-17, late evening)
- [2026-11-17-line-endings-lf-everywhere.md](2026-11-17-line-endings-lf-everywhere.md): Line endings: LF everywhere (owner, 2026-11-17, evening: "we often stumble on LF vs CRLF ... fix it for good")
- [2026-11-17-parked-distant-future-other-validators-backlogs.md](2026-11-17-parked-distant-future-other-validators-backlogs.md): Parked, distant future: other validators' backlogs (owner, 2026-11-17, about 00:10: "an expansion sort of feature for distant future")
- [2026-11-23-parked-until-release-1-is-out-retire-the-daily-city-run.md](2026-11-23-parked-until-release-1-is-out-retire-the-daily-city-run.md): Parked until Release 1 is out: retire the daily city run (owner, 2026-11-23, 12:40: "its ok to wait, add it to the list of work")
- [2026-11-24-city-neighbourhoods-on-the-worlds-counts-and-places.md](2026-11-24-city-neighbourhoods-on-the-worlds-counts-and-places.md): City neighbourhoods on the world's counts, and places with nothing open (2026-11-24, evening; nothing built)
- [2026-11-21-storage-redesign-facts-serving-working-state.md](2026-11-21-storage-redesign-facts-serving-working-state.md): Storage redesign: facts, serving, working state (owner, 2026-11-21, 13:10)
- [2026-11-24-parked-the-worlds-monthly-backfill-on-several-machines.md](2026-11-24-parked-the-worlds-monthly-backfill-on-several-machines.md): Parked: the world's monthly backfill on several machines (owner, 2026-11-24: "parking this idea for now, will return when less busy")
- [2026-11-24-overtures-next-release-measured-a-process-proposed.md](2026-11-24-overtures-next-release-measured-a-process-proposed.md): Overture's next release: measured, a process proposed (2026-11-24, evening; owner: "develop a process of updating Overture to the next version")
- [2026-11-24-legal-pages-the-list-agreed-nothing-built.md](2026-11-24-legal-pages-the-list-agreed-nothing-built.md): Legal pages: the list agreed, nothing built (2026-11-24, late evening; owner: "this website needs terms of use and some other legal stuff like cookie consent")
- [2026-11-26-performance-review-of-the-traces-and-logs.md](2026-11-26-performance-review-of-the-traces-and-logs.md): Performance review of the traces and logs (2026-11-26, 06:15-07:30; owner: "lets review the traces and logs for performance improvements")
- [2026-11-26-the-city-runs-clean-up-after-the-world-dailies-run-well.md](2026-11-26-the-city-runs-clean-up-after-the-world-dailies-run-well.md): The city run's clean-up, after the world dailies run well (owner, 2026-11-26: "handoff the further cleanup")
- [2026-11-26-the-overture-release-tool.md](2026-11-26-the-overture-release-tool.md): The Overture release tool (2026-11-26, from 11:20; owner: "lets make that overture release tool")
- [2026-11-26-the-12-01-switch-to-overture-11-18-0-mapped-not-built.md](2026-11-26-the-12-01-switch-to-overture-11-18-0-mapped-not-built.md): The 12-01 switch to Overture 11-18.0: mapped, not built (2026-11-26, 18:00-18:30; owner: "we are going to do it on 12 01 right?")
- [2026-11-26-the-world-day-resumable.md](2026-11-26-the-world-day-resumable.md): The world day resumable (owner, 11-26, 18:05: "build a resumability please"; the laptop stays on, only the owner is offline)
- [2026-11-27-the-map-tab-redesign.md](2026-11-27-the-map-tab-redesign.md): The Map tab redesign (2026-11-27, morning; owner: "i think map page is not up to date anymore. how do we redesign it")
- [2026-11-28-the-world-day-off-power-throttling.md](2026-11-28-the-world-day-off-power-throttling.md): The world day off power throttling (2026-11-28; owner via osmium-windows-fast: "go ahead and set it up")
- [2026-11-28-rust-for-the-world-days-python.md](2026-11-28-rust-for-the-world-days-python.md): Rust for the world day's Python: surveyed, the owner chose "world day only, later" (2026-11-28, 00:00-00:35)
