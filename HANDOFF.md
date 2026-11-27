# Handoff: sc-open-quests

Read first. This file holds only what is live, **rewritten in place** (never appended to); every item says "as of"
when it was last true. The story behind each item is in [journal/](journal/README.md). What the project is for:
[README.md](README.md), "Goals" (the original brief, verbatim). Release 1 = daily world updates with 30 published days,
12-01 the earliest date (owner, 11-24); release 2 = the world's monthly backfill
([journal/2026-11-16-release-goals.md](journal/2026-11-16-release-goals.md)). Standing rule: anything published counts
every quest, never an easier subset (DESIGN.md, "Don't").

## Now

- **World dailies stopped under the HOLD (as of 11-27 00:35).** `.scratch/planet-cut/HOLD` placed 11-26 18:02 (owner:
  "i am going offline soon ... stop now"); its note names the stop. The loop task `kk-SCOpenQuests-planetstore` (daily
  14:45, 12 h limit) logs "held" and takes no day while HOLD exists. Store and world gated through 11-25; day 11-26 was
  stopped mid tier 2 and is now the resume proof's (next item). **Lifting the HOLD is the owner's word alone**, and not
  before the proof is done. `.scratch/planet-cut/PAUSE` is the softer stop built 11-26 (the day stops at the next engine
  start or step); whether one is placed now: unconfirmed. Restart: delete HOLD (and PAUSE), then
  `schtasks /Run /TN kk-SCOpenQuests-planetstore`.
  [journal/2026-11-26-the-overture-release-tool.md](journal/2026-11-26-the-overture-release-tool.md) (HOLD lifted 16:58,
  PAUSED 18:02), [journal/2026-11-26-the-world-day-resumable.md](journal/2026-11-26-the-world-day-resumable.md) (PAUSE).
- **Session sc-open-quests-5e's resume proof on day 11-26 (as of 11-27 02:55: R2 running, ends about 04:20).** A (killed and
  resumed 5 times) against B (uninterrupted): **DIFFER in 6 of 263** (three world.bin, place-sets, counts). **R1, the
  replay from B's kept outputs: EQUAL to B, 263 of 263**, so the resume path is exact; A's difference came from engine outputs
  made in other runs. R2 (a second uninterrupted run, `proof_r.py`, keep-awake running) tells whether two clean runs differ the
  same way; `canon.py` then compares up to place-set numbering. The world after R2 is an uninterrupted 11-26 with `finished`
  written. No gate, store_tail or publish; HOLD stays; nothing else may run DuckDB, builds or engines beside it. If it died:
  `.scratch/resume-proof/proof.log`, `R2.out`; rerunning a finish is safe (it restores from `before/`).
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

- **Lift the HOLD and start the loop** once 5e's proof is read (as of 11-27). How 11-26 is taken after the proof (resumed
  from `day.pkl` or redone): ask 5e or read its RESULT, unconfirmed.
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

1. **After 5e's proof:** `python tools/overture_switch.py prepare 2026-11-18.0` (the tool is built and merged
   in 06ac3b7d4, never run; new folders only; only between world days or under the HOLD; DuckDB never beside engines: the 11-23 commit-limit failure). Then the f47 canary on the new list
   and a publish dry run counting deletes (as of 11-26 19:45).
   [journal/2026-11-26-the-12-01-switch-to-overture-11-18-0-mapped-not-built.md](journal/2026-11-26-the-12-01-switch-to-overture-11-18-0-mapped-not-built.md)
2. **The first world day after the HOLD is lifted:** check it with the list "To check on the first world day after the HOLD
   is lifted" (the four speed-ups installed 11-26: engine room waits, `points` seconds, timers, the day's wall against
   11-25's 12,643 s), then `rename_places.py check` (as of 11-26).
   [journal/2026-11-26-performance-review-of-the-traces-and-logs.md](journal/2026-11-26-performance-review-of-the-traces-and-logs.md)
3. **The 12-01 switch to Overture 11-18.0 (owner, 11-26: "we are going to do it on 12 01 right?"):** `overture_switch.py
   cutover` at the store's day D under a hand-written HOLD (about 4.5 h; peaks about 80 GB, C: had 105 GB free at 18:20 on
   11-26), then flip `data/world.json` and lift the HOLD. The history join (`gated_days` walks one folder) is not built.
   Owner, 18:35: the old world's `world.bin` files go once the new world passes its gate at D; regional extracts may go
   early (never Ontario); ended places' files are kept frozen, nothing deleted (built: `daily` publishes keep-gone).
   `config/parts` not rebuilt (a follow-up). The staged 11-18.0 registry goes live only here (as of 11-26 19:45).
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

## Parked

One line each in [BACKLOG.md](BACKLOG.md): the world's monthly backfill (release 2) and doing it on several machines,
retiring the Python tile store, a native Windows osmium, other validators' backlogs, the blog, ended-place pages and
successor links, the Overture tool's same-name gap, and the performance review's leftovers.

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
