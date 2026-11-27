## Overture's next release: measured, a process proposed (2026-11-24, evening; owner: "develop a process of updating Overture to the next version")

Nothing built, the pin unmoved. First move ever: we have only been on 2026-10-21.0. Scripts and narrow copies (keep them, the
releases expire): `.scratch/overture-next/` (`diff.py`, `diff.out`, `reid.py`, `d-*.parquet`, `area-*.parquet` for 09-23.1,
10-21.0 and 11-18.0). Read beside the loop at 400-700 MB; its first version wrote 0.75 GB and took the disk to 40.3 GiB, shrunk
at once to 0.28 GB (40.8 GiB).

- **Releases.** Newest 2026-11-18.0 (OSM to 11-09); next 12-16.0, a "major breaking" slot (March, June, September, December),
  nothing announced for divisions. S3 keeps a release 60 days, changelogs for good: 10-21.0 goes about 12-20, 11-18.0 about
  01-17. **Our pull of 10-21.0 is the only copy after that, and no backup list has it.**
- **What a month changes for us** (countable places, OSM relation or way; same size both months):

  | | 09-23 -> 10-21 | 10-21 -> 11-18 |
  |---|---|---|
  | countable before, after | 1,065,942, 1,069,532 | 1,069,532, 1,073,190 |
  | ids gained, lost | 4,789, 1,199 | 5,135, 1,477 |
  | of the lost: the same OSM object under a new id | 527 | 672 |
  | kept ids: renamed, parent moved, OSM id replaced | 770, 843, 197 | 374, 1,135, 213 |
  | kept ids: outline changed | 27,131 | 25,910 |
  | of them: bbox overlap under 90%, under 50% (bbox only) | 1,008, 157 | 1,184, 210 |
  | squares lost, gained | 115, 644 | 114, 569 |

  Quiet months. By the changelog (areas removed): 2025-12 2,236, 2026-01 4,278, 2026-06 25,305 (Czechia, Slovakia), 2026-07
  2,333, 2026-09 3,674. 2026-03 changed 770,003 areas (bbox FLOAT to DOUBLE); 04 and 05 repeated 03's data.
- **A GERS id does not survive a subtype change** (DESIGN.md "Places: naming the world" says it does): no kept id changed subtype
  or country in either month; every subtype move seen is a new id on the same OSM object. 24 ids lost in October are back in
  November. The changelog does not compare `sources`, and has no split, merge or re-id, so it cannot replace our own diff.
- **Our cities on 11-18.0:** all 147 as before by relation (143; bratislava, laval, london-gb, markham go by name or otherwise,
  in all three releases). **27 of 4,214 parts lose their id: Toronto 24 (the federal ridings, OSM retagged them quarter -> ward,
  so microhood -> neighborhood), Halifax's Bedford South, Hamburg's Louis-Braille-Platz, Burnaby's Lochdale (gone).** 26 have
  the same OSM object. 213 parts' Overture outlines changed (theirs are OSM's, so that is only a hint).
- **Where it bites.** (1) `places.py` would not stop on 11-18.0: the same nine subtypes. (2) **The world cannot take a new place
  list between two days**: rows keep a place-set number, only touched elements are placed again, and the gate reads only
  `osm-<city>`, so a swap gives wrong counts and a passing gate. It needs a reseed. One is due about 2027-01-04 anyway
  (area dates reach 11-01 + 64 days, DESIGN.md "a horizon"); **the planet job of 12-07 that was to be it has been off since 11-16**
  (read in the retire section, its plan not looked for further). (3) `geo/` must be built in a new folder: W's registries point
  at `.scratch/world-places/world/geo/`, and `places` writes in place. (4) `world_publish.py` deletes at most 2,000 files,
  no override: 11-18.0 is about 1,560 (1,477 places, 84 of them parents), September to November at once about 2,740. Skipping
  a release, or the squares, stops publishing. Every later day's cache is also thrown away at the pin bump, and the changed
  children files may pass `DAY_CAP` (not counted). (5) A lost id loses its series, its links and its part in widgets; a changed
  outline is an unmarked step in a series; a new place starts at its first day. (6) `gated_days` walks one world folder without gaps.
- **Proposal, OVERTURE.md beside REPIN.md, in this order:** (a) monthly, after a release: `tools/overture_diff.py` (this
  session's two scripts) over narrow columns, no pin moved; report ids, re-ids, subtype, parents, outline overlap, squares,
  perspectives, cities, parts. (b) gates, else stop: no unknown subtype, no 12-hex clash, all 147 cities matched, lost parts
  listed, lost countable under 1% per country (June's Czechia would stop it), schema changes read. (c) **a checked-in crosswalk
  `config/place-ids.json`: a new GERS id on the same OSM object keeps our old place id** when the outlines overlap (a rule run once,
  reviewed), with the dropped-squares and duplicate lists beside it. Lost ids then are about 800, not 1,477, and Toronto's links
  and series stay. (d) pull to `data/overture/<release>/` (about 7 GB; `--out`, never over the old one) and back it up. (e) one
  branch: pin, parts, `places.py`, name layer, `places` and `plan` in a new folder. (f) go live **only with a reseed**, world and
  name layer together, the old world's days kept joined. (g) mark outline steps of 10% or more as `KNOWN_STEPS`.
  Cadence: every release diffed, adopted only at a reseed (about quarterly).
- **Not measured:** how much the 25,910 outlines changed (needs the 4.6 GB of outlines), the cost of the reseed with them.
- **Open for the owner:** which release at the next reseed; the crosswalk; whether a lost place's page stays as "ended".
- **Owner's answers (wizard, 2026-11-24, 20:00):** a lost place's page **stays, marked ended**. OVERTURE.md and `overture_diff.py`:
  **not yet**. Ids: "we should migrate to new ids, whole system including references" (so not the crosswalk as proposed in (c)), and the
  principle is **keep up with Overture and back-migrate our data to it**. Both and the release are **being discussed**. Facts for it:
  - *The ids are public, not only internal*: `?place=`, `?in=`, `?part=` links, the bucket's paths, `docs/places` (4,290 files), 4,214
    `history/<city>/<id>.json`, snapshots, facts, the issue form, the iPhone widget's saved part. No redirect exists. The old -> new map
    (same OSM object) is needed either way: for migration it renames our data, and a small published file sends old links on.
  - *Renaming ids in the past is cheap*: a day's counts name their places in one list (`counts.json` `parts`, 29 MB a day); facts, the
    archive's `parts` keys and the registry likewise. Not built or timed.
  - *Outlines and new places cannot be applied to past days that way*: a day keeps counts per place, not positions (`world.bin` has
    lat/lon and one place-set number, for the newest day only). It needs a recount from the planet at the date, and the history file was deleted
    11-16. Release 2's monthly backfill recounts on whatever outlines are pinned then.
  - *A reseed costs about 4.5 h* (11-01: 23:27-03:49, HANDOFF "Step 3, the seed at 11-01"), so a monthly move with a reseed is
    affordable on paper. Disk and memory as of tonight are not (40.8 GiB, 9 GB of commit).
- **Owner, 2026-11-24, 20:20 (discussion, nothing built):** no recount, **the jump in a series at a move is accepted**; 11-18.0 is skipped
  ("we can skip it and do the reseed on next one", read as 12-16.0). Ids: Overture's will not do, "more permanent ids maybe name based
  or our internal ones?". Starting point, not a command: at each release match places agentically, suggest replacements for
  deleted ones, mindful of widgets, place links and social shares.
  - **Measured for it (`match.py`, 10-21 -> 11-18):** of 1,477 lost ids 676 have the same OSM object, 159 the same name within about
    2 km, 642 neither. Of the 642, 124 overlap some place (bbox IoU 0.2+, 39 of them 0.5+), 518 overlap none, and for 510 of those the
    parent lives on. So judgement is needed for some hundreds a month, not a million. 1,009 OSM objects ended in the month.
  - **Names are worse as ids:** 48,730 places share name and parent with another, 351,901 name and country; 374 renamed and 1,135 moved
    parent in the month.
  - **Proposed:** our own id, the 12-hex ones frozen (every link works today), Overture's GERS and OSM ids being attributes that move.
    Only exceptions are stored (about 700 a month): id, current GERS, OSM object, state (live, ended), successors. `place_id()` in
    `places.py`, `add_parts.py` and `world_cells.py` becomes one function that reads it. Cities already work like this (`toronto`).
  - **Not in the idea yet:** a link carries a second id, `?in=<cc>/<regionId>`; the iPhone widget finds a part by name too (aliases
    for former names); a widget already on a phone knows no new format, so an ended place's file must stay where it is; the Android
    widget has no place code (cities only, by grep); the share-previews branch needs an ended card; splits and merges have several
    successors; an id can come back (24 did); squares and duplicates can use the same list ("covered by").
- **Owner, 2026-11-24, 20:35, decided:** (1) **our own GUIDs, generated, the Overture-derived ids replaced everywhere, published files and
  links included** ("we are in prerelease and can break anything we want including links"); this replaces "the 12-hex ones frozen".
  (2) At a release a match is a **suggestion an operator judges**; ingesting an Overture release is always a manual agent-operator
  job (no unattended adoption, no rule that decides alone). (3) The next release taken is **2026-12-16.0**. Not started: code and rename.
  - **Timing:** Release 1 is about 12-01, so the id change goes **before it** (a pure rename, no reseed: the same places, outlines and
    counts under other ids); Overture 12-16.0 comes after it, at the reseed due about 2027-01-04.
  - **Rename surface (read 11-24):** `place_id()` is written three times (`places.py:41`, `add_parts.py:64`, `world_cells.py:177`);
    `config/parts` (4,214), `docs/places`, `docs/data/{parts,history}`; W's `places.json`, 128 files' `parts/`, `place-sets.json`
    (314 MB), 23 days' `counts.json` (1,018,647 place ids each, beside 688,181 `city:` and 147 `osm-` ones that do not change);
    `data/facts` (3.7 GB), the archive's `parts` keys; the bucket (about 1.13M files: `--full`, and over `MAX_DELETE`); fixtures,
    the issue form, widget. Publisher keys are 48-bit ints (`hexkey`, `idstr`; `app.js:1843`; `run.py:782`): a full GUID as the public
    id needs those rewritten, the first 12 hex of a random GUID, unique by check, does not.
  - **Design:** one registry (GUID, public id, GERS, OSM object, name, subtype, state, successors, since), the only source of a new id,
    backed up to R2 before anything uses it: random ids cannot be derived again. One `tools/place_ids.py` for all readers.
  - **Proof:** after the rename every place's counts equal the old ones under the map, every day, exactly.
  - **Clashes:** `dropped-places` (16 ids, unmerged), `world-cities`, `retire-cities` and `share-previews` all hold place ids; merge or
    translate them first. All of it needs a gap in the loop (RUNNING and starved tonight: 9.6 GB of commit, disk 40.7 GiB).
- **Owner (wizard, 2026-11-24, 20:45):** rename **before Release 1**; public id **the first 12 hex of the GUID**; write the code now;
  the rename, bucket and live site wait for a separate go. **Built, not run and not tested (syntax only): branch `place-ids`**
  (worktree `../sc-open-quests-place-ids`, sparse: md, py, config, tools, tests), a439b588: `tools/place_ids.py` (registry, `mint` once
  only), `tools/rename_places.py` (`plan`, `apply`, `check`), `places.py`, `add_parts.py`, `world_cells.py` read the registry,
  `world_publish.py` (`ids` in its cache stamp, deletes in batches after `latest.json`, `--max-delete`), `archive_backup.py`
  (`place-ids`), DATA-FORMAT, tests.
  - **An open day holds the old ids** (`.scratch/planet-day/world-days/<day>/before/place-sets.json` and the dumps; 11-24 is open):
    resumed after a rename it would bring them back, gate passing. `apply` refuses while a day is open, RUNNING or STOPPED.
  - **Order, in a gap (nothing done):** (1) 11-24 closed, HOLD; whole test suite. (2) Merge or translate `dropped-places`,
    `world-cities`, `retire-cities`, `share-previews`; merge `place-ids`. (3) `place_ids.py mint --src data/overture/world`, `check`,
    `archive_backup.py --only place-ids`, **read it back before going on**. (4) `rename_places.py plan`, then `apply`, then
    `check`; grep W for old ids outside `geometry`. (5) `places.py build` (engine), `run.py history`, `facts.py cities --force`,
    `world --force`, `verify`; every place's counts equal under the map. (6) `world_publish.py build`, `verify`, `upload --print`, then
    the owner's go: `upload --full --max-delete <n>`; **`rclone delete --files-from` first with `--dry-run`, its count must equal
    the plan's** (untried: if the filter were ignored it would empty the bucket). `kk` `daily` fails until then. (7)
    `state_checkpoint.py link`, `upload`; HOLD off; after the first day, `rename_places.py check` again.
  - **Not looked at:** `.scratch/world-places/world/places.json` (the hard-link twin of W's) keeps old ids; `add_parts` and fixtures'
    hard-coded ids; the spend of about 1.13M uploads (`spend_breaker` asks); the widget's and issue form's links, which break as
    decided; memory of `apply` (places.json 395 MB, three copies) and about 1 GB of disk, unaffordable at 40.7 GiB.
  - The GERS-derived ids stay in `gers` and in outline paths. The ingest tool for 12-16.0 (agent proposes, operator judges, ended pages,
    suggested successors, `?in=`, former names) is not begun.
- **Owner, 2026-11-24:** Release 1 **waits** for the id rename; 12-01 is the earliest date it may be considered, not a fixed one. Who
  merges the other branches: "not sure operator will figure it out" (read as: whoever runs the rename decides then).
  Read off the branches for that person (12-hex strings added against main, files shared with `place-ids`):
  `dropped-places` holds ids in `config/dropped-places.json` (both `id` and `keeps.id`; `rename_places.py` config covers it) and shares
  DATA-FORMAT, `add_parts.py`, `places.py` (conflicts likely); `world-cities` in `tests/test_world_cities.py` only (made-up data,
  not checked), shares DATA-FORMAT; `share-previews` in `cloudflare/README.md` and two tests (real place ids in links: **these do
  need new ids**, the rename does not touch them), no shared file; `retire-cities` and `world-stable` none (`retire-cities`
  shares DATA-FORMAT). So `dropped-places` first, then `place-ids`, the rest in any order. Corrects the "Clashes" line above:
  `retire-cities` holds no place ids.
