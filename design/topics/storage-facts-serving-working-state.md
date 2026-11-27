## Storage: facts, serving, working state (2026-11-21, 13:10; owner: "we store data in a shape too close to how we publish it, and do not publish/back it up")

What was wrong. The cities' source of truth (`data/archive/<region>/snapshots/<date>.json`) is a JSON document
nested the way the page wants it. The world's only off-disk copy is the published change-point files
(`place/`, `latest/`), which keep `open` and `agedOnly` only; its counts (`W/counts/<D>/`) and its state (the 128
row files) sit in `.scratch` on one disk, in no backup.

Decided by the owner (wizard, 2026-11-21): all four as recommended.

- **Three layers.**
  - **Facts**: canonical, append-only, backed up, public. One long table for cities and the world alike:
    `date, place_id, quest, open, aged_only` plus the resurvey variants; a `runs` table beside it (one row per day
    and source: SC version, engine commit, source hash, gate result); places and quests as dimension tables. A
    pilot city is a place like any other. Every file is a whole day, never a delta: change points are a serving
    encoding and stay out of the truth.
  - **Serving**: everything the page reads (`docs/data/*` and the world bucket's files, schema 1 or the schema 2
    being built on `world-stable`), built from facts and nothing else. Its shapes are free to change, as schema 2
    does, because nothing else depends on them. Deleting all of it must cost only compute.
  - **Working state**: the 128 row files, the node store, the tile store. A cache with a checkpoint, not a backup.
- **Format: Parquet, read with DuckDB.** One immutable file per source per day
  (`facts/source=world/date=2026-11-13.parquet`). New dependencies: pyarrow, duckdb.
- **Backup:** facts and runs go to the private bucket `sc-open-quests-archive` under the rules it has (copy-only,
  replaced versions kept).
- **Public:** a copy of the facts at `sc-data.comentality.com/facts/`, an open dataset under ODbL with a README.
  World facts are about 113 MB a day compressed (the counts files of 11-19), about 41 GB a year.
- **State checkpoint:** the 128 row files (48 GB for the 11-08 seed; this seed not measured) to R2 monthly, two
  kept, with the diffs since. The node and tile stores are never copied: a planet file and diffs rebuild them.
- **`docs/data` leaves git** after the builders read facts and the byte-for-byte proof has passed. Git then holds
  code and config.

Order of work:
1. Close the hole with no format change: `archive_backup.py` also copies the world's gated days (`counts/<D>/`,
   `days/<D>/*.json`) to the archive bucket. One state checkpoint once the catch-up has ended and a day has closed
   (the loop replaces the row files while it runs).
2. A converter: archive snapshots and world counts to Parquet.
3. The proof: rebuild `docs/data` and the world files from Parquet, byte for byte equal to today's output (the
   builders are already byte-stable).
4. The builders read facts; then the engine and the world day write facts directly.
5. Publish the dataset.
6. `docs/data` out of git.
