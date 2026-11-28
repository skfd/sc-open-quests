## The share card redraws itself once a month (2026-11-27, evening)

- HANDOFF Next 4's missing half: nothing redrew the share card (`design/project_card.py`, then
  `design/render_share_card.py`). Decided before the work: no new scheduled task; `run.py site` does it, the run that
  `kk-SCOpenQuests-inputs` makes at 11:15, a gap of the world loop.
- **The gate:** `site(card=True)` is passed only by `inputs()`. The loop's own publish (`planet_store_day.publish`,
  `run.py site` as a subprocess after its day, about 17:45, with RUNNING already gone and perhaps another day to
  follow) and the command line never redraw. On top, `redraw_card` skips while `.scratch/planet-cut/RUNNING` exists (a
  catch-up started by hand can run at 11:15), off main, and over uncommitted edits to the card's files.
- **When:** the card shows the data's day, not the run's (latest.json's date, written into docs/index.html as
  `share-card.png?v=`). "An earlier month than today" would redraw twice at a month's turn (12-01 at 11:15 the world's
  newest day is still 11-30, so the card would say 30 Nov and be stale again on 12-02) and every day while the world
  is held. So: stale when the world's newest gated day (`gated_days`, which `site` reads anyway) is in a later month than
  the card's day; after drawing, the new `?v=` must be in a later month too (sc-data behind the world), else the files
  go back. A page with no `?v=<day>` is left alone and logged (the render could not write into it either).
- **Order in `site`:** place files (`publish_world`), then the card, committed by itself (`Share card: <day>`, four
  files: design/project-card.svg and .png, docs/img/share-card.png, docs/index.html), then `deploy_site`, which sees
  docs/ changed and deploys and pushes as usual. A failure logs "card: redraw FAILED", checks the four files out again,
  and the site run goes on.
- Tests: `tests/test_site_run.py` (CardStaleTest, RedrawCardTest with scripts and git mocked, RedrawCardGitTest with
  real git in a throwaway repo for the commit and the putting back, the gate in SiteTest; nothing drawn). Full suite
  in the worktree: 452 passed, 3 skipped (two of them the unbuilt tilestore in a worktree). The inputs task runs
  `python` from PATH, which has Pillow 12.3.0; headless Edge under Task Scheduler has never run.
  First real run: 12-02's inputs run, after 12-01's world day is published (unchecked until then).
