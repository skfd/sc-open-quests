## The city run's clean-up, after the world dailies run well (owner, 2026-11-26: "handoff the further cleanup")

The 12:15 task `kk-SCOpenQuests` (`run.py update`) is deleted (11-26) and `docs/data`'s city files end on 2026-11-25
(`config/city-files.json`). What is left of the city run is code, docs and files nobody runs. **Not before:** the HOLD lifted
(the owner's word) and a few world days taken under the new code, each publish showing in `logs/site.log` place files only,
"docs/ and config/ are as deployed; nothing to do", no data commit, main pushed. Before Release 1 (about 12-01) is fine, not needed.

- **Code to take out of `run.py`:** `update`, `download`, `count`, `backfill` and their CLI entries; `publish_site`'s and
  `backup_archive`'s callers once `update` is gone (check what `site` and `inputs` still call first); the `daily.lock`
  wait, if only `update` takes it. **Keep:** `history`, `site`, `inputs`, `planet`?, `check-release`, `migrate-archive`?,
  `dated_extracts` and `read_json` (`tools/backfill_history.py` uses them), `data/archive` and its 2017-2026 history.
- **Tests:** the `download`/`backfill` cases in `tests/test_planet.py` and `tests/test_regions.py`; the rest of the suite must
  stay green (290 + `place-ids`' on 11-26).
- **Scripts and docs:** `schedule-add.ps1`, `schedule-remove.ps1`, README's "Scheduling" part on `kk-SCOpenQuests`, `logs/scheduler.log`
  (keep or archive), REPIN.md's "let the 12:15 run do it", DESIGN.md's daily-run parts (mark as history, do not delete).
- **To decide on the way:** `kk-SCOpenQuests-planet` (disabled; `run.py planet`, monthly) is it still needed for the
  monthly backfill, or does the world store replace it? `tools/add_parts.py` needs another extract source once the
  regional fetches stop. `backup_archive` backs up `data/archive`; does `data/archive-world` have a backup of its own?
- **Disk:** the regional extracts in `~/Code/.osm-data` (Ontario, Quebec, BC, Alberta, the German states, about 55 GB) are
  no longer downloaded and age out on the store's 14-day retention; Ontario is shared with `kk-ontario-update`. Delete nothing by hand.
