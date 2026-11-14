#!/bin/bash
# Tier 2 without the way index (DESIGN.md, "Tier 2 for the world", measurement (a)): europe-west's five days streamed
# again exactly as t2a (the delta form, area dates, from the area-dated 11-08 seed), but with
# OPENQUESTS_NO_WAY_INDEX=1: a changed way's old geometry is today's refs at yesterday's places, and ways holding a
# changed node are not looked up. Each day checked against europe-test.sh's whole counts; compare with t2a's
# check-*.txt. Waits for the world stream's catch-up (world-days.sh) to end. Every step skips what is done:
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' -ArgumentList
#     '/c/Users/kk/Code/sc-open-quests/tools/stream/europe-t2n.sh'
#     -RedirectStandardOutput logs\stream-t2n.log -RedirectStandardError logs\stream-t2n.err
set -euo pipefail
M=/c/Users/kk/Code/sc-open-quests
D=$M/.scratch/stream/europe-west
T=$D/t2n
ST="python $M/tools/stream/stream.py"
CITIES=$M/data/cities/europe-west.json
EU=/c/Users/kk/Code/.osm-data/europe
DIFFS=$M/.scratch/planet/diffs-keep
export JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
export OPENQUESTS_NO_WAY_INDEX=1
log() { echo "$(date '+%F %T') $*"; }
quiet() { (cd $M && python -c "import sys; sys.path.insert(0, 'tools'); import world_cells as w; w.quiet(20)"); }
trap 'log "stream t2n ended ($?)"' EXIT
log "stream t2n start"
until grep -q "world days ended" $M/logs/world-days.log 2>/dev/null; do sleep 60; done

mkdir -p $T
# the way store is still read for relations' member ways; it must start at 11-08 (t2a's has moved on)
[ -f $T/ways.npz ] || $ST ways --clip $EU/europe-2026-11-08.osm.pbf --dir $T
[ -f $T/nodes.idx ] || cp $D/nodes.idx $T/
[ -f $T/overlay.pickle ] || (cd $T && python -c "import pickle; pickle.dump({}, open('overlay.pickle', 'wb'))")
[ -f $T/state.json ] || $ST seed --dump $D/area/day-08/state.bin --dir $T
day=9
for seq in 5171 5172 5173 5174 5175; do
  dd=$(printf "%02d" $day)
  if [ ! -f $T/check-2026-11-$dd.txt ]; then
    quiet
    log "apply $seq (to 11-$dd), tier 2 in the delta form, no way index"
    $ST apply --dir $T --diff $DIFFS/$seq.osc.gz --today 2026-11-${dd}T00:00:00Z --cities $CITIES --zone Europe/London \
      --tier2-clip $EU/europe-2026-11-$dd.osm.pbf --tier2-old-clip $EU/europe-2026-11-$(printf "%02d" $((day - 1))).osm.pbf
    $ST check --dir $T --dump $D/day-$dd/state.bin
  fi
  day=$((day + 1))
done
log "stream t2n done"
