## Parked: retire the Python tile store (owner, 2026-11-16, about 22:25: "write down to return to this cleanup at some point")

- **What:** `tools/stream/tilestore.py` and `tiles.py` (about 1,400 lines). The Rust `tilestore/` replaced their cut,
  update and read; the live paths (`planet_store_day.py`, `world_cells.py storecut`, `storecheck_cities.py`) already
  run the Rust binary. Quest logic was never in either: it is the Kotlin engine's.
- **Still importing them:** `tests/test_tiles.py`, `tests/test_tilestore_update.py` (Rust update held against the
  Python one on the synthetic day); `tools/stream/tilecheck/` `storecmp`, `subcmp`, `why`, `edge`, `reledge` (Python's
  reader decodes the store); dead or nearly: `chain-z.sh`, `day12.sh`, `overpass/bench.sh`, `opbench.py`.
- **To do it:** a Rust `compare`/dump command (or keep a ~100-line Python decoder) for the tilecheck tools; tests
  against fixtures or osmium instead of Python; delete the dead scripts. Gain at a repin: the tile rule lives in two
  places (`AreaPass.kt`, Rust) instead of three.
- **When:** not before release 1's loop is caught up and checked (subcmp/why are its diagnosis tools); early
  December at the earliest. Not while the release-1 agents' worktrees are open.
