"""Overpass with attic as tier 2's map data store: a benchmark on this machine (HANDOFF, "Overpass benchmark").

A local Overpass (Docker, wiktorn/overpass-api) holds a clip with attic kept and a day diff applied, so one database
answers D and D-1. For the rectangles of a tier-2 recount it is asked what `tiles.py select()` would hand the engine
(each rectangle's box padded as the engine pads it):
  nodes in the boxes; ways crossing them (a superset of the ways with a node there); relations with a member node or
  crossing way there, and all their member ways; every node of those ways; with versions and timestamps (out meta).
The answer becomes a PBF with the day's stamp, is recounted as `tiles.py recount` does, and compared with the frozen
recount on the whole clip.

  opbench.py subset --cities C --prefix P --out C2       the rectangles whose id starts with P
  opbench.py ql --cities C [--date T] [--only ID] [--ring 300]          the query, to stdout
  opbench.py query --container N --ql Q --out X.osm      run it in the container, timed, with the disk's reads
  opbench.py pbf --container N --osm X.osm --stamp T --out X.osm.pbf     sorted, header stamped
  opbench.py recount --pbf X --cities C --today T --out D [--heap 12]
  opbench.py each --container N --cities C [--date T] --out J [--cold]  every rectangle alone, timed
  opbench.py dropcache --container N                    the Docker VM's page cache dropped (privileged container)

Container paths: the repo's .scratch/overpass/<mode>/ is /work, so --out and --osm paths must lie under it.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "stream"))

ENV = dict(os.environ, MSYS_NO_PATHCONV="1")


def log(msg: str):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def boxes(cities: Path):
    import tiles
    return tiles.city_boxes(cities, ROOT)


def padded(s, w, n, e, ring):
    import tiles
    return tiles.padded(s, w, n, e, ring)


def bbox_ql(b) -> str:
    s, w, n, e = b
    return f"({s:.7f},{w:.7f},{n:.7f},{e:.7f})"


def make_ql(cities: Path, date: str | None, ring: float, only: str | None = None, eps: float = 1e-6) -> str:
    bs = []
    for cid, s, w, n, e in boxes(cities):
        if only and cid != only:
            continue
        ps, pw, pn, pe = padded(s, w, n, e, ring)
        bs.append((ps - eps, pw - eps, pn + eps, pe + eps))
    if not bs:
        sys.exit("no rectangles")
    head = "[out:xml][timeout:7200][maxsize:17179869184]" + (f'[date:"{date}"]' if date else "") + ";"
    nodes = "".join(f"node{bbox_ql(b)};" for b in bs)
    ways = "".join(f"way{bbox_ql(b)};" for b in bs)
    return "\n".join([
        head,
        f"({nodes})->.n;",
        f"(way(bn.n);{ways})->.w;",
        "(rel(bn.n);rel(bw.w);)->.r;",
        "(way(r.r);.w;)->.aw;",
        "(.n;node(w.aw);)->.an;",
        "(.an;.aw;.r;);",
        "out meta;",
        ""])


def to_container(p: Path, mode_dir: Path) -> str:
    rel = p.resolve().relative_to(mode_dir.resolve())
    return "/work/" + rel.as_posix()


def dexec(container: str, script: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "exec", "-i", container, "sh", "-c", script], input=stdin,
                          capture_output=True, env=ENV)


def db_device(container: str) -> str:
    r = dexec(container, "df /db | tail -1 | awk '{print $1}'")
    return Path(r.stdout.decode().strip()).name


def disk_reads(container: str, dev: str) -> tuple[int, int]:
    """(read requests, sectors read) of the db's device, from the VM's /proc/diskstats"""
    r = dexec(container, f"awk '$3==\"{dev}\"{{print $4, $6}}' /proc/diskstats")
    a = r.stdout.decode().split()
    return (int(a[0]), int(a[1])) if len(a) == 2 else (0, 0)


def dropcache(container: str):
    r = dexec(container, "sync; echo 3 > /proc/sys/vm/drop_caches")
    if r.returncode:
        sys.exit("drop_caches failed (is the container privileged?): " + r.stderr.decode())


def run_query(container: str, ql: str, out_c: str | None) -> dict:
    """the query through osm3s_query on the db directly; out_c a container path, or None to count bytes only"""
    dev = db_device(container)
    r0 = disk_reads(container, dev)
    sink = f"> {out_c}" if out_c else "| wc -c"
    script = f"s=$(date +%s.%N); /app/bin/osm3s_query --db-dir=/db/db --quiet {sink}; rc=$?; e=$(date +%s.%N); echo \"rc=$rc t=$s $e\" >&2"
    t = time.time()
    r = dexec(container, script, ql.encode())
    wall = time.time() - t
    r1 = disk_reads(container, dev)
    err = r.stderr.decode()
    m = re.search(r"rc=(\d+) t=([\d.]+) ([\d.]+)", err)
    secs = float(m[3]) - float(m[2]) if m else wall
    out = {"seconds": round(secs, 3), "readRequests": r1[0] - r0[0], "readMiB": round((r1[1] - r0[1]) * 512 / 2**20, 1)}
    if out_c is None:
        try:
            out["bytes"] = int(r.stdout.decode().strip())
        except ValueError:
            out["bytes"] = None
    other = re.sub(r"rc=\d+ t=[\d.]+ [\d.]+\s*", "", err).strip()
    if (m and m[1] != "0") or "runtime error" in other or "Error" in other:
        out["error"] = other[-2000:]
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("subset"); p.add_argument("--cities", type=Path, required=True)
    p.add_argument("--prefix", required=True); p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("ql"); p.add_argument("--cities", type=Path, required=True); p.add_argument("--date")
    p.add_argument("--only"); p.add_argument("--ring", type=float, default=300.0)
    p = sub.add_parser("query"); p.add_argument("--container", required=True); p.add_argument("--ql", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True); p.add_argument("--mode-dir", type=Path, required=True)
    p.add_argument("--json", type=Path)
    p = sub.add_parser("pbf"); p.add_argument("--container", required=True); p.add_argument("--osm", type=Path, required=True)
    p.add_argument("--stamp", required=True); p.add_argument("--out", type=Path, required=True)
    p.add_argument("--mode-dir", type=Path, required=True)
    p = sub.add_parser("recount"); p.add_argument("--pbf", type=Path, required=True); p.add_argument("--cities", type=Path, required=True)
    p.add_argument("--today", required=True); p.add_argument("--out", type=Path, required=True)
    p.add_argument("--heap", type=int, default=12); p.add_argument("--ring", type=float, default=300.0)
    p = sub.add_parser("compare"); p.add_argument("--a", type=Path, required=True); p.add_argument("--b", type=Path, required=True)
    p.add_argument("--cities", type=Path, required=True); p.add_argument("--json", type=Path)
    p = sub.add_parser("each"); p.add_argument("--container", required=True); p.add_argument("--cities", type=Path, required=True)
    p.add_argument("--date"); p.add_argument("--out", type=Path, required=True); p.add_argument("--cold", action="store_true")
    p.add_argument("--ring", type=float, default=300.0)
    p = sub.add_parser("dropcache"); p.add_argument("--container", required=True)
    o = ap.parse_args()

    if o.cmd == "subset":
        c = json.loads(o.cities.read_text(encoding="utf-8"))
        c["cities"] = [x for x in c["cities"] if x["id"].startswith(o.prefix)]
        o.out.parent.mkdir(parents=True, exist_ok=True)
        o.out.write_text(json.dumps(c, indent=1), encoding="utf-8")
        log(f"{len(c['cities'])} rectangles -> {o.out}")
    elif o.cmd == "ql":
        sys.stdout.write(make_ql(o.cities, o.date, o.ring, o.only))
    elif o.cmd == "query":
        res = run_query(o.container, o.ql.read_text(encoding="utf-8"), to_container(o.out, o.mode_dir))
        res["outMiB"] = round(o.out.stat().st_size / 2**20, 1) if o.out.exists() else None
        log(f"query {o.ql.name}: {json.dumps(res)}")
        if o.json:
            o.json.write_text(json.dumps(res, indent=1), encoding="utf-8")
        if "error" in res:
            sys.exit("query failed")
    elif o.cmd == "pbf":
        src, dst = to_container(o.osm, o.mode_dir), to_container(o.out, o.mode_dir)
        t = time.time()
        r = dexec(o.container, f"osmium sort -O {src} -o {dst} --output-header=osmosis_replication_timestamp={o.stamp}")
        if r.returncode:
            sys.exit("osmium sort failed: " + r.stderr.decode())
        log(f"pbf {o.out.name}: {o.out.stat().st_size / 2**20:.1f} MiB in {time.time() - t:.1f} s")
    elif o.cmd == "recount":
        import stream
        t = time.time()
        stream.engine(o.pbf, o.out, o.today, o.cities, "Europe/London", None, area_pass=True, heap_gb=o.heap, base=ROOT,
                      extra_opts=f"-Dopenquests.areaPaddingM={o.ring:.0f}")
        log(f"recount {o.pbf.name} at {o.today} in {time.time() - t:.0f} s -> {o.out}")
    elif o.cmd == "compare":
        import tiles
        res = tiles.compare(o.a, o.b, o.cities, ROOT)
        print(json.dumps(res, indent=1))
        if o.json:
            o.json.write_text(json.dumps(res, indent=1), encoding="utf-8")
    elif o.cmd == "each":
        rows = []
        for cid, s, w, n, e in boxes(o.cities):
            if o.cold:
                dropcache(o.container)
            res = run_query(o.container, make_ql(o.cities, o.date, o.ring, cid), None)
            ps, pw, pn, pe = padded(s, w, n, e, o.ring)
            res["id"] = cid
            res["km2"] = round((pn - ps) * 111.32 * (pe - pw) * 111.32 * math.cos(math.radians((ps + pn) / 2)), 3)
            rows.append(res)
            log(f"{cid}: {json.dumps(res)}")
        tot = {k: round(sum(r.get(k) or 0 for r in rows), 1) for k in ("seconds", "readRequests", "readMiB", "bytes")}
        secs = sorted(r["seconds"] for r in rows)
        summary = {"date": o.date, "cold": o.cold, "queries": len(rows), "total": tot,
                   "medianSeconds": secs[len(secs) // 2], "maxSeconds": secs[-1],
                   "errors": sum(1 for r in rows if "error" in r), "rows": rows}
        o.out.write_text(json.dumps(summary, indent=1), encoding="utf-8")
        log(f"each: {json.dumps({k: v for k, v in summary.items() if k != 'rows'})}")
    elif o.cmd == "dropcache":
        dropcache(o.container)


if __name__ == "__main__":
    main()
