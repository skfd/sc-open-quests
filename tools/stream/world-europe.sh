#!/bin/bash
# The world's tier 1 on five planet days, tested where europe-west's whole counts can check it (DESIGN.md, "The
# world state store"): copies of the four world files holding Lisboa, Dublin and London (f34 f44 f90 f106), the
# europe-west node locations of 11-08 (a fresh overlay), diffs 5171..5175 applied with world_state.py, each day
# checked against europe-west's whole count of that day. Every step skips what is done:
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' -ArgumentList
#     '/c/Users/kk/Code/sc-open-quests/tools/stream/world-europe.sh'
#     -RedirectStandardOutput logs\world-europe.log -RedirectStandardError logs\world-europe.err
set -euo pipefail
M=/c/Users/kk/Code/sc-open-quests
W=$M/.scratch/planet/world-places
T=$M/.scratch/planet/world-test
D=$M/.scratch/stream/europe-west
DIFFS=$M/.scratch/planet/diffs-keep
WS="python $M/tools/stream/world_state.py"
export JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
log() { echo "$(date '+%F %T') $*"; }
trap 'log "world europe ended ($?)"' EXIT
log "world europe start"

if [ ! -f $T/world-stream.json ]; then
  $WS subset $W $T f34,f44,f90,f106
  (cd $M && python -c "
import numpy as np, sys
sys.path.insert(0, 'tools/stream')
from stream import REC
np.save('.scratch/planet/world-test/seed-keys.npy', np.unique(np.fromfile('.scratch/stream/europe-west/day-08/state.bin', REC)['key']))")
  mkdir -p $T/nodes
  cp $D/nodes.idx $T/nodes/
  (cd $T/nodes && python -c "import pickle; pickle.dump({}, open('overlay.pickle', 'wb'))")
fi
[ -f $T/check-2026-11-08.txt ] || $WS check $T --dump $D/day-08/state.bin > $T/check-2026-11-08.txt || true
cat $T/check-2026-11-08.txt
day=9
for seq in 5171 5172 5173 5174 5175; do
  dd=$(printf "%02d" $day)
  if [ ! -f $T/check-2026-11-$dd.txt ]; then
    log "apply $seq (to 11-$dd)"
    $WS apply $T --nodes $T/nodes --diff $DIFFS/$seq.osc.gz --today 2026-11-${dd}T00:00:00Z
    $WS check $T --dump $D/day-$dd/state.bin > $T/check-2026-11-$dd.txt || true
    cat $T/check-2026-11-$dd.txt
  fi
  day=$((day + 1))
done
log "world europe done"
