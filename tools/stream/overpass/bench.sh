#!/bin/bash
# Overpass with attic as tier 2's store, benchmarked here (HANDOFF, "Overpass benchmark"; opbench.py says what is asked).
#   bench.sh rehearse   the Lisboa rectangles, on a small extract of the 11-12 clip
#   bench.sh full       all of t2n's 103 rectangles, on the whole europe clip of 11-12
# Load the 11-12 clip with attic kept; stage 1: undated query against ref/old (11-12); apply planet day diff 5175 with
# attic kept; stage 2: undated against ref (11-13); stage 3: [date:11-12T00:00Z] against ref/old and against stage 1's
# answer; then every rectangle alone, cold and warm, at both dates. Every step skips what is done (a .done file), so a
# rerun goes on. Results in .scratch/overpass/<mode>/ (summary.json). The db lives in Docker volume opbench-<mode>.
# Cleanup: docker rm -f opbench-<mode>; docker volume rm opbench-<mode>.
set -e
MODE=${1:?rehearse or full}
cd /c/Users/kk/Code/sc-open-quests
export MSYS_NO_PATHCONV=1
export JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
I=wiktorn/overpass-api:v0.7.62.11
N=opbench-$MODE
W=.scratch/overpass/$MODE
REF=.scratch/tiles/ref
D1=2026-11-12T00:00:00Z
D=2026-11-13T00:00:00Z
OP="python tools/stream/overpass/opbench.py"
mkdir -p $W
WABS=$(cd $W && pwd -W)
EUR=C:/Users/kk/Code/.osm-data/europe
DIFFS=$(cd .scratch/planet/diffs-keep && pwd -W)
step() { [ -f $W/$1.done ]; }
done_() { touch $W/$1.done; }
t0() { T0=$(date +%s); }
t1() { echo $(( $(date +%s) - T0 )); }
echo "=== bench $MODE $(date)"

if [ $MODE = rehearse ]; then
  CITIES=$W/cities.json
  [ -f $CITIES ] || $OP subset --cities $REF/cities.json --prefix lisboa --out $CITIES
else
  CITIES=$REF/cities.json
fi

if ! docker ps --format '{{.Names}}' | grep -qx $N; then
  docker rm -f $N >/dev/null 2>&1 || true
  docker volume create $N >/dev/null
  docker run -d --privileged --name $N --entrypoint sleep -v $N:/db -v $EUR:/in:ro -v $DIFFS:/diffs:ro -v "$WABS":/work $I infinity
fi

if ! step src; then
  if [ $MODE = rehearse ]; then
    BB=$(python -c "
import sys; sys.path.insert(0,'tools/stream'); import tiles
from pathlib import Path
b=tiles.city_boxes(Path('$CITIES'),Path('.'))
print(f'{min(x[2] for x in b)-0.05},{min(x[1] for x in b)-0.05},{max(x[4] for x in b)+0.05},{max(x[3] for x in b)+0.05}')")
    echo "== rehearsal extract, bbox $BB"
    docker exec $N osmium extract -b $BB -s smart -S types=any /in/europe-2026-11-12.osm.pbf -O -o /work/src.osm.pbf \
      || docker exec $N osmium extract -b $BB -s complete_ways /in/europe-2026-11-12.osm.pbf -O -o /work/src.osm.pbf
    echo /work/src.osm.pbf > $W/src.txt
  else
    echo /in/europe-2026-11-12.osm.pbf > $W/src.txt
  fi
  done_ src
fi
SRC=$(cat $W/src.txt)

if ! step load; then
  echo "== load $SRC with attic kept"
  docker exec $N sh -c "rm -rf /db/db && mkdir -p /db/db"
  t0
  docker exec $N sh -c "osmium cat $SRC -f osm -o - | /app/bin/update_database --db-dir=/db/db --keep-attic --version=$D1 --compression-method=lz4 --map-compression-method=lz4 --flush-size=16"
  S=$(t1)
  B=$(docker exec $N du -sb /db/db | cut -f1)
  echo "{\"loadSeconds\": $S, \"dbBytes\": $B}" > $W/load.json
  echo "load: $S s, db $B bytes"
  done_ load
fi

stage() {  # name date-or-empty stamp ref-dir
  local nm=$1 dt=$2 st=$3 rf=$4
  if ! step $nm; then
    echo "== $nm: query ${dt:-undated}, recount at $st, against $rf"
    $OP ql --cities $CITIES ${dt:+--date $dt} > $W/$nm.ql
    $OP query --container $N --ql $W/$nm.ql --out $W/$nm.osm --mode-dir $W --json $W/$nm-query.json
    $OP pbf --container $N --osm $W/$nm.osm --stamp $st --out $W/$nm.osm.pbf --mode-dir $W
    rm -f $W/$nm.osm
    $OP recount --pbf $W/$nm.osm.pbf --cities $CITIES --today $st --out $W/$nm-rc
    $OP compare --a $rf/state.bin --b $W/$nm-rc/state.bin --cities $CITIES --json $W/$nm-compare.json
    done_ $nm
  fi
}

stage s1-undated-1112 "" $D1 $REF/old

if ! step diff; then
  echo "== apply 5175 with attic kept"
  docker exec $N sh -c "rm -rf /db/osc && mkdir -p /db/osc && gunzip -c /diffs/5175.osc.gz > /db/osc/000005175.osc"
  t0
  docker exec $N /app/bin/update_from_dir --osc-dir=/db/osc --db-dir=/db/db --version=$D --keep-attic --flush-size=0
  S=$(t1)
  docker exec $N rm -rf /db/osc
  B=$(docker exec $N du -sb /db/db | cut -f1)
  echo "{\"diffSeconds\": $S, \"dbBytes\": $B}" > $W/diff.json
  echo "diff 5175: $S s, db $B bytes"
  done_ diff
fi

stage s2-undated-1113 "" $D $REF
stage s3-dated-1112 $D1 $D1 $REF/old

if ! step s3vs1; then
  echo "== stage 3's answer against stage 1's"
  docker exec $N osmium diff -s -q /work/s1-undated-1112.osm.pbf /work/s3-dated-1112.osm.pbf > $W/s3vs1.txt 2>&1 || true
  docker exec $N osmium diff -s /work/s1-undated-1112.osm.pbf /work/s3-dated-1112.osm.pbf 2>&1 | tail -5 >> $W/s3vs1.txt || true
  docker exec $N sh -c "osmium diff -f opl /work/s1-undated-1112.osm.pbf /work/s3-dated-1112.osm.pbf | head -40" >> $W/s3vs1.txt 2>&1 || true
  cat $W/s3vs1.txt | head -10
  done_ s3vs1
fi

for dt in "" $D1; do
  tag=${dt:+dated}; tag=${tag:-undated}
  for c in cold warm; do
    if ! step each-$tag-$c; then
      echo "== every rectangle alone, $tag, $c"
      $OP each --container $N --cities $CITIES ${dt:+--date $dt} --out $W/each-$tag-$c.json $([ $c = cold ] && echo --cold)
      done_ each-$tag-$c
    fi
  done
done

for nm in s1-undated-1112 s2-undated-1113 s3-dated-1112; do
  if ! step union-cold-$nm; then
    $OP dropcache --container $N
    $OP query --container $N --ql $W/$nm.ql --out $W/cold-$nm.osm --mode-dir $W --json $W/cold-$nm-query.json
    rm -f $W/cold-$nm.osm
    done_ union-cold-$nm
  fi
done

python - "$W" <<'EOF'
import json, sys
from pathlib import Path
w = Path(sys.argv[1])
def j(n):
    p = w / n
    return json.loads(p.read_text()) if p.exists() else None
out = {"load": j("load.json"), "diff": j("diff.json")}
for nm in ("s1-undated-1112", "s2-undated-1113", "s3-dated-1112"):
    c = j(f"{nm}-compare.json") or {}
    out[nm] = {"query": j(f"{nm}-query.json"), "queryCold": j(f"cold-{nm}-query.json"),
               "compare": {k: v for k, v in c.items() if "examples" not in k}}
for nm in ("undated-cold", "undated-warm", "dated-cold", "dated-warm"):
    e = j(f"each-{nm}.json")
    if e:
        out["each-" + nm] = {k: v for k, v in e.items() if k != "rows"}
(w / "summary.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
EOF
echo "=== bench $MODE ended $(date)"
