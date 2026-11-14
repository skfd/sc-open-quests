#!/bin/bash
# The stream on europe-west with tier 2 in the delta form (DESIGN.md, "The stream: its state"): as europe-t2.sh (the
# splice), but each day's rectangles are also recounted on yesterday's clip at yesterday's clock, and only the
# recount's own changes go into the state (stream.py apply --tier2-old-clip, tier2.delta). Its own state in $D/t2d
# (ways.npz copied from $D/t2, nodes.idx from $D); the whole counts of each day are europe-test.sh's ($D/day-NN).
# Every step skips what is done:
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' -ArgumentList
#     '/c/Users/kk/Code/sc-open-quests/tools/stream/europe-t2d.sh'
#     -RedirectStandardOutput logs\stream-t2d.log -RedirectStandardError logs\stream-t2d.err
set -euo pipefail
M=/c/Users/kk/Code/sc-open-quests
D=$M/.scratch/stream/europe-west
T=$D/t2d
ST="python $M/tools/stream/stream.py"
CITIES=$M/data/cities/europe-west.json
EU=/c/Users/kk/Code/.osm-data/europe
DIFFS=/c/Users/kk/Code/.osm-data/planet/diffs
export JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
log() { echo "$(date '+%F %T') $*"; }
quiet() { (cd $M && python -c "import sys; sys.path.insert(0, 'tools'); import world_cells as w; w.quiet(20)"); }

trap 'log "stream t2d ended ($?)"' EXIT
log "stream t2d start"
mkdir -p $T
[ -f $T/ways.npz ] || cp $D/t2/ways.npz $T/  # the seed clip's ways, as europe-t2.sh built them
[ -f $T/ways-overlay.pickle ] || python -c "import pickle; pickle.dump({}, open(r'$T/ways-overlay.pickle', 'wb'))"
[ -f $T/nodes.idx ] || cp $D/nodes.idx $T/
[ -f $T/overlay.pickle ] || python -c "import pickle; pickle.dump({}, open(r'$T/overlay.pickle', 'wb'))"
[ -f $T/state.json ] || $ST seed --dump $D/day-08/state.bin --dir $T
day=9
for seq in 5171 5172 5173 5174 5175; do
  dd=$(printf "%02d" $day)
  if [ ! -f $T/check-2026-11-$dd.txt ]; then
    quiet
    log "apply $seq (to 11-$dd) with tier 2"
    $ST apply --dir $T --diff $DIFFS/$seq.osc.gz --today 2026-11-${dd}T00:00:00Z --cities $CITIES --zone Europe/London \
      --tier2-clip $EU/europe-2026-11-$dd.osm.pbf --tier2-old-clip $EU/europe-2026-11-$(printf "%02d" $((day - 1))).osm.pbf
    $ST check --dir $T --dump $D/day-$dd/state.bin
  fi
  day=$((day + 1))
done
log "stream t2d done"
