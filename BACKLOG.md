# Backlog

Parked ideas and later work, one short entry each; the detail is in the linked journal entry. When one is picked up,
it moves to HANDOFF.md's Next and leaves here.

- **The world's monthly backfill (release 2):** monthly points for the world from 2017-01, as the cities have
  (owner, 11-16). [journal/2026-11-16-release-goals.md](journal/2026-11-16-release-goals.md)
  **History cut rehearsed on Berlin (11-27):** cut-then-slice equals slice-then-cut, every number, at 2017-01, 2020-01,
  2026-09; `complete_ways` drops a few border-crossing multipolygon members that carried no quest there (check on a
  planet canary: lakes and forests across file borders). Planet: cut about 8-10 h, out about 175 GB, **disk peak about
  345 GB** (does not fit beside the world; the history file elsewhere or freed after 12-01), a month about 2.5-3.5 h,
  118 months 12-17 days of this machine. Also found: the cities' monthly points before 11-02 were counted before the
  64.1 repin, a seam of about +0.27% on Berlin. `tools/history_cut_rehearsal.py`;
  [journal/2026-11-27-rehearsing-the-history-cut-on-berlin.md](journal/2026-11-27-rehearsing-the-history-cut-on-berlin.md)
- **That backfill on several machines** (owner, 11-24: "parking this idea for now, will return when less busy"): months and
  plan files share no state, about 15,100 independent jobs.
  [journal/2026-11-24-parked-the-worlds-monthly-backfill-on-several-machines.md](journal/2026-11-24-parked-the-worlds-monthly-backfill-on-several-machines.md)
- **64 or 128 days for the horizon** (owner, 11-27): decide after two or three monthly switches; 128 if a switch has
  slipped or been skipped. Costs one halving more, a rebuilt engine and the europe-west date check again.
  [journal/2026-11-27-the-64-day-horizon.md](journal/2026-11-27-the-64-day-horizon.md)
- **Retire the Python tile store** (owner, 11-16: "write down to return to this cleanup at some point"):
  `tools/stream/tilestore.py` and `tiles.py`, replaced by the Rust `tilestore/`; early December at the earliest.
  [journal/2026-11-16-parked-retire-the-python-tile-store.md](journal/2026-11-16-parked-retire-the-python-tile-store.md)
- **Port the world day's Python steps to Rust** (owner, 11-28: "World day only, later"): the ~8.8k lines of daily
  data work (`world_day`, `world_tier2`, `world_state`, `tier2`, `stream.py`'s pyosmium...) into the `tilestore` binary,
  one step at a time, each proven equal over real days; only steps 11-28's `steps.json` shows still cost after the
  11-26 pools. Glue and the Kotlin engine stay. After the 12-01 cutover and release 1.
  [design/topics/rust-for-the-world-days-python.md](design/topics/rust-for-the-world-days-python.md)
- **Benchmark a native Windows osmium** (owner, 11-16: "lets put benchmarking it into todo"): conda-forge's `osmium-tool`
  for win-64 against the Docker one.
  [journal/2026-11-16-parked-benchmark-a-native-windows-osmium.md](journal/2026-11-16-parked-benchmark-a-native-windows-osmium.md)
- **Other validators' backlogs per city over time** (owner, 11-17: "an expansion sort of feature for distant future"):
  Osmose, KeepRight, `fixme=*`. Not before open quests over time have shipped.
  [journal/2026-11-17-parked-distant-future-other-validators-backlogs.md](journal/2026-11-17-parked-distant-future-other-validators-backlogs.md)
- **The blog:** a draft, `blog/how-streetcomplete-quests-age.md` (owner, 11-17); the site has no blog yet.
  [journal/2026-11-17-blog-draft-how-streetcomplete-quests-age.md](journal/2026-11-17-blog-draft-how-streetcomplete-quests-age.md)
- **Ended places after an Overture switch:** "ended" marking on their pages, successor links, `?in=`, publishing former
  names; for now their files stay frozen (owner, 11-26).
  [journal/2026-11-26-the-overture-release-tool.md](journal/2026-11-26-the-overture-release-tool.md),
  [journal/2026-11-26-the-12-01-switch-to-overture-11-18-0-mapped-not-built.md](journal/2026-11-26-the-12-01-switch-to-overture-11-18-0-mapped-not-built.md)
- **`config/parts` after the switch:** not rebuilt for 11-18.0 (ids are stable; ended parts show as `noFile`); rebuilding
  needs another extract source once the regional fetches stop.
  [journal/2026-11-26-the-12-01-switch-to-overture-11-18-0-mapped-not-built.md](journal/2026-11-26-the-12-01-switch-to-overture-11-18-0-mapped-not-built.md)
- **Statistics on a map** (owner, 11-27: "idea of visualizing stats should be explored later write it down"; "shaded
  design will take a step back"): places shaded by open quests (per km² needs land area published), following the quest
  ticks; the children map of "Place statistics for the whole world". The Map tab is a navigation tool first.
  [journal/2026-11-27-the-map-tab-redesign.md](journal/2026-11-27-the-map-tab-redesign.md)
- **The performance review's leftovers:** not looked at: the Rust `update` (708 s), tier 2 reads (1,074 s), the gate's
  four engines (279 s); the publish's tail; the children uploads may double from 11-30 (a forecast).
  [journal/2026-11-26-performance-review-of-the-traces-and-logs.md](journal/2026-11-26-performance-review-of-the-traces-and-logs.md)
