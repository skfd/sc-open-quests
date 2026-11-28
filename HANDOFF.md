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
  to 2026-11-27 on disk yet". **11-27 done (as of 11-27 18:20):** STOPPED 14:51 on the deleted cell folder (2,244 outlines restored,
  3.2 MB; **keep `.scratch/planet/world-places/files/` and `geo/` while world-1101 is live**), resumed 15:49 with the
  cover kept, gate PASS 17:19 (+12, worst city 0.00177%), done 17:27, published 17:42 (exit 0). 181 GiB free after.
  Next day: 11-28 at 14:45, the first without the old city window. Stop: put back a HOLD (no day) or PAUSE (stops the running day at its next step).
  [journal/2026-11-26-the-world-day-resumable.md](journal/2026-11-26-the-world-day-resumable.md)
- **Power-throttling trial on the world day (as of 11-28 00:30; owner via osmium-windows-fast, brief
  `~/Code/osmium-windows-fast/journal/2026-11-28-sc-open-quests-throttling-brief.md`).** `tools/stream/qos.py`
  (bc7d5e680): a watcher in the world day sets every process of it off power throttling when the switch says
  `high`, and in every mode records each process (`logs/qos/<run>-procs.csv`), the fast/slow cores every 15 s
  (`W/days/<D>/cores.csv`, `qos.json`) and each engine's CPU seconds (`engines.json` "cpu s"). Days in
  `data/qos.txt` (gitignored): **11-28 default, 11-29 high, 11-30 high, 12-01 default**, then default. Way back:
  edit that file, or `SCOQ_QOS=off`. Check after a day: `qos: ...` line in `logs/planet-store.log`, and
  `processes ... failed 0`, and that the first row (python.exe) of 11-28's `logs/qos/*-procs.csv` reads `below
  normal`: the task has no `<Priority>`, so Task Scheduler's default 7 (BELOW_NORMAL) is expected, not yet seen. If it
  reads `normal`, `high` on 11-29/11-30 changes priority as well as throttling: say so when judging (Next 5).
  `qos.json`/`cores.csv` are written after the day's done line (resumed days too). Probe on a real engine passed;
  untried inside a scheduled run until 14:45 today.
  [design/topics/the-world-day-off-power-throttling.md](design/topics/the-world-day-off-power-throttling.md)
- **The world day is resumable (as of 11-27; built c3b998fd1, proven on 11-26).** A stopped finish resumes from what it
  left done behind markers (about 18 min late in the day, not 2.8 h); PAUSE stops a running day at its next step.
  `design/topics/the-world-day-resumable.md` (what is proven, what only mocked).
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
  **`data/cities.paused` placed 11-27 14:50 (owner: "fix the wait"; gitignored, keep it):** the loop's `WD.quiet(20)` before
  the store's update still waited out the deleted city run's window (`backfill_history.QUIET`, 11:55-14:15 local); 11-27
  stood still 11:54-14:15 in it. The marker skips that wait; the wait's code goes with the city run's clean-up.
  [journal/2026-11-26-the-city-runs-clean-up-after-the-world-dailies-run-well.md](journal/2026-11-26-the-city-runs-clean-up-after-the-world-dailies-run-well.md)
- **Four tasks done 11-27 evening (owner chose them, 20:45):** the share card redraws monthly (merged); the Overture
  tool's same-name gap (merged, class `same-name-kept`); the horizon guard (branch `horizon-guard`, Next 4); the history
  cut rehearsed on Berlin (merged; findings in BACKLOG's release-2 entry).
- **Rust port, first two steps built and proven equal (as of 11-28 01:20):** branch `rust-world-day` (head 90448855f),
  worktree `../sc-open-quests-rust-day`, not merged. `stream.read_diff` by `tilestore diffcols` (diff 5189: 104 s to
  23 s, dicts equal in order on 5189 and 5185) and tier 1's small PBF by `tilestore smallpbf` (5185, 5187, 5189: 0 of
  5-6M objects differ; 28-72 s to 12-18 s), switches `SCOQ_RUST_DIFF=0` / `SCOQ_RUST_SMALLPBF=0` the way back. Full
  suite in the worktree 476 passed, 1 skipped. About 2-3 min a day; nothing run inside a real world day yet. Next:
  merge after the 12-01 cutover (owner's call), then 11-28's `steps.json` picks the next step.
  [design/topics/rust-for-the-world-days-python.md](design/topics/rust-for-the-world-days-python.md)
- **Worktrees (as of 11-27):** `.claude/worktrees/agent-a9b152efd4c2e1246` (P3's 28.6 GB rehearsal data, kept for three
  traces) and `../sc-open-quests-place-ids` (branch `place-ids`, merged). Leave both.

## Waiting on the owner

- **The iPhone widgets: two black, two "request timed out" (as of 11-28 01:45).** Every published script copy draws
  from here on the live files, and every URL answers fast, so nothing found broken on our side. On the phone: run
  `open-quests` inside Scriptable (Medium, a widget's Parameter); if it draws, the widget runs are being cut short; if
  it times out, open `https://sc-data.comentality.com/latest.json` in Safari on the same network (VPN, Private Relay,
  DNS filter?). Also the four Parameters, when they last showed numbers, and whether line 26 of the phone's copy
  reads `WORLD = "https://sc-data..."` (the 11-25 copy).
  [journal/2026-11-28-iphone-widgets-blank-or-timing-out.md](journal/2026-11-28-iphone-widgets-blank-or-timing-out.md)
- **Glance at the share-preview Worker's requests and CPU** in the Cloudflare dashboard over the first days (as of
  11-27 20:40; $5 limit, past it the home page fails with error 1103). Telegram showed a neighbourhood link right
  (owner, 20:35): its number, "As of Nov 27", and the site card.
- **Be at the machine on 12-01 from about 18:30 (as of 11-27 10:45)** to watch the cutover (Next 3) and lift the HOLD
  after `adopt`.

## Next, in order

1. **The 12-01 switch: `prepare` done, a one-file canary run; the cutover chain and `adopt` never run on real data
   (as of 11-27 11:00).** The owner chose the start time (Next 3) and no dress rehearsal: "we will do it live".
   `prepare 2026-11-18.0` done 10:26 (every step; `status` shows them): 1,073,190 places, plan check equal (128 files,
   2,244 cells), partcache 5.8 GB. Canary rehearsed on f47 at 11-26, old against new place list on the same cut
   (`.scratch/switch/2026-11-18.0/canary.py`, `REPORT.txt`): 212 of 13,405 parts differ (1.6%), open quests +0.015%.
   Publish: the name layer changes 729 place files and at most 563 children files; 630 published places end (kept
   frozen); with ~1.6% of places moving, the first day after the switch is about 16k files above a normal day's ~60k,
   under DAY_CAP 200k (estimate from one file of 128, which has no cities; the events cache rebuilds once, the release
   stamp changes). Full suite 460 passed, 1 skipped (11-27 22:00, after the evening merges).
   [journal/2026-11-26-the-12-01-switch-to-overture-11-18-0-mapped-not-built.md](journal/2026-11-26-the-12-01-switch-to-overture-11-18-0-mapped-not-built.md)
2. **The first world day after the HOLD is lifted (take 11-28, not 11-27: 11-27 resumed after a stop, its timers part
   kept, and the old window held it 2.4 h (window removed: 7c2ee1f7f); nor 11-26: 11-26's finish ran in the proof, its lines are in
   `.scratch/resume-proof/R2.log`, not `logs/planet-store.log`, and a resumed day writes no steps.json):** check it with the list "To check on the first world day after the HOLD
   is lifted" (the four speed-ups installed 11-26: engine room waits, `points` seconds, timers, the day's wall against
   11-25's 12,643 s), then `rename_places.py check` (as of 11-26). 11-28 runs with the qos watcher observing only (`default`, as of 11-28).
   [journal/2026-11-26-performance-review-of-the-traces-and-logs.md](journal/2026-11-26-performance-review-of-the-traces-and-logs.md)
3. **The 12-01 cutover to Overture 11-18.0: on 12-01, after the loop's 12-01 publish line (about 18:35), at D = 12-01,
   watched by the owner (owner, 11-27 10:45).** From the main checkout, detached (background jobs die at 2 h; start it
   with `python tools/detach.py logs/switch.log . .scratch/overture/.venv/Scripts/python.exe -u tools/overture_switch.py
   cutover 2026-11-18.0`, as 11-27's `prepare` was) (writes the HOLD, refuses while the loop runs or
   publishes, or the store's day is not the world's gated day; about 4.5 h: storecut, notes, canary, count, seed, counts, gate, join,
   compare), then `adopt 2026-11-18.0`, commit what it names, and the owner lifts the HOLD (before midnight). After the new
   world's gate at D passes, the old world's `world.bin` files go (owner, 11-26). Disk: 178 GiB free on 11-27 10:50 after
   `.scratch/planet/world-places/files/` went (58 GB, owner 10:48; its `cells/` restored after 11-27 stopped on them, see
   Now); the cut peaks +80 GB, the new world keeps about 65 GB. **Paths (checked 11-27 16:10):** world-2026-11-18.0 points
   only into itself and `.scratch/world-places/2026-11-18.0/geo/`, all present; world-1101 into
   `.scratch/planet/world-places/files/*/cells` and `geo/`: those go with the old world.bin, not before. Ended places' files stay frozen (`daily` keep-gone; adopt-names `keep_ended`). `config/parts` not rebuilt (follow-up).
   **First time on real data:** every cutover step (storecut..compare) and all of `adopt`; prepare failed three times on
   first contact (11-27). The count is one engine at a time (11-17: 127 of 128 starts, 2.4 h at 57 GiB commit free;
   11-27's canary saw 43 GiB, a 30 GB heap fits). **Abort rule:** a step fails, or compare is not reached by about 23:00:
   leave the HOLD, `adopt` not run, so the old world stays live; a rerun resumes at the markers (`status`). If the store
   moved meanwhile, the seed-day check stops it: clear the switch markers from `seed-day` on and `cut/storecut.json`, then rerun.
   [journal/2026-11-26-the-12-01-switch-to-overture-11-18-0-mapped-not-built.md](journal/2026-11-26-the-12-01-switch-to-overture-11-18-0-mapped-not-built.md)
4. **Merge branch `horizon-guard` after the 12-01 switch, and before 12-28 whatever happens (as of 11-27 21:30).**
   `tools/stream/area_horizon.py`: seed day from `data/world.json` `seeded`; `world_publish.daily` publishes no day past
   seed + 64 (seed + 64 itself still complete) and exits 1, `--past-horizon` overrides; the loop's publish logs a warning
   from 7 days before. world-1101 ends 2027-01-04 (warns from 12-28), so if the cutover aborts it is needed by then;
   world-2026-11-18.0 seeded at 12-01 ends 2027-02-03. 29 tests; full suite 471 passed, 3 skipped in the worktree; merges
   cleanly onto main at 11-27. Open: days joined from the old world after a late switch are judged by the new seed.
   [journal/2026-11-27-the-horizon-guard.md](journal/2026-11-27-the-horizon-guard.md) (on the branch)
5. **Judge the power-throttling trial on 12-02 (as of 11-28):** per engine key (`engines.json` "cpu s", "total s")
   and per step (`steps.json`) for 11-29/11-30 (`high`) against 11-28/12-01 (`default`), plus the slow cores'
   share in each day's `cores.csv`; the compare script is not written yet. Then leave the result in
   osmium-windows-fast's README "Cause 3", "who is affected" (a scheduled headless pipeline), and decide the bare
   line of `data/qos.txt`.
6. **Release day (12-01 at the earliest):** redraw the share card (`python design/project_card.py && python
   design/render_share_card.py`, in a loop gap), look at `docs/img/share-card.png`, commit; from then on `run.py site(card=True)`
   (inputs' 11:15 run only) redraws it when the world has a day in a later month (merged 11-27; first automatic
   redraw 12-02, headless Edge under Task Scheduler unchecked). `share-previews` itself was merged 11-26 (as of 11-26).
   [journal/2026-11-10-idea-share-previews-for-links.md](journal/2026-11-10-idea-share-previews-for-links.md)
7. **Share previews, after the 12-01 switch (as of 11-27 20:20):** rerun `node cloudflare/test/parity.mjs docs
   https://sc-data.comentality.com/` (4,091 of 4,091 on 11-27). Live since 11-27; the daily `site` run deploys the
   Worker (`wrangler.jsonc`), the way back is `wrangler.static.jsonc` (`cloudflare/README.md`, "Share previews").
8. **The city run's clean-up**, not before the HOLD is lifted and a few world days publish cleanly ("docs/ and config/ are
   as deployed; nothing to do", no data commit): `run.py`'s `update`/`download`/`count`/`backfill`, their tests,
   `schedule-add.ps1`, README's Scheduling part; decide `kk-SCOpenQuests-planet` on the way (as of 11-26; owner: "handoff
   the further cleanup").
   [journal/2026-11-26-the-city-runs-clean-up-after-the-world-dailies-run-well.md](journal/2026-11-26-the-city-runs-clean-up-after-the-world-dailies-run-well.md)
9. **Overture 12-16.0, the first unattended monthly release:** the watcher prepares it (`narrow`, `propose`, `auto`, the
   judge: `claude-opus-5-5` at high effort), the operator gets only exceptions; switch on 2027-01-01 (as of 11-26; owner,
   about 12:05: "on first of the month we switch it").
   [journal/2026-11-26-the-overture-release-tool.md](journal/2026-11-26-the-overture-release-tool.md)
10. **The Map tab as a navigation tool, after the 12-01 switch** (as of 11-27; owner chose it 10:45): Overture outlines
   down to cities as one PMTiles file on sc-data, MapLibre, a tap gives the chain of places. Its sentence ("the rest of
   the world is not counted yet") stays until then (owner). Design:
   [design/topics/the-map-tab-a-navigation-tool.md](design/topics/the-map-tab-a-navigation-tool.md)

## Parked

One line each in [BACKLOG.md](BACKLOG.md): the world's monthly backfill (release 2) and doing it on several machines,
retiring the Python tile store, porting the world day's Python steps to Rust, a native Windows osmium, other validators' backlogs, the blog, ended-place pages and
successor links, the performance review's leftovers, and statistics on a map.

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
