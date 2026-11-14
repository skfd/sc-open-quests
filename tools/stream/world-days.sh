#!/bin/bash
# The world's stream, tier 1 (DESIGN.md, "The world state store"; owner, 11-14: stream the world from the 11-08 seed
# through the coming weeks): once the planet node store is built (.scratch/store/planet.sh, "planet done"), the
# stream state is made of hard links to the seed's files (a file is replaced whole on change, so the seed keeps its
# 11-08 rows), then every kept day diff from 5171 on is applied in order, each at its state file's timestamp, the
# node store kept current in place. The days europe-west has whole counts for (11-09..11-13) are checked on the
# files those counts reach. Rerun to catch up: every applied diff is skipped.
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' -ArgumentList
#     '/c/Users/kk/Code/sc-open-quests/tools/stream/world-days.sh'
#     -RedirectStandardOutput logs\world-days.log -RedirectStandardError logs\world-days.err
set -euo pipefail
M=/c/Users/kk/Code/sc-open-quests
W=$M/.scratch/planet/world-places
S=$M/.scratch/planet/world-stream
LOC=$M/.scratch/store/planet.loc
D=$M/.scratch/stream/europe-west
DIFFS=$M/.scratch/planet/diffs-keep
WS="python $M/tools/stream/world_state.py"
export JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
log() { echo "$(date '+%F %T') $*"; }
trap 'log "world days ended ($?)"' EXIT
log "world days start"
until grep -q "planet done" $M/logs/planet-loc.log 2>/dev/null; do
  grep -q "FAILED" $M/logs/planet-loc.log 2>/dev/null && { log "the node store build failed"; exit 1; }
  sleep 60
done
[ "$(cat $LOC.state)" = "2026-11-08T00:00:00Z" ] || [ -f $S/world-stream.json ] || { log "planet.loc is not at 11-08: $(cat $LOC.state)"; exit 1; }
log "node store ready: $(ls -la $LOC | awk '{print $5}') bytes, at $(cat $LOC.state)"

powershell -File "$(cygpath -w $M/.scratch/planet/keep-diffs.ps1)" || true
if [ ! -f $S/world-stream.json ]; then
  $WS subset $W $S all --link
  (cd $M && python -c "
import numpy as np, sys
sys.path.insert(0, 'tools/stream')
from stream import REC
np.save('.scratch/planet/world-stream/seed-keys.npy', np.unique(np.fromfile('.scratch/stream/europe-west/day-08/state.bin', REC)['key']))")
fi
for f in $(ls $DIFFS/*.osc.gz | sort -t/ -k1 -V); do
  seq=$(basename $f .osc.gz)
  [ "$seq" -ge 5171 ] || continue
  grep -q "\"$seq.osc.gz\"" $S/world-stream.json && continue
  today=$(grep timestamp $DIFFS/$seq.state.txt | sed 's/.*=//; s/\\//g')
  log "apply $seq (to $today)"
  $WS apply $S --nodes $LOC --diff $f --today $today
  echo "$today" > $LOC.state
  dd=${today:8:2}
  if [ "${today:0:8}" = "2026-11-" ] && [ -f $D/day-$dd/state.bin ] && [ ! -f $S/check-2026-11-$dd.txt ]; then
    $WS check $S --dump $D/day-$dd/state.bin > $S/check-2026-11-$dd.txt || true
    cat $S/check-2026-11-$dd.txt
  fi
done
log "world days done"
