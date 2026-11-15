"""Where an Overpass query's time goes, and whether queries scale in parallel (DESIGN.md, "Overpass with attic").

  split.py --container N --mode-dir W --cities C --date T
Runs on the bench db: the union query with `out count;` (selection only), with the XML to /dev/null in the container
(selection and writing, no bind mount), a trivial query (the floor), and the rectangles alone 1, 4 and 8 at a time
(to /dev/null), each warm after one warm-up. Prints and writes split.json in W. Also checks every answer for an
Overpass <remark> (timeouts and memory limits come back as a remark with exit 0).
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opbench as ob


def timed(container, ql, sink="> /dev/null"):
    script = (f"s=$(date +%s.%N); /app/bin/osm3s_query --db-dir=/db/db --quiet {sink}; e=$(date +%s.%N); "
              "echo \"t=$s $e\" >&2")
    r = ob.dexec(container, script, ql.encode())
    import re
    m = re.search(r"t=([\d.]+) ([\d.]+)", r.stderr.decode())
    return float(m[2]) - float(m[1]), r.stdout.decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--container", required=True)
    ap.add_argument("--mode-dir", type=Path, required=True)
    ap.add_argument("--cities", type=Path, required=True)
    ap.add_argument("--date")
    o = ap.parse_args()
    res = {"date": o.date}
    union = ob.make_ql(o.cities, o.date, 300.0)
    count = union.replace("out meta;", "out count;")
    timed(o.container, count)  # warm-up
    res["unionCountSeconds"], cnt = timed(o.container, count, "")
    res["unionCountOutput"] = " ".join(cnt.split())[-400:]
    res["unionDevNullSeconds"], _ = timed(o.container, union)
    t, remark = timed(o.container, union, "| grep -c '<remark' || true")
    res["unionRemarks"] = remark.strip()
    floor = ("[out:xml]" + (f'[date:"{o.date}"]' if o.date else "") + ";node(1);out meta;")
    res["floorSeconds"] = sorted(timed(o.container, floor)[0] for _ in range(5))[2]
    qls = [ob.make_ql(o.cities, o.date, 300.0, cid) for cid, *_ in ob.boxes(o.cities)]
    for n in (1, 4, 8):
        t0 = time.time()
        with ThreadPoolExecutor(n) as ex:
            secs = list(ex.map(lambda q: timed(o.container, q)[0], qls))
        res[f"each{n}"] = {"wall": round(time.time() - t0, 1), "sumSeconds": round(sum(secs), 1),
                           "median": round(sorted(secs)[len(secs) // 2], 3)}
        ob.log(f"{n} at a time: {res[f'each{n}']}")
    out = o.mode_dir / f"split-{'dated' if o.date else 'current'}.json"
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
