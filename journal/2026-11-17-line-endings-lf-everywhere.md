## Line endings: LF everywhere (owner, 2026-11-17, evening: "we often stumble on LF vs CRLF ... fix it for good")

- Cause: `core.autocrlf=true` (Git for Windows' system config and `~/.gitconfig`) checked 5,449 tracked files out
  as CRLF, while every tool here writes LF (Python `newline="\n"`, the engine, osmium, Claude's Write). A file was
  CRLF if git last wrote it and LF if a tool did, so the same file differed between main and a worktree. That
  broke Edit matches, byte compares, the R2 copy of `_headers`, and the folder-by-folder LF pins in `.gitattributes`.
- Fixed in `.gitattributes`: `* text=auto eol=lf` first, `*.bat`/`*.cmd` CRLF, `docs/vendor/**` untouched. Plus
  `.editorconfig`. The index was already LF, so that commit changed no file.
- **Still to do, once no other session or long run is live:** rewrite the files still CRLF on disk (about 5,450).
  This skips anything with uncommitted changes (dry run without `--apply`):
  `python ~/.claude/skills/kk-line-endings/rewrite.py . --apply`
  Afterwards `git ls-files --eol | grep -c w/crlf` should print 3: `gradlew.bat` and the two vendor files.
  Worktrees made before the fix need the same command run inside each one.
- The owner's lazy recipe for any repo that trips on this is the `kk-line-endings` skill; a hook asks for it
  (2026-11-17). This repo has had it applied: `.vscode/settings.json` sets `files.eol` to LF, and CLAUDE.md
  carries the rule for program output.
- Not covered by attributes: output a program writes (untracked, `.scratch`). Write it with `newline="\n"`, and
  compare text without regard to CR. `engine/sync-sc.ps1` records the raw-byte sha256 of each vendored file, which
  depends on the SC clone's own line endings. Under LF those hashes describe CRLF bytes the repo no longer has.
  Nothing re-checks them, but normalize them on the next sync.
