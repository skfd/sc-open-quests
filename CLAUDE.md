# sc-open-quests

Read HANDOFF.md first: it is short and holds only what is live (what runs, who holds the HOLD, what waits on the owner,
what is next). README.md has the goals; DESIGN.md indexes the settled design in design/topics/; journal/ is history,
never required reading. PRIOR-ART.md lists related work.

Writing the docs:
- After each meaningful step, **edit HANDOFF.md's Now/Next in place** and commit (`Handoff: ...`). Do not append a dated
  section to it; keep every item dated "as of".
- The story of what happened (findings, measurements, the owner's words with the time) goes to the journal, in the same
  commit: `journal/<today>-<slug>.md` or the topic's existing file, append-only.
- A settled decision goes to its file in design/topics/ (a new one gets a line in DESIGN.md's index); a parked idea to
  BACKLOG.md.
- At the end of a session, compact: anything finished leaves HANDOFF.md.
- Mark unfinished checks explicitly ("tests still running; rerun if restarted").
- Nothing of this goes under `docs/`: that folder is the published site, and a change there makes `run.py site` deploy.

Text files are LF (.gitattributes, .vscode/settings.json). Scripts write text with `newline="\n"`; compare text ignoring `\r`.
