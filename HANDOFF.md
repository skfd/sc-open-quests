# Handoff: sc-open-quests

Read first. This file holds only what is live, **rewritten in place** (never appended to); every item says "as of"
when it was last true. The story behind each item is in [journal/](journal/README.md). What the project is for:
[README.md](README.md), "Goals" (the original brief, verbatim). Release 1 = daily world updates with 30 published days,
12-01 the earliest date (owner, 11-24); release 2 = the world's monthly backfill
([journal/2026-11-16-release-goals.md](journal/2026-11-16-release-goals.md)). Standing rule: anything published counts
every quest, never an easier subset (DESIGN.md, "Don't").

## Now

- **World dailies running again (as of 11-27 09:21).** The owner, 09:20: "start the day"; HOLD moved to
  `.scratch/planet-cut/hold-history/HOLD-lifted-20261127-0921`, `kk-SCOpenQuests-planetstore` run by hand (daily 14:45,
  12 h limit). 09:20 log: "day 2026-11-26: resuming": the finish is skipped (R2's), then gate, store_tail, facts, publish,
  and 11-27 if its inputs allow. **11-26 done 09:33 (117 GiB free after store_tail), published 09:48 (exit 0)**; "no diff
  to 2026-11-27 on disk yet", so 11-27 waits for 11:15's inputs and the 14:45 run (a day needs 115 GiB free). Stop: put back a HOLD (no day) or PAUSE (stops the running day at its next step).
  [journal/2026-11-26-the-world-day-resumable.md](journal/2026-11-26-the-world-day-resumable.md)
- **The world day is resumable and proven (as of 11-27 05:05; built c3b998fd1).** A finish stopped anywhere and resumed ends
  byte for byte where an uninterrupted run on the same engine outputs ends (R1, supplement C: 263 of 263); a late stop costs
  about 18 min, not the 2.8 h finish. Two clean runs of a day can number its new place sets differently (B against R2: equal up
  to numbering), cache or not. **Day 11-26 is finished under the HOLD**: the world is R2's uninterrupted run, `finished`
  written; the loop's next start resumes it at the gate, then store_tail and publish. PAUSE: `.scratch/planet-cut/PAUSE`
  (none placed). Outputs in `.scratch/resume-proof/` (RESULT*.txt, proof.log, canon.py).
  [journal/2026-11-26-the-world-day-resumable.md](journal/2026-11-26-the-world-day-resumable.md)
- **Task `kk-SCOpenQuests-overture`, daily 09:30 from 11-27 (as of 11-26 13:30):** `overture_release.py watch >>
  logs/overture.log`. 11-18.0 is already judged and staged, so it should find nothing new before 12-16.0 (unconfirmed
  until its first run). It opens an operator session (SessionCli) only when the judge leaves exceptions.
  [journal/2026-11-26-the-overture-release-tool.md](journal/2026-11-26-the-overture-release-tool.md)
- **Task `kk-SCOpenQuests-inputs`, daily 11:15 (as of 11-26):** `run.py inputs` (Europe clip, diff, notes) then
  `run.py site` for what the loop could not publish; `site` **pushes main** even when nothing deploys (main was 19
  commits ahead of origin at 01:20 on 11-27). Log `logs/inputs.log`, `logs/site.log`.
- **Gone or off (as of 11-26):** the city run's task `kk-SCOpenQuests` deleted 11:15 on 11-26 (the world's day counts the
  cities; `docs/data`'s city files end 11-25, `config/city-files.json`); `kk-SCOpenQuests-planet` (monthly) disabled.
  [journal/2026-11-26-the-city-runs-clean-up-after-the-world-dailies-run-well.md](journal/2026-11-26-the-city-runs-clean-up-after-the-world-dailies-run-well.md)
- **Worktrees (as of 11-27):** `.claude/worktrees/agent-a9b152efd4c2e1246` (P3's 28.6 GB rehearsal data, kept for three
  traces) and `../sc-open-quests-place-ids` (branch `place-ids`, merged). Leave both.

## Waiting on the owner

- **Lift the HOLD and start the loop** (as of 11-27 05:05: the proof is done). 11-26 is finished; the next start resumes it at
  its gate, then 11-27 if its inputs are there.
- **Keep-awake for the loop (as of 11-26 22:55; proposal, not built):** the loop holds a "system required" power request
  while RUNNING exists; today a day on an idle or unplugged laptop stands still in Modern Standby.
  [journal/2026-11-26-the-world-day-resumable.md](journal/2026-11-26-the-world-day-resumable.md)
- **The share-preview Worker's deploy** (`cloudflare/wrangler.previews.jsonc`, deployed by nothing scheduled) needs the
  owner's go and the $5 Workers limit question (past it the home page fails with error 1103) (as of 11-26).
  [journal/2026-11-10-idea-share-previews-for-links.md](journal/2026-11-10-idea-share-previews-for-links.md)
- **The crash files in the repo root** (`hs_err_pid*.log`, `replay_pid*.log`, untracked, 11-23's engines, diagnosed) may go
  when the owner says (as of 11-26).
  [journal/2026-11-26-performance-review-of-the-traces-and-logs.md](journal/2026-11-26-performance-review-of-the-traces-and-logs.md)

## Next, in order

1. **The 12-01 switch is prepared and rehearsed (as of 11-27 10:40); waits for the owner's sign-off and a start time.**
   `prepare 2026-11-18.0` done 10:26 (every step; `status` shows them): 1,073,190 places, plan check equal (128 files,
   2,244 cells), partcache 5.8 GB. Canary rehearsed on f47 at 11-26, old against new place list on the same cut
   (`.scratch/switch/2026-11-18.0/canary.py`, `REPORT.txt`): 212 of 13,405 parts differ (1.6%), open quests +0.015%.
   Publish: the name layer changes 729 place files and at most 563 children files; 630 published places end (kept
   frozen); with ~1.6% of places moving, the first day after the switch is about 16k files above a normal day's ~60k,
   under DAY_CAP 200k (estimate; the events cache rebuilds once, the release stamp changes).
   [journal/2026-11-26-the-12-01-switch-to-overture-11-18-0-mapped-not-built.md](journal/2026-11-26-the-12-01-switch-to-overture-11-18-0-mapped-not-built.md)
2. **The first world day after the HOLD is lifted (take 11-27, not 11-26: 11-26's finish ran in the proof, its lines are in
   `.scratch/resume-proof/R2.log`, not `logs/planet-store.log`, and a resumed day writes no steps.json):** check it with the list "To check on the first world day after the HOLD
   is lifted" (the four speed-ups installed 11-26: engine room waits, `points` seconds, timers, the day's wall against
   11-25's 12,643 s), then `rename_places.py check` (as of 11-26).
   [journal/2026-11-26-performance-review-of-the-traces-and-logs.md](journal/2026-11-26-performance-review-of-the-traces-and-logs.md)
3. **The 12-01 cutover to Overture 11-18.0: on 12-01, after the loop's 12-01 day ends (about 18:15), at D = 12-01,
   watched by the owner (owner, 11-27 10:45).** From the main checkout, detached (background jobs die at 2 h; start it
   with `python tools/detach.py logs/switch.log . .scratch/overture/.venv/Scripts/python.exe -u tools/overture_switch.py
   cutover 2026-11-18.0`, as 11-27's `prepare` was) (writes the HOLD, refuses while the loop runs or
   the store's day is not the world's gated day; about 4.5 h: storecut, notes, canary, count, seed, counts, gate, join,
   compare), then `adopt 2026-11-18.0`, commit what it names, and the owner lifts the HOLD (before midnight). After the new
   world's gate at D passes, the old world's `world.bin` files go (owner, 11-26). Disk: 178 GiB free on 11-27 10:50 after
   `.scratch/planet/world-places/files/` went (58 GB, owner 10:48); the cut peaks +80 GB, the new world keeps about 65 GB.
   Ended places' files stay frozen (`daily` keep-gone; adopt-names `keep_ended`). `config/parts` not rebuilt (follow-up).
   [journal/2026-11-26-the-12-01-switch-to-overture-11-18-0-mapped-not-built.md](journal/2026-11-26-the-12-01-switch-to-overture-11-18-0-mapped-not-built.md)
4. **Release day (12-01 at the earliest):** redraw the share card (`python design/project_card.py && python
   design/render_share_card.py`, in a loop gap), look at `docs/img/share-card.png`, commit; then write what redraws it
   monthly (nothing does). `share-previews` itself was merged 11-26 (as of 11-26).
   [journal/2026-11-10-idea-share-previews-for-links.md](journal/2026-11-10-idea-share-previews-for-links.md)
5. **The city run's clean-up**, not before the HOLD is lifted and a few world days publish cleanly ("docs/ and config/ are
   as deployed; nothing to do", no data commit): `run.py`'s `update`/`download`/`count`/`backfill`, their tests,
   `schedule-add.ps1`, README's Scheduling part; decide `kk-SCOpenQuests-planet` on the way (as of 11-26; owner: "handoff
   the further cleanup").
   [journal/2026-11-26-the-city-runs-clean-up-after-the-world-dailies-run-well.md](journal/2026-11-26-the-city-runs-clean-up-after-the-world-dailies-run-well.md)
6. **Overture 12-16.0, the first unattended monthly release:** the watcher prepares it (`narrow`, `propose`, `auto`, the
   judge: `claude-opus-5-5` at high effort), the operator gets only exceptions; switch on 2027-01-01 (as of 11-26; owner,
   about 12:05: "on first of the month we switch it").
   [journal/2026-11-26-the-overture-release-tool.md](journal/2026-11-26-the-overture-release-tool.md)
7. **The Map tab as a navigation tool, after the 12-01 switch** (as of 11-27; owner chose it 10:45): Overture outlines
   down to cities as one PMTiles file on sc-data, MapLibre, a tap gives the chain of places. Its sentence ("the rest of
   the world is not counted yet") stays until then (owner). Design:
   [design/topics/the-map-tab-a-navigation-tool.md](design/topics/the-map-tab-a-navigation-tool.md)

## Parked

One line each in [BACKLOG.md](BACKLOG.md): the world's monthly backfill (release 2) and doing it on several machines,
retiring the Python tile store, a native Windows osmium, other validators' backlogs, the blog, ended-place pages and
successor links, the Overture tool's same-name gap, the performance review's leftovers, and statistics on a map.

## Where things are

- [journal/](journal/README.md): history, append-only, one file per topic or day. Its README lists every heading of the
  old 500 KB HANDOFF.md (split 2026-11-27); a code comment citing `HANDOFF, "<phrase>"` resolves with
  `grep -rn '<phrase>' journal/`.
- [DESIGN.md](DESIGN.md): settled design, an index of [design/topics/](design/topics/) (one file per decision, old
  heading text kept, so `DESIGN.md, "<heading>"` still resolves). Not under `docs/`: that folder is the published site.
- [BACKLOG.md](BACKLOG.md): parked ideas and later work.
- [REPIN.md](REPIN.md): moving to a new StreetComplete version.
- [DATA-FORMAT.md](DATA-FORMAT.md): the published JSON.
- [HARDWARE.md](HARDWARE.md): hardware for a daily world count (written 11-06).
- [PRIOR-ART.md](PRIOR-ART.md): related work.
- `tools/overture_release.py` and `tools/overture_switch.py`: their docstrings are the procedures.
