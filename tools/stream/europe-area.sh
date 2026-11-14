#!/bin/bash
# Area quests' dates on europe-west (DESIGN.md, "Area quests' dates"): once the world seed (chain5.sh) has ended,
# the engine installed with them, every engine test, the 11-08 clip counted again with --dump-state (now with
# area dates up to 64 days), the dates held against the area quests the whole counts of 11-09..11-13 open on
# untouched ground (.scratch/stream/areacheck.py), and the five days streamed again in the delta form from that
# seed ($D/t2a), each checked against europe-test.sh's whole counts. Every step skips what is done:
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' -ArgumentList
#     '/c/Users/kk/Code/sc-open-quests/tools/stream/europe-area.sh'
#     -RedirectStandardOutput logs\stream-area.log -RedirectStandardError logs\stream-area.err
set -euo pipefail
M=/c/Users/kk/Code/sc-open-quests
D=$M/.scratch/stream/europe-west
A=$D/area
T=$D/t2a
ST="python $M/tools/stream/stream.py"
CITIES=$M/data/cities/europe-west.json
EU=/c/Users/kk/Code/.osm-data/europe
DIFFS=/c/Users/kk/Code/.osm-data/planet/diffs
NOTES=$D/planet-notes-261113-europe-west.jsonl
export JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
log() { echo "$(date '+%F %T') $*"; }
quiet() { (cd $M && python -c "import sys; sys.path.insert(0, 'tools'); import world_cells as w; w.quiet(20)"); }

trap 'log "stream area ended ($?)"' EXIT
log "stream area start"
# the world seed runs from the installed engine: wait for its chain to end
until grep -q "seed chain ended" $M/logs/planet-seed.log 2>/dev/null; do sleep 60; done
log "the seed chain has ended: $(grep 'seed chain ended' $M/logs/planet-seed.log | tail -1)"

mkdir -p $A
if [ ! -f $A/engine.done ]; then
  (cd $M/engine && ./gradlew installDist --no-daemon -q 2>&1 | grep -v "^w:" || true)
  log "engine installed"
  if (cd $M/engine && ./gradlew test --no-daemon -q > $A/engine-tests.log 2>&1); then log "engine tests passed"
  else log "engine tests FAILED: $A/engine-tests.log"; fi
  touch $A/engine.done
fi

if [ ! -f $A/day-08/state.bin.json ]; then
  quiet
  log "count 2026-11-08 with area dates"
  $ST count --pbf $EU/europe-2026-11-08.osm.pbf --today 2026-11-08T00:00:00Z --cities $CITIES \
    --zone Europe/London --notes $NOTES --dir $A/day-08
  grep "area dates" $A/day-08/engine.log || true
fi
[ -f $A/areacheck.txt ] || python $M/.scratch/stream/areacheck.py $A/day-08/state.bin $D $D/t2d/touched.npy > $A/areacheck.txt
cat $A/areacheck.txt

mkdir -p $T
[ -f $T/ways.npz ] || cp $D/t2/ways.npz $T/
[ -f $T/ways-overlay.pickle ] || (cd $T && python -c "import pickle; pickle.dump({}, open('ways-overlay.pickle', 'wb'))")
[ -f $T/nodes.idx ] || cp $D/nodes.idx $T/
[ -f $T/overlay.pickle ] || (cd $T && python -c "import pickle; pickle.dump({}, open('overlay.pickle', 'wb'))")
[ -f $T/state.json ] || $ST seed --dump $A/day-08/state.bin --dir $T
day=9
for seq in 5171 5172 5173 5174 5175; do
  dd=$(printf "%02d" $day)
  if [ ! -f $T/check-2026-11-$dd.txt ]; then
    quiet
    log "apply $seq (to 11-$dd), tier 2 in the delta form, area dates"
    $ST apply --dir $T --diff $DIFFS/$seq.osc.gz --today 2026-11-${dd}T00:00:00Z --cities $CITIES --zone Europe/London \
      --tier2-clip $EU/europe-2026-11-$dd.osm.pbf --tier2-old-clip $EU/europe-2026-11-$(printf "%02d" $((day - 1))).osm.pbf
    $ST check --dir $T --dump $D/day-$dd/state.bin
  fi
  day=$((day + 1))
done
log "stream area done"
