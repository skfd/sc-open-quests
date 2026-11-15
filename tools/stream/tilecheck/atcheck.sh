#!/bin/bash
# The Rust history reader (tilestore at) against osmium time-filter, object for object, at each date given.
#   atcheck.sh X.osh.pbf OUTDIR 2019-01-01T00:00:00Z [more dates]
# osmium runs in the Docker image name-ru-repair-osmium (osmium 1.18), the history file's folder mounted read-only.
# Leaves OUTDIR/rs-<date>.osm.pbf, os-<date>.osm.pbf and cmp-<date>.json; exits 1 if any date differs.
set -u
osh=$1; out=$2; shift 2
here=$(cd "$(dirname "$0")" && pwd)
ts="$here/../../../tilestore/target/release/tilestore.exe"
mkdir -p "$out"
dir=$(cd "$(dirname "$osh")" && pwd -W 2>/dev/null || cd "$(dirname "$osh")" && pwd)
outw=$(cd "$out" && pwd -W 2>/dev/null || cd "$out" && pwd)
bad=0
for d in "$@"; do
  n=${d//:/}
  "$ts" at --pbf "$osh" --at "$d" --out "$out/rs-$n.osm.pbf" 2>&1 | tail -1
  MSYS_NO_PATHCONV=1 docker run --rm -v "$dir:/in:ro" -v "$outw:/out" --entrypoint osmium name-ru-repair-osmium \
    time-filter "/in/$(basename "$osh")" "$d" -o "/out/os-$n.osm.pbf" --overwrite || bad=1
  python "$here/pbfcmp.py" "$out/rs-$n.osm.pbf" "$out/os-$n.osm.pbf" > "$out/cmp-$n.json" || bad=1
  python -c "import json,sys; c=json.load(open(sys.argv[1])); print(sys.argv[2], c['objects'], 'objects,', c['different'], 'different, equal' if c['equal'] else 'different, NOT EQUAL')" "$out/cmp-$n.json" "$d"
done
exit $bad
