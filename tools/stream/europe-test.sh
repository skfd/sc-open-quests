#!/bin/bash
# The stream on europe-west, 2026-11-08 to 11-13 (DESIGN.md, "The stream: its state"): the 11-08 Europe clip
# counted whole with --dump-state is the seed; the day diffs 5171-5175 go in one at a time; after each, the
# state is held against that day's clip counted whole. Waits for the world count (chain4) to end and for the
# daily window; one engine at a time. Every step skips what is done, so a rerun goes on where it stopped:
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' -ArgumentList
#     '/c/Users/kk/Code/sc-open-quests-stream/tools/stream/europe-test.sh'
#     -RedirectStandardOutput logs\stream-europe.log -RedirectStandardError logs\stream-europe.err
set -euo pipefail
M=/c/Users/kk/Code/sc-open-quests
S=/c/Users/kk/Code/sc-open-quests-stream
D=$M/.scratch/stream/europe-west
ST="python $S/tools/stream/stream.py"
CITIES=$M/data/cities/europe-west.json
NOTES=$M/data/notes/planet-notes-261113-europe-west.jsonl
EU=/c/Users/kk/Code/.osm-data/europe
DIFFS=/c/Users/kk/Code/.osm-data/planet/diffs
export JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
log() { echo "$(date '+%F %T') $*"; }
quiet() { (cd $M && python -c "import sys; sys.path.insert(0, 'tools'); import world_cells as w; w.quiet(20)"); }

log "stream europe start"
until grep -qE "oracle (written|failed)" $M/logs/planet-places.log; do sleep 120; done
log "the world count is done"

for d in 08 09 10 11 12 13; do
  [ -f $D/day-$d/state.bin.json ] && continue
  quiet
  log "count 2026-11-$d"
  $ST count --pbf $EU/europe-2026-11-$d.osm.pbf --today 2026-11-${d}T00:00:00Z --cities $CITIES \
    --zone Europe/London --notes $NOTES --dir $D/day-$d
done

[ -f $D/state.json ] || $ST seed --dump $D/day-08/state.bin --dir $D
day=9
for seq in 5171 5172 5173 5174 5175; do
  dd=$(printf "%02d" $day)
  if [ ! -f $D/check-2026-11-$dd.txt ]; then
    quiet
    log "apply $seq (to 11-$dd)"
    $ST apply --dir $D --diff $DIFFS/$seq.osc.gz --today 2026-11-${dd}T00:00:00Z --cities $CITIES --zone Europe/London
    $ST check --dir $D --dump $D/day-$dd/state.bin
  fi
  day=$((day + 1))
done
log "stream europe done"
