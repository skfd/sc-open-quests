## Pipeline: shared extracts and one notes pass (2026-10-24)

Groundwork for counting many places from one planet file (weekly) and the planet history (monthly).

- **A region names its extract.** A region was its extract: one id for the store folder, the
  osm-extracts fetch and the output folder. An optional `extract` key in `config/regions.json` (default:
  the id) now names the store folder and the fetch, and an optional `url` goes to `fetch --url` for an
  extract osm-extracts does not know by name. The region stays the engine run: one time zone, its own
  cities, its own `data/archive/<id>/` and `docs/data/<id>/`, grid and notes clip. So a country across
  time zones, or more cities than one run takes, is several regions over one extract. `download`
  fetches each extract once; a snapshot is matched to its extract by sha256 inside the region's own
  archive, so each region counts a shared extract once and skips it after. Today's twelve regions need
  no change.
- **Notes: one pass for every region.** `clip_notes.py` decompressed the whole 433 MB dump once per
  region (46 s each, twelve a day even on days without a new extract). It now takes many polys
  (`--config`, or repeated `--poly`/`--out`) and writes every clip from one pass: a 1-degree grid of the
  clips' bounding boxes picks the few notes worth an exact test. The first region to need a clip of a
  dump makes all missing ones. 2026-10-24 dump, twelve regions: 102 to 173 s on a busy machine, where
  the old tool took 79 to 140 s for one region at the same time (46 s when quiet). So twelve regions now
  cost about one and a half old single-region passes, against twelve (about 9 quiet minutes) before.
- **The polygon, not its bbox, plus the cities' boxes.** The clip was the poly's bounding box (Ontario's
  reaches deep into the US). It is now the poly itself (holes subtracted, edges in, antimeridian-safe),
  united with the region's cities' bounding boxes padded by 1 km, the engine's own padding. The engine
  reads notes only inside city polygons (hidden quests, the note quest) and counts open notes in each
  city's bbox (the 10,000 warning); Geofabrik's polys are simplified, and `add_city.py` warns about
  border cities whose boundary pokes out of them by metres, so the poly alone could lose a note it uses.
  Against the per-region clips of the same dump: every common note byte-identical, every note in a padded
  city box kept, 77,300 notes dropped (all outside both the poly and every box; Ontario 40,780, British
  Columbia 18,460), 965 added (within 1 km outside the poly's bbox: the regions Berlin 536, Bremen 295,
  Hamburg 133, Alberta 1 at Wood Buffalo). Counts do not move; a snapshot's `notes.open` does, as it counts the clip's open
  notes. Existing snapshots are not recounted for it.
- **The planet history file is a parameter.** `backfill_history.py --planet history-<YYMMDD>`, by default
  the newest in the store's `planet/` folder (today the same `history-261005`).
