## Rust for the world day's Python: the world day only, later (2026-11-28)

Owner, 11-28 about 00:05: "we need to consider replacing all python code with rust please"; chose at 00:33 "World day
only, later". The survey and its numbers: journal/2026-11-28-rust-for-the-world-days-python.md. Nothing built.

- **Only the world day's data work is a candidate** (~8.8k lines: `tools/stream/` `world_day`, `world_tier2`,
  `world_state`, `tier2`, `store_context`, `stream`, `notes_day`, `planet_store_day` and the rest it reaches, plus
  `world_cells.py`). It goes into the `tilestore` binary, step by step, where the pieces mostly exist: the diff parser
  (`osc.rs`), the node file (`locfile.rs`), the PBF writer. `stream.py`'s pyosmium (`read_diff`, the node lookups,
  `write_small_pbf`) is part of it.
- **The glue stays Python:** `run.py`, the publish, the Overture tool, cloud upload, spend breaker, site and share-card
  scripts. Their time is uploads, DuckDB, the Claude judge and a browser; Rust buys little there.
- **The Kotlin engine stays:** it is the quest logic, pinned to StreetComplete and checked against it (the 11-06 topic,
  "A rewrite in a systems language: discussed, nothing built").
- **Not run daily is deleted, not ported:** the Python tile store (BACKLOG), `proto/`, the Overpass bench and the like.
- **Each step is proven the house way:** its output equal to the Python step's over real days before the Python goes;
  its tests re-pointed to the Rust.
- **Order is decided by measure, not by size:** a step is ported only if 11-28's (or a later clean day's) `steps.json`
  shows it costs, after the 11-26 pools. What Rust may buy: speed on Python loops (tier 1's rewrite, tier 2's delta,
  the diff read, node lookups) and less of the commit the loop's own process takes from the engines (17 GB on 11-24;
  unmeasured). Little for the 558,000 small engine files, which are bound by the file count.
- **When:** after the 12-01 cutover and release 1; builds and equal-output runs in loop gaps or under a HOLD, never
  beside a running world day.
