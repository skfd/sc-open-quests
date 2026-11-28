## The Overture release tool (2026-11-26, from 11:20; owner: "lets make that overture release tool")

- **Owner (wizard, about 11:20):** (1) **the HOLD waits for this tool**: world dailies stay paused until it is built and tried
  on 11-18.0; (2) **registry side only** this round (pull, diff against the registry, proposals, the operator's verdicts, a staged
  registry); ended pages, successor links and `?in=` later; (3) **a decisions file, bulk accept by named class, the uncertain rows
  walked through in a session**; nothing accepted without the operator.
- Plan: `tools/overture_release.py` (`narrow`, `propose`, `status`, `accept`, `judge`, `apply`), files in
  `data/place-ids/releases/<release>/` (backed up with the registry, out of `config/` so no site deploy). `apply` writes a
  **staged** registry there; the live one is swapped only at the reseed. Former names in a side file. Population = `mint`'s (every
  division with an area). Proof on 11-18.0 against a copy of the registry; no DuckDB, tests or S3 until the 12:15 city run ends.
- **Built (11:20-11:45): `tools/overture_release.py`** (929a800a, c6f99cdc, the decisions file as plain tab lines, the apply fix
  below); tests `tests/test_overture_release.py` (4: each class, bulk-accept refusals, apply's checks and a rerun keeping minted
  ids, verdicts kept). Its docstring is the procedure.
- **Tried on 11-18.0 against a copy of the registry (11:30-11:43, `--root .scratch/overture-release-proof/releases`, after the
  inputs run, before the city run; DuckDB capped at 1.5 GB):** `narrow 2026-10-21.0 --src data/overture/world` 1,082,287 places (the
  registry's count, 3 s); `narrow 2026-11-18.0` from S3 1,085,945 (84 s); `propose` 12 s: kept 1,080,809, lost 1,478, new GERS
  5,136 (the earlier diff: 1,477 and 5,135 of the countable); rows same-osm 199, same-osm-changed 469, same-name-near 59, contested
  8 (four pairs: duplicates on one OSM object or name), overlap 162 (e.g. Cuando Cubango split into Cuando and Cubango), ended-parent
  581, new 4,405. Gates: no new subtype, 143 of 147 cities by relation as before, NI/UZ/IL lose over 1%, 26 city parts (Toronto's
  24 ridings `same-osm-changed`, Bedford South, Lochdale `ended-parent`), 100 of 63,800 small squares gone. Rehearsed operator:
  every class but contested accepted, the four pairs judged by script (`scratchpad/rehearse.py`, not kept), `apply` 35 s:
  1,086,692 places, 1,085,945 live (= the release), same 731, ended 747 (all with successors), minted 4,405, former names 556;
  `place_ids.py check` 0 problems; every old id with its GUID; Beaches-East York keeps its id, GERS and subtype moved. **The live
  registry's hash unchanged (b3d75207...).** First run of `apply` was quadratic (the registry's GERS set built once a place),
  stopped, fixed.
- **Not built (later, by the owner's scope):** swapping the staged registry in at the reseed (`adopt`: backup, copy, pin bump,
  `small_squares.py build`, `places.py build` into a new folder), ended pages, successor links, `?in=`, publishing former names.
  12-16.0 is the first real use: `narrow 2026-12-16.0`, `propose 2026-12-16.0` (old = the pin), judge, `apply`, back up.
- **The HOLD's condition (tool built and tried on 11-18.0) is met; lifting it stays the owner's**, after the 13:20 check.
- **Corrections to the trial above (11:46, rerun in clean proposals):** a lost place's parent counted as living when it was lost
  too (3 ended places got an ended successor); fixed, only kept places are parents or successors now, tested. Rerun: ended-parent
  **573**, ended-none **8** (the earlier diff's 8 lost places with neither overlap nor a living parent), the rest as above; `apply`
  same 731, ended 747 (739 with successors, 8 without), 0 ended successors (`apply.json` now counts them). The 8 contested rows are
  pairs on one OSM object or one name, so 199 + 469 + 8 is near, not exactly, the 676 of the earlier diff. **Known gap:** same-name
  matching looks only at new GERS ids (59 rows; the earlier 159 included kept places nearby), so a kept place of the same name is
  never offered as a successor. **Backup:** `archive_backup.py --only place-ids` copies the folder recursively, so the releases'
  files go with the registry.
- **12-16.0, the first real use, in order:** `narrow 2026-10-21.0 --src data/overture/world` (the pin's copy, once), `narrow
  2026-12-16.0`, `propose 2026-12-16.0`, read `report.md`, `accept --class ...`, `judge` the rest in a session with the owner,
  `apply`, `archive_backup.py --only place-ids`. The swap-in waits for the reseed.
- **Is skipping a release safe? Measured (11:57-11:59, owner's question; throwaway registry minted from 09-23.1's narrow copies
  in `.scratch/overture-next`, outputs `.scratch/overture-skip-test/`):** one month 09-23 -> 10-21: 1,199 lost, 607 strong
  `same` (51%), contested 7, overlap 132, ended-parent 443, ended-none 10. Two months 09-23 -> 11-18 (10-21 skipped): **2,594
  lost (the two single months sum to 2,677: ids that flicker away and back cancel), 1,305 strong `same` (50%)**, contested 15
  (7 + 8), overlap 276 (294), ended-parent 976 (1,016), ended-none 22 (18). So a skip matches as well, place for place; it is one
  bigger judging session, not a harder one. Needed for a skip: the pinned release's narrow copy (lost places' locations), kept
  in the backed-up releases folder. City parts not meaningful in this test (its ids are not ours).
- **Owner, 11-26 about 12:05, decided: monthly.** "When Overture releases we review and prepare and on first of the month we switch
  it. Most of this should be automated algorithmically, judgement should be agentic with Fable, and only exceptional judgement cases
  go to operator." **This replaces the 11-24 rule** "every match an operator judges, no rule decides alone": now an algorithm
  decides the clear cases, Fable (claude-fable-5-2) judges the rest, the operator sees only exceptions. Switch day: the 1st, at a
  reseed (first 2027-01-01 with 12-16.0). Found: no `anthropic` package, no API key, no `ant` CLI here; Claude Code 2.1.332 is.
- **Owner (wizard, about 12:10):** Fable through **Claude Code headless** (`claude -p --model claude-fable-5-2`, the owner's
  subscription); the algorithm decides **only clear cases** (new, back, same OSM object with same name and subtype, or same OSM
  object with the name or subtype changed and the outlines overlapping well); **the operator gets only rows Fable is unsure of**
  (low confidence, or two runs disagree); the **first switch on the 1st is watched** (2027-01-01), later ones unattended.
- **Owner (wizard, about 12:25):** **the first monthly switch is 12-01 with 11-18.0** (not 01-01 with 12-16.0); the
  operator is reached by **a session the watcher opens** (`SessionCli new --in <repo> --prompt ...`, once a release,
  `operator-session.txt`); **the HOLD stays on** (not lifted after the 13:20 check).
- **Built (12:10-12:30):** `auto` (the clear classes), `agent` (Fable through `claude -p`, two runs a batch), `look`,
  `exceptions`, `watch` (402525435, f1b857365 and the session call). Fable on a 40-row sample of 11-18.0 (12:12-12:17, 5 min,
  about $3 at list prices on the subscription): 39 of 40 taken, 1 to the operator (the same OSM relation already ours under
  another id); it found Armenian communities merged into Goris and Stepanavan by their villages' new parent, dropped Moxico
  from Cuando Cubango's successors. The full 834 rows running since about 12:20 in `.scratch/overture-fable-trial/`.
- **The full Fable trial on 11-18.0 (12:20-13:17, `.scratch/overture-fable-trial/`, 834 rows the algorithm left, batches of
  40, two runs, three at once):** **the owner's Fable limit ran out** partway ("resets Nov 29, 12pm"): 154 rows' runs failed.
  Of the 680 judged: **578 taken** (46 differ from the proposal), **102 to the operator** (76 unsure, 26 runs disagree; by class
  overlap 46, ended-parent 35, same-osm-far 11, same-name-near 5, ended-none 3, contested 2). Real doubts mostly (which
  successor; places whose OSM object only broke for a while, e.g. Warsaw's Bemowo, Estonia's Muusika: they end now and come back
  as `back` -> `revive` when Overture has them again); some because `look` gave no parent ids: fixed. **Fixed:** a failed
  run now leaves its rows for the next run (the 154 reset to unjudged), and `watch` calls the operator only when Fable is done.
- **Task `kk-SCOpenQuests-overture`, daily 09:30 (-05:00) from 11-27:** `overture_release.py watch >> logs/overture.log`
  (conhost headless, 6 h limit). On 11-27 and 11-28 the 154 rows fail again on the limit (resets 11-29 12:00); 11-29's run is
  before noon; **11-30 09:30 is the first that can finish them**, then it opens the operator's session.
- **Owner, 11-26 about 13:30: the judge is the default model at high effort, now and later** (not Fable: its limit).
  `JUDGE_MODEL = "claude-opus-5-5"`, `JUDGE_EFFORT = "high"` (`claude -p --model ... --effort high`), ea0e20ee. The 11-18.0
  results moved from the trial into `data/place-ids/releases/` (registry hash checked equal), backed up; the 102 operator rows
  sent back to the judge once with the improved `look`; 256 rows judged by Opus from about 13:30.
- **11-18.0 judged and STAGED (11-26, 13:30-14:20).** Opus at high effort judged the 256 waiting rows (28 min): 53 left for the
  operator, of which 45 only doubted an ended place's successor. **Owner (wizard): a successor in doubt is not the
  operator's** (`settle_successors`: the first high-confidence answer, else the parent the proposal names, else the first
  answer). The **8 "same place or not" rows judged by the owner**: El Túnel follows its name (same acb3c3b2); Gancho de Camino
  Nº 2 ended to La Poma Nº 2; 15 Temmuz Millet Meydanı ended to the bazaar (not `same`, against the recommendation); Уэлен,
  Кислино, Villa Argentina- Barrio Cervecero, 6 de Julio, San Emilio `same`. `apply`: **1,086,698 places, 1,085,945 live
  (the release), same 725, ended 753, minted 4,386 (+25 whose same proposal was turned down), former names +566**;
  `place_ids.py check` clean; backed up. **The live registry is untouched (b3d75207...).** It goes live only at the 12-01
  switch, which is NOT built (adopt, pin, pulls, small squares, places build in a new folder, the reseed). HOLD stays.
- **State at 16:45 on 11-26 (read-only check; owner: "what's left to do before we resume world dailies?").** The 13:20 check, done
  late: the 11:15 inputs run ended `inputs done` at 11:28 (Europe clip at 11-26 00:00, diff 5188); the 12:15 city run no longer
  exists (task deleted 11:15), so its half of the check is moot. The sc-data delete ended `exit 0` at 15:11. The 14:45 task
  started, logged "held", took no day. No RUNNING, no STOPPED; HOLD still holds the 11-25 note. Main is 2 commits ahead of origin
  (the next `run.py site` pushes). **One day (11-26) is waiting.** Nothing technical is left before the lift; the open
  question is the owner's: does the HOLD also wait for the 12-01 switch (`adopt`), which is not built?
- **HOLD LIFTED 16:58 on 11-26 (owner, wizard: "Lift now, start loop").** The HOLD's note copied to
  `.scratch/anomalies/HOLD-2026-11-25.txt`, HOLD deleted, the loop started through its own task (`schtasks /Run /TN
  kk-SCOpenQuests-planetstore`, so the same command and 12 h limit). It took day 11-26 (`pins: added europe-2026-11-26`).
  Expected about 20:30 plus the publish. **The first world day on the four speed-ups:** check it with the list above ("To check on
  the first world day after the HOLD is lifted"), then `rename_places.py check`. A check is scheduled into this session for 20:45.
  Next to build, in the gaps between days (no builds or DuckDB beside a running day): the 12-01 switch (`adopt`).
- **PAUSED 18:02 on 11-26 (owner, wizard: "i am going offline soon", the laptop goes off: "stop now").** HOLD placed (its note
  names the stop); the task ended (`schtasks /End`) and the loop's two python processes (48792, 7908) killed at a still point:
  no engine alive, tier 2 past `rectangles` (17:53), in a Python step. `RUNNING` is left (pid 7908, gone): the next start logs
  "left by a run that is gone: taking over". The 20:45 check is cancelled. **When the laptop is back (the owner's word):** delete
  HOLD, `schtasks /Run /TN kk-SCOpenQuests-planetstore`; 11-26 resumes from `day.pkl` (store at D: `finish` again, about 2.5 h)
  or redoes the day, then takes 11-27 if its inputs are there. Then the first-day checks above and `rename_places.py check`.
  The 09:30 Overture watcher and the 11:15 inputs run are due again tomorrow if the laptop is on.
- **The same-name gap closed (11-27, about 20:40-21:10, a worktree agent; branch `worktree-agent-a279920b917c3369e`,
  ad66579b0).** A kept place (its GERS id in both releases) can never be a `same` target: `apply` and the judge refuse a GERS
  id that is not new, and two of our places would share one id. So a kept namesake is a **successor**: a lost place with no
  OSM match and no new same-name match, but a kept place of the same name and country within 2 km, is the new class
  **`same-name-kept`** -> `ended <that id>` (same subtype first, then the nearest; not AUTO, so the judge sees it; bulk accept
  allowed; several lost places may end into one kept place, nothing is contested). Where no single OSM match decides a row
  (same-name-near, contested, the ambiguous fall-through), the kept namesake is only added to the candidates with a note; AUTO
  rows, targets and `contested` are untouched. `settle_successors` falls back on the namesake as on the parent; the judge's
  prompt names the case. Tests: 6 in `KeptNamesakes` (the shared fixture's tests unchanged); full suite 448 passed, 3 skipped
  (two tilestore tests skip in a worktree: the Rust binary is built only in the main checkout).
- **What it would have changed on 11-18.0 (measured; nothing in data/ or main's .scratch written):** `propose` rerun with HEAD
  and with the change into the agent's scratchpad (copies of both `places.parquet`, the live registry read only, hash
  b3d75207 as on 11-26). HEAD reproduces the judged `proposals.tsv` (key, class, proposal, candidates) except 5 rows whose
  equal-IoU successors come out in another order (ties, not a change). With the change: **48 lost places gain a kept
  candidate**: 47 become `same-name-kept` (from overlap 32, ended-parent 15), 1 contested row (El Túnel, NI) shows it; 25 of
  the 47 get a different proposal (22 already proposed exactly that place as the best overlap). **47 of the 48 judged verdicts
  already name the kept place** (the judge found it through `look`'s "same name within about 30 km"); the one that does not
  is a generic Japanese 1丁目 whose kept namesakes are other chōme, and the judge was right. So the staged 11-18.0 registry
  needs no rejudging; the change makes the proposals say what the judge had to look up.
- **Corrections to the two lines above (11-27, about 21:20, af0ee9556).** (1) **16, not 48, lost places gain a candidate they
  did not have** (15 ex-ended-parent, the 1 contested): the 32 ex-overlap rows already listed the kept namesake as an overlap
  successor; 22 of them change only class and note, 10 get the proposal narrowed to it alone. 48 is the rows with a kept
  namesake within 2 km. (2) "Already name it" was any mention; **by exact verdict (successors as a set), 43 of the 47
  `same-name-kept` verdicts equal the new proposal, 25 the old** (22 where both are the same). Of the 10 changed ex-overlap rows
  the judge gave the new proposal 7 times, the old 2 (Pacayita, Barra da Lagoa: both successors kept), neither once
  (Ratones: two of the old three); among the ex-ended-parent rows 14 new, 1 old (the 1丁目). So the class keeps its precedence
  over overlap; as a judge row, a bulk `accept --class same-name-kept` would have taken 43 of 47 as the judge did. (3)
  **`settle_successors` is not extended:** a namesake is a heuristic (the 1丁目), not the parent that always covers the place,
  so the rule that settles a doubted successor keeps falling back on the parent only (owner's rule of 11-26 unchanged). (4) The
  fall-through with several new namesakes and a kept one (no 11-18.0 row) got a test. Suite: 448 passed, 3 skipped; without the
  6 new tests (`KeptNamesakes` deselected), 442 passed, 3 skipped (in this worktree).
