#!/bin/bash
# Count europe-west on two consecutive clips with every match dumped. Same quests file and notes clip.
cd /c/Users/kk/Code/sc-open-quests || exit 1
export JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
export JAVA_OPTS="-Duser.timezone=Europe/London -Xmx30g"
S=.scratch/diff-flips
for d in 2026-11-08 2026-11-09; do
  [ -s $S/matches-$d.tsv ] && [ -f $S/done-$d ] && continue
  start=$(date +%s)
  engine/build/install/sc-open-quests-engine/bin/sc-open-quests-engine.bat count \
    --pbf "C:\\Users\\kk\\Code\\.osm-data\\europe\\europe-$d.osm.pbf" \
    --quests data/quests/v64.1.json --cities data/cities/europe-west.json \
    --out $S/out-$d \
    --source-meta "C:\\Users\\kk\\Code\\.osm-data\\europe\\europe-$d.meta.json" \
    --notes data/notes/planet-notes-261109-europe-west.jsonl \
    --dump-matches $S/matches-$d.tsv --dump-quests "$(cat $S/quests.txt)" || { echo "FAILED $d"; exit 1; }
  echo "$d counted in $(( $(date +%s) - start )) s"
  touch $S/done-$d
done
echo "counts done"
