#!/bin/bash
# the tile store at zoom $1 (DESIGN.md, "Smaller tiles"): cut 11-12 and 11-13, update by diff 5175 with the clip polygon
# as region, compare with the fresh cut, recount D through the store. With $2 = "update-only", the 11-12 store is reset
# to generation 0 and only the update and checks run.
set -e
Z=$1
cd /c/Users/kk/Code/sc-open-quests
export JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
export OPENQUESTS_TILE_Z=$Z
TS="python tools/stream/tilestore.py"
TI="python tools/stream/tiles.py"
R=.scratch/tiles/ref
POLY=C:/Users/kk/Code/.osm-data/europe/polygon.geojson
if [ $Z = 14 ]; then S=.scratch/tiles/store; S13=.scratch/tiles/store13; else S=.scratch/tiles/store-z$Z; S13=.scratch/tiles/store13-z$Z; fi
if [ "$2" = update-only ]; then
  rm -f $S/*-0001.*
  python -c "import json; p='$S/store.json'; m=json.load(open(p)); m['generations']=m['generations'][:1]; json.dump(m, open(p,'w'), indent=1)"
else
  rm -rf $S $S13
  $TS cut --geom .scratch/tiles/geom-12 --out $S --day 2026-11-12
  $TS cut --geom .scratch/tiles/geom-13 --out $S13 --day 2026-11-13
fi
$TS update --store $S --diff .scratch/planet/diffs-keep/5175.osc.gz --before .scratch/tiles/geom-12 --day 2026-11-13 --polygon $POLY
echo "== tiles under the rectangles"
$TS compare --a $S --b $S13 --cities $R/cities.json --under
echo "== every tile, by the clip polygon's edge"
python -I tools/stream/tilecheck/edge.py $S $S13 $POLY
echo "== relation store"
python -I tools/stream/tilecheck/reledge.py $S $S13 $POLY
echo "== D through the updated store"
$TS read --store $S --cities $R/cities.json --out .scratch/tiles/s13-z$Z/join.osm.pbf --stamp 2026-11-13T00:00:00Z
$TI recount --pbf .scratch/tiles/s13-z$Z/join.osm.pbf --cities $R/cities.json --today 2026-11-13T00:00:00Z --out .scratch/tiles/s13-z$Z/rc
$TI compare --a $R/state.bin --b .scratch/tiles/s13-z$Z/rc/state.bin --cities $R/cities.json
du -sb $S/* | sort -k2
echo "chain z$Z done"
