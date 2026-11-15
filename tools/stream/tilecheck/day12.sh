#!/bin/bash
# two days through the z14 store from generation 0: 5175 (to 11-13) and 5176 (to 11-14), each held against a fresh cut,
# the way and relation tile indexes too, and D of day one recounted through the store
set -e
cd /c/Users/kk/Code/sc-open-quests
export JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
TS="python tools/stream/tilestore.py"
TI="python tools/stream/tiles.py"
R=.scratch/tiles/ref
S=.scratch/tiles/store
POLY=C:/Users/kk/Code/.osm-data/europe/polygon.geojson
rm -f $S/*-0001.* $S/*-0002.*
python -c "import json; p='$S/store.json'; m=json.load(open(p)); m['generations']=m['generations'][:1]; json.dump(m, open(p,'w'), indent=1)"
check() {  # $1 fresh store, $2 generation
  echo "== tiles, by the clip polygon's edge (against $1)"
  python -I tools/stream/tilecheck/edge.py $S $1 $POLY
  echo "== relation store"
  python -I tools/stream/tilecheck/reledge.py $S $1 $POLY
  echo "== way and relation tile indexes"
  python -I tools/stream/tilecheck/idxcheck.py $S/wtiles-000$2.npy $1/wtiles-0000.npy $POLY
  python -I tools/stream/tilecheck/idxcheck.py $S/rtiles-000$2.npy $1/rtiles-0000.npy $POLY
}
$TS update --store $S --diff .scratch/planet/diffs-keep/5175.osc.gz --before .scratch/tiles/geom-12 --day 2026-11-13 --polygon $POLY
check .scratch/tiles/store13 1
echo "== D of day one through the store"
$TS read --store $S --cities $R/cities.json --out .scratch/tiles/s13/join.osm.pbf --stamp 2026-11-13T00:00:00Z
$TI recount --pbf .scratch/tiles/s13/join.osm.pbf --cities $R/cities.json --today 2026-11-13T00:00:00Z --out .scratch/tiles/s13/rc
$TI compare --a $R/state.bin --b .scratch/tiles/s13/rc/state.bin --cities $R/cities.json
$TS update --store $S --diff .scratch/planet/diffs-keep/5176.osc.gz --before .scratch/tiles/geom-13 --day 2026-11-14 --polygon $POLY
check .scratch/tiles/store14 2
echo "day12 done"
