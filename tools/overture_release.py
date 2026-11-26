"""Take an Overture release into our place registry: the tool proposes, the operator judges, nothing is adopted alone.

Each release is a manual job of an agent and an operator (owner, 2026-11-24; HANDOFF.md, "The Overture release tool"). The
files live in data/place-ids/releases/<release>/, backed up to R2 with the registry (archive_backup.py --only place-ids):

    python tools/overture_release.py narrow RELEASE [--src DIR]    the release's places, narrow (S3, or a local world pull)
    python tools/overture_release.py propose RELEASE [--old R]     the registry against the release: proposals.tsv, report.md
    python tools/overture_release.py status RELEASE                what is judged and what is not, by class
    python tools/overture_release.py accept RELEASE --class C ...  every unjudged row of class C takes its proposal as verdict
    python tools/overture_release.py judge RELEASE KEY VERDICT     one row's verdict
    python tools/overture_release.py apply RELEASE                 every row judged: the staged registry (the live one untouched)

**What a release does to a place.** A place is ours (place_ids.py): its GERS id is an attribute. A registry place whose GERS id
is still in the release is *kept* and takes the release's name, subtype, OSM object and country (a changed name goes to the
former names). The rest need a verdict, one row each in proposals.tsv:

- a *lost* place (live, its GERS id gone): `same <gers>` (the place lives on under that new GERS id: our id, links and series
  stay) or `ended [s1,s2]` (its page stays, marked ended; successors are our ids or new GERS ids of this release);
- a *new* GERS id that no lost row proposes to take: `new` (a new id is minted for it);
- an ended place whose GERS id is *back*: `revive`, or `new` (it stays ended and the GERS id gets a new place).

**Classes** say how strong a proposal is, so the operator can accept a whole class in one command (`accept`) and judge the
rest row by row (`judge`, or by editing the file's `verdict` column). `contested` rows (two lost places propose the same new
GERS id) are never accepted in bulk.

    same-osm          lost; one new GERS id on the same OSM object, same name and subtype          -> same <gers>
    same-osm-changed  lost; the same OSM object, but the name or the subtype changed               -> same <gers>
    same-name-near    lost; no OSM match; one new place of the same name and country within 2 km   -> same <gers>
    contested         lost; its new GERS id is also proposed for another lost place                 -> same <gers> (judge)
    overlap           lost; places of the release overlap it (bbox IoU 0.2+): the best up to three -> ended <successors>
    ended-parent      lost; nothing overlaps, its parent lives on                                   -> ended <parent>
    ended-none        lost; nothing to suggest                                                      -> ended
    back              an ended place's GERS id is in the release again                              -> revive
    new               a new GERS id no lost row proposes to take                                    -> new

A new GERS id whose `same` proposal the operator turns down is minted by `apply` (and listed there): every place of the release
has an id, or places.py stops.

**apply never touches the live registry.** It writes data/place-ids/releases/<release>/registry.tsv.gz and former-names.tsv,
checked: every place of the registry still there with its GUID, the live GERS ids exactly the release's places, place_ids'
rules. Run again after a changed verdict, it keeps the ids it minted before. The staged registry is swapped in only at the
reseed that takes the release (the world cannot take a new place list between two days, HANDOFF.md "Overture's next release"),
after a backup: then config/places.json's pin, small_squares.py build, places.py build into a new folder, the reseed.

The population is place_ids.mint's: every division that has an area. Needs duckdb; the release is read only.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import gzip
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import place_ids  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "data" / "place-ids" / "releases"
FORMER = ROOT / "data" / "place-ids" / "former-names.tsv"
S3 = "s3://overturemaps-us-west-2/release"
GERS = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
CLASSES = ("same-osm", "same-osm-changed", "same-name-near", "contested", "overlap", "ended-parent", "ended-none",
           "back", "new")
NO_BULK = {"contested"}
COLUMNS = ("key", "class", "proposal", "verdict", "judged", "id", "gers_old", "name", "subtype", "country", "osm",
           "candidates", "note")
NEAR_KM = 2.0
IOU_MIN = 0.2
MAX_SUCCESSORS = 3
LOST_SHARE_FLAG = 0.01   # a country losing more than this share of its places is flagged in the report


def folder(release: str, root: Path = RELEASES) -> Path:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.\d+", release):
        raise SystemExit(f"not a release name: {release!r} (like 2026-12-16.0)")
    return root / release


def log(msg: str) -> None:
    print(msg, flush=True)


def connect():
    import duckdb
    con = duckdb.connect()
    con.execute("SET memory_limit = '1500MB'; SET threads = 2; SET preserve_insertion_order = false")
    return con


# --- narrow: the release's places, the columns this tool needs


def narrow(release: str, src: Path | None = None, out_root: Path = RELEASES) -> Path:
    """places.parquet: a row per division that has an area (mint's population), its area bboxes joined into one."""
    out = folder(release, out_root) / "places.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    con = connect()
    if src is None:
        con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region = 'us-west-2'")
        div = f"read_parquet('{S3}/{release}/theme=divisions/type=division/*', hive_partitioning=1)"
        area = f"read_parquet('{S3}/{release}/theme=divisions/type=division_area/*', hive_partitioning=1)"
    else:
        div = f"read_parquet('{(src / 'division.parquet').as_posix()}')"
        area = f"read_parquet('{(src / 'division_area.parquet').as_posix()}')"
    tmp = out.with_suffix(".part")
    con.execute(f"""COPY (
        WITH a AS (SELECT division_id, min(bbox.xmin) x0, min(bbox.ymin) y0, max(bbox.xmax) x1, max(bbox.ymax) y1
                   FROM {area} GROUP BY 1)
        SELECT d.id AS gers,
               coalesce(split_part([s.record_id FOR s IN d.sources IF s.dataset = 'OpenStreetMap' AND s.property = ''][1],
                                   '@', 1), '') AS osm,
               coalesce(d.names."primary", '') AS name, coalesce(d.subtype, '') AS subtype,
               coalesce(d.country, '') AS country, d.parent_division_id AS parent,
               a.x0, a.y0, a.x1, a.y1, (a.x0 + a.x1) / 2 AS lx, (a.y0 + a.y1) / 2 AS ly
        FROM {div} d JOIN a ON a.division_id = d.id
        ORDER BY gers) TO '{tmp.as_posix()}' (FORMAT parquet, COMPRESSION zstd)""")
    os.replace(tmp, out)
    n = con.execute(f"SELECT count(*), count(DISTINCT gers) FROM '{out.as_posix()}'").fetchone()
    if n[0] != n[1]:
        raise SystemExit(f"{out}: {n[0]:,} rows but {n[1]:,} GERS ids")
    log(f"{release}: {n[0]:,} places with an area into {out} ({out.stat().st_size >> 20} MB)")
    return out


# --- propose


def _registry_table(con, registry: Path) -> None:
    """the registry as table r (every column text), read with Python: names may hold quotes"""
    rows = []
    with gzip.open(registry, "rt", encoding="utf-8", newline="") as z:
        head = z.readline().rstrip("\n").split("\t")
        if tuple(head) != place_ids.COLUMNS:
            raise SystemExit(f"{registry}: columns {head}")
        for line in z:
            v = line.rstrip("\n").split("\t")
            rows.append((v[1], v[2], v[3], v[4], v[5], v[6], v[7]))
    con.execute("CREATE TEMP TABLE r (id VARCHAR, gers VARCHAR, osm VARCHAR, name VARCHAR, subtype VARCHAR, "
                "country VARCHAR, state VARCHAR)")
    import pyarrow as pa
    t = pa.table({k: [x[i] for x in rows] for i, k in enumerate(("id", "gers", "osm", "name", "subtype", "country",
                                                                  "state"))})
    con.register("r_arrow", t)
    con.execute("INSERT INTO r SELECT * FROM r_arrow")
    con.unregister("r_arrow")


def _km(lx1, ly1, lx2, ly2) -> float:
    import math
    return math.hypot((lx1 - lx2) * math.cos(math.radians((ly1 + ly2) / 2)), ly1 - ly2) * 111.2


def _cand(c: dict) -> str:
    bits = [c.get("subtype") or "?", c.get("osm") or "no OSM"]
    if c.get("km") is not None:
        bits.append(f"{c['km']:.1f} km")
    if c.get("iou") is not None:
        bits.append(f"IoU {c['iou']:.2f}")
    who = c["id"] if c.get("id") else c["gers"]
    return f"{who} {c.get('name') or '(no name)'} ({', '.join(bits)})"


def propose(release: str, old: str, registry: Path = place_ids.REGISTRY, root: Path = RELEASES) -> Path:
    here = folder(release, root)
    new_p, old_p = here / "places.parquet", folder(old, root) / "places.parquet"
    for p, rel in ((new_p, release), (old_p, old)):
        if not p.exists():
            raise SystemExit(f"{p} is missing: `narrow {rel}` first")
    out = here / "proposals.tsv"
    if out.exists() and any(row["verdict"] for row in read_rows(out)):
        raise SystemExit(f"{out} has verdicts: propose would throw them away. Move it aside first if that is meant.")
    con = connect()
    _registry_table(con, registry)
    con.execute(f"CREATE TEMP TABLE n AS SELECT * FROM '{new_p.as_posix()}'")
    con.execute(f"CREATE TEMP TABLE o AS SELECT * FROM '{old_p.as_posix()}'")

    def rows(sql: str) -> list[dict]:
        cur = con.execute(sql)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, v)) for v in cur.fetchall()]

    # the live places that stay, the lost, the ended ones back, the new GERS ids
    con.execute("CREATE TEMP TABLE lost AS SELECT r.*, o.lx, o.ly, o.x0, o.y0, o.x1, o.y1, o.parent "
                "FROM r LEFT JOIN o USING (gers) WHERE r.state = 'live' AND r.gers NOT IN (SELECT gers FROM n)")
    con.execute("CREATE TEMP TABLE fresh AS SELECT * FROM n WHERE gers NOT IN (SELECT gers FROM r)")
    back = rows("SELECT r.*, n.name AS nname FROM r JOIN n USING (gers) WHERE r.state = 'ended' "
                "AND r.gers NOT IN (SELECT gers FROM r WHERE state = 'live')")
    live_id = dict(con.execute("SELECT gers, id FROM r WHERE state = 'live'").fetchall())

    by_osm = defaultdict(list)
    for c in rows("SELECT l.id AS lid, f.* FROM lost l JOIN fresh f ON f.osm = l.osm AND l.osm <> ''"):
        by_osm[c.pop("lid")].append(c)
    near = defaultdict(list)
    for c in rows(f"""SELECT l.id AS lid, l.lx AS llx, l.ly AS lly, f.* FROM lost l JOIN fresh f
                     ON f.name = l.name AND f.country = l.country AND l.name <> ''
                     AND abs(f.ly - l.ly) < {NEAR_KM / 111.2 * 1.5} AND abs(f.lx - l.lx) < {NEAR_KM / 111.2 * 6}"""):
        c["km"] = _km(c.pop("llx"), c.pop("lly"), c["lx"], c["ly"])
        if c["km"] <= NEAR_KM:
            near[c.pop("lid")].append(c)
    over = defaultdict(list)
    for c in rows(f"""SELECT l.id AS lid, n.*,
            greatest(0, least(l.x1, n.x1) - greatest(l.x0, n.x0)) * greatest(0, least(l.y1, n.y1) - greatest(l.y0, n.y0)) AS i,
            greatest((l.x1 - l.x0) * (l.y1 - l.y0), 1e-12) AS al, greatest((n.x1 - n.x0) * (n.y1 - n.y0), 1e-12) AS an
            FROM lost l JOIN n ON n.x0 < l.x1 AND n.x1 > l.x0 AND n.y0 < l.y1 AND n.y1 > l.y0"""):
        iou = c["i"] / (c["al"] + c["an"] - c["i"])
        if iou >= IOU_MIN:
            c["iou"] = iou
            c["id"] = live_id.get(c["gers"])
            over[c.pop("lid")].append(c)

    out_rows = []
    lost = rows("SELECT * FROM lost ORDER BY id")
    taken = Counter()
    for p in lost:
        osm_c, near_c = by_osm.get(p["id"], []), near.get(p["id"], [])
        if len(osm_c) == 1:
            c = osm_c[0]
            same = c["name"] == p["name"] and c["subtype"] == p["subtype"]
            p["_cls"], p["_target"], p["_c"] = ("same-osm" if same else "same-osm-changed"), c["gers"], osm_c
        elif not osm_c and len(near_c) == 1:
            p["_cls"], p["_target"], p["_c"] = "same-name-near", near_c[0]["gers"], near_c
        else:
            p["_target"] = None
            p["_c"] = osm_c + near_c
        if p["_target"]:
            taken[p["_target"]] += 1
    for p in lost:
        note = ""
        if p["_target"]:
            cls = "contested" if taken[p["_target"]] > 1 else p["_cls"]
            proposal = f"same {p['_target']}"
            cands = p["_c"]
            if cls == "contested":
                note = "another lost place proposes the same new GERS id"
        else:
            ov = sorted(over.get(p["id"], []), key=lambda c: -c["iou"])
            succ = ov[:MAX_SUCCESSORS]
            parent = live_id.get(p.get("parent") or "")
            if p["_c"]:   # several OSM or name matches: none proposed alone, all shown
                note = f"{len(p['_c'])} same-object or same-name candidates: judge"
            if succ:
                cls, cands = "overlap", p["_c"] + succ
                proposal = "ended " + ",".join(c["id"] or c["gers"] for c in succ)
            elif parent:
                cls, cands, proposal = "ended-parent", p["_c"], f"ended {parent}"
                note = (note + "; " if note else "") + "the parent lives on"
            else:
                cls, cands, proposal = "ended-none", p["_c"], "ended"
            if p["lx"] is None:
                note = (note + "; " if note else "") + f"not in {old}: no location"
        out_rows.append({"key": p["id"], "class": cls, "proposal": proposal, "verdict": "", "judged": "", "id": p["id"],
                         "gers_old": p["gers"], "name": p["name"], "subtype": p["subtype"], "country": p["country"],
                         "osm": p["osm"], "candidates": " | ".join(_cand(c) for c in cands), "note": note})
    for p in back:
        out_rows.append({"key": p["id"], "class": "back", "proposal": "revive", "verdict": "", "judged": "", "id": p["id"],
                         "gers_old": p["gers"], "name": p["name"], "subtype": p["subtype"], "country": p["country"],
                         "osm": p["osm"], "candidates": "", "note": f"in {release} as {p['nname']!r}"})
    proposed = set(taken)
    for f in rows("SELECT * FROM fresh ORDER BY gers"):
        if f["gers"] in proposed:
            continue
        out_rows.append({"key": f["gers"], "class": "new", "proposal": "new", "verdict": "", "judged": "", "id": "",
                         "gers_old": "", "name": f["name"], "subtype": f["subtype"], "country": f["country"],
                         "osm": f["osm"], "candidates": "", "note": ""})
    write_rows(out, out_rows)
    report = here / "report.md"
    report.write_text(make_report(con, release, old, out_rows), encoding="utf-8", newline="\n")
    log(f"{len(out_rows):,} rows into {out}; the report: {report}")
    log(status_text(out_rows))
    return out


def make_report(con, release: str, old: str, out_rows: list[dict]) -> str:
    """the counts, and the gates an operator reads before judging"""
    q = lambda s: con.execute(s).fetchall()  # noqa: E731
    live, kept, fresh = q("SELECT count(*) FROM r WHERE state = 'live'")[0][0], \
        q("SELECT count(*) FROM r JOIN n USING (gers) WHERE r.state = 'live'")[0][0], q("SELECT count(*) FROM fresh")[0][0]
    ch = q("""SELECT count(*) FILTER (r.name <> n.name), count(*) FILTER (r.subtype <> n.subtype),
              count(*) FILTER (r.osm <> n.osm), count(*) FILTER (r.country <> n.country)
              FROM r JOIN n USING (gers) WHERE r.state = 'live'""")[0]
    cls = Counter(r["class"] for r in out_rows)
    L = [f"# Overture {release} against the registry ({old} narrow copy for the lost places' locations)", "",
         f"Made {dt.datetime.now().isoformat(timespec='minutes')} by tools/overture_release.py propose.", "",
         "| | places |", "|---|---:|",
         f"| live in the registry | {live:,} |", f"| in {release} (with an area) | {q('SELECT count(*) FROM n')[0][0]:,} |",
         f"| kept (same GERS id) | {kept:,} |", f"| lost (live, GERS id gone) | {live - kept:,} |",
         f"| new GERS ids | {fresh:,} |", "",
         f"Kept places that change: name {ch[0]:,}, subtype {ch[1]:,}, OSM object {ch[2]:,}, country {ch[3]:,}.", "",
         "## Rows by class", "", "| class | rows |", "|---|---:|"]
    L += [f"| {c} | {cls[c]:,} |" for c in CLASSES if cls[c]]
    L += ["", "## Gates", ""]
    new_sub = [s for (s,) in q("SELECT DISTINCT subtype FROM n EXCEPT SELECT DISTINCT subtype FROM o")]
    L.append(f"- **Subtypes not in {old}:** {', '.join(new_sub) if new_sub else 'none'} (places.py knows nine).")
    cities = json.loads((ROOT / "config" / "cities.json").read_text(encoding="utf-8"))["cities"]
    osm_n = {o for (o,) in q("SELECT DISTINCT osm FROM n")}
    osm_o = {o for (o,) in q("SELECT DISTINCT osm FROM o")}
    rels = {c["id"]: f"r{c['relation']}" for c in cities}
    gone = [i for i, r in rels.items() if r in osm_o and r not in osm_n]
    matched = sum(r in osm_n for r in rels.values())
    L.append(f"- **Cities whose relation was a place in {old} and is not in {release}:** "
             f"{', '.join(gone) if gone else 'none'} ({matched} of {len(cities)} match by relation).")
    shares = q(f"""WITH l AS (SELECT country, count(*) k FROM lost GROUP BY 1),
                  t AS (SELECT country, count(*) k FROM r WHERE state = 'live' GROUP BY 1)
                  SELECT t.country, l.k, t.k FROM t JOIN l USING (country) WHERE l.k > {LOST_SHARE_FLAG} * t.k AND l.k >= 20
                  ORDER BY l.k DESC""")
    L.append(f"- **Countries losing over {LOST_SHARE_FLAG:.0%} of their places (20 or more):** " +
             (", ".join(f"{c} {k:,} of {t:,}" for c, k, t in shares) if shares else "none"))
    parts = []
    by_key = {r["key"]: r for r in out_rows}
    for f in sorted((ROOT / "config" / "parts").glob("*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        for p in rec["parts"]:
            r = by_key.get(p["id"])
            if r:
                parts.append(f"  - {rec['city']}: {p['name']} ({p['id']}): {r['class']}, `{r['proposal']}`")
    L.append(f"- **City parts among the rows:** {len(parts)}")
    L += parts
    for name, fn, key in (("dropped-places", "dropped-places.json", "gers"), ("small-squares", "small-squares.json", None)):
        doc = json.loads((ROOT / "config" / fn).read_text(encoding="utf-8"))
        ids = [p[key] if key else p for p in doc["places"]]
        import pyarrow as pa
        con.register("x", pa.table({"gers": ids}))
        k = q("SELECT count(*) FROM x WHERE gers NOT IN (SELECT gers FROM n)")[0][0]
        con.unregister("x")
        L.append(f"- **{name}: GERS ids not in {release}:** {k:,} of {len(ids):,} (build the list again at the reseed)")
    L += ["", "## Next", "",
          "`status`, then `accept --class ...` for the classes the operator takes whole, `judge` the rest; `apply` writes the",
          "staged registry. The live registry changes only at the reseed that takes the release.", ""]
    return "\n".join(L)


# --- the decisions file


def read_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        if tuple(r.fieldnames or ()) != COLUMNS:
            raise SystemExit(f"{path}: columns {r.fieldnames}")
        return list(r)


def write_rows(path: Path, rows: list[dict]) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, delimiter="\t", quoting=csv.QUOTE_NONE, escapechar=None,
                       lineterminator="\n")
    w.writeheader()
    for row in rows:
        w.writerow({k: re.sub(r"[\t\r\n]+", " ", str(row.get(k) or "")) for k in COLUMNS})
    tmp = path.with_suffix(".part")
    tmp.write_text(buf.getvalue(), encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def parse_verdict(v: str, cls: str) -> tuple[str, list[str]]:
    """(word, arguments); raises ValueError on a verdict the row cannot take"""
    word, _, rest = v.strip().partition(" ")
    args = [a for a in re.split(r"[,\s]+", rest.strip()) if a]
    lost = cls not in ("new", "back")
    if word == "same" and lost and len(args) == 1 and GERS.fullmatch(args[0]):
        return word, args
    if word == "ended" and lost and all(place_ids.ID.fullmatch(a) or GERS.fullmatch(a) for a in args):
        return word, args
    if word == "new" and cls in ("new", "back") and not args:
        return word, args
    if word == "revive" and cls == "back" and not args:
        return word, args
    allowed = {"new": "new", "back": "revive | new"}.get(cls, "same <gers> | ended [successors]")
    raise ValueError(f"{v!r} is not a verdict for a {cls} row ({allowed})")


def stamp(how: str) -> str:
    return f"{how} {dt.date.today().isoformat()}"


def accept(release: str, classes: list[str], root: Path = RELEASES) -> int:
    path = folder(release, root) / "proposals.tsv"
    rows = read_rows(path)
    bad = [c for c in classes if c not in CLASSES]
    if bad:
        raise SystemExit(f"no such class: {bad} ({', '.join(CLASSES)})")
    if NO_BULK & set(classes):
        raise SystemExit(f"{sorted(NO_BULK & set(classes))} cannot be accepted in bulk: judge each row")
    n = 0
    for row in rows:
        if row["class"] in classes and not row["verdict"]:
            row["verdict"], row["judged"] = row["proposal"], stamp(f"accept --class {row['class']}")
            n += 1
    write_rows(path, rows)
    log(f"{n:,} rows accepted as proposed ({', '.join(classes)})")
    log(status_text(rows))
    return n


def judge(release: str, key: str, verdict: str, note: str = "", root: Path = RELEASES) -> None:
    path = folder(release, root) / "proposals.tsv"
    rows = read_rows(path)
    hit = [r for r in rows if r["key"] == key]
    if not hit:
        raise SystemExit(f"no row {key!r} in {path}")
    row = hit[0]
    try:
        parse_verdict(verdict, row["class"])
    except ValueError as e:
        raise SystemExit(str(e)) from None
    row["verdict"], row["judged"] = verdict.strip(), stamp("judge")
    if note:
        row["note"] = (row["note"] + "; " if row["note"] else "") + note
    write_rows(path, rows)
    log(f"{key}: {row['verdict']}")


def status_text(rows: list[dict]) -> str:
    tot, done = Counter(r["class"] for r in rows), Counter(r["class"] for r in rows if r["verdict"])
    lines = [f"  {c:<17} {tot[c]:>8,} rows, {done[c]:>8,} judged" for c in CLASSES if tot[c]]
    left = sum(tot.values()) - sum(done.values())
    return "\n".join(lines + [f"  {'all':<17} {sum(tot.values()):>8,} rows, {left:,} not judged"])


# --- apply


def read_release(path: Path) -> dict[str, tuple[str, str, str, str]]:
    """gers -> (osm, name, subtype, country)"""
    con = connect()
    return {g: (o, n, s, c) for g, o, n, s, c in
            con.execute(f"SELECT gers, osm, name, subtype, country FROM '{path.as_posix()}'").fetchall()}


def apply(release: str, registry: Path = place_ids.REGISTRY, former: Path = FORMER, root: Path = RELEASES,
          guid=place_ids.new_guid) -> dict:
    here = folder(release, root)
    rows = read_rows(here / "proposals.tsv")
    left = [r["key"] for r in rows if not r["verdict"]]
    if left:
        raise SystemExit(f"{len(left):,} rows not judged, e.g. {left[:3]}: `status {release}`")
    rel = read_release(here / "places.parquet")
    reg = place_ids.load(registry)
    errors = []
    verdicts = {}
    for r in rows:
        try:
            verdicts[r["key"]] = (r, *parse_verdict(r["verdict"], r["class"]))
        except ValueError as e:
            errors.append(f"{r['key']}: {e}")
    fresh = {g for g in rel if g not in {p.gers for p in reg.places.values()}}
    takers = defaultdict(list)
    for key, (r, word, args) in verdicts.items():
        if word == "same":
            if args[0] not in fresh:
                errors.append(f"{key}: same {args[0]}: not a new GERS id of {release}")
            takers[args[0]].append(key)
    errors += [f"{g} is taken by {len(k)} rows: {k}" for g, k in takers.items() if len(k) > 1]
    if errors:
        raise SystemExit(f"{len(errors)} problems in the verdicts:\n  " + "\n  ".join(errors[:20]))

    # ids this release minted on an earlier apply are kept, by GERS id
    staged = here / "registry.tsv.gz"
    before = {}
    if staged.exists():
        for p in place_ids.load(staged).places.values():
            if p.since == release:
                before[p.gers] = p
    places = {pid: dataclasses.replace(p) for pid, p in reg.places.items()}
    renamed = []

    def take(p: place_ids.Place, gers: str) -> None:
        osm, name, subtype, country = rel[gers]
        name = place_ids._clean(name)
        if name != p.name and p.name:
            renamed.append((p.id, p.name, release))
        p.gers, p.osm, p.name, p.subtype, p.country = gers, osm, name, subtype, country

    for p in places.values():   # kept: the release's attributes
        if p.state == "live" and p.gers in rel:
            take(p, p.gers)
    minted_new, minted_refused = [], []
    revived, ended, same = 0, 0, 0
    pending = {}   # place id -> successor tokens, resolved after minting
    for key, (r, word, args) in verdicts.items():
        if word == "same":
            take(places[key], args[0])
            same += 1
        elif word == "ended":
            places[key].state = "ended"
            pending[key] = args
            ended += 1
        elif word == "revive":
            p = places[key]
            p.state, p.successors = "live", ()
            take(p, p.gers)
            revived += 1
    taken = set(takers)
    new_rows = {key for key, (r, word, a) in verdicts.items() if word == "new" and r["class"] == "new"}
    back_new = {verdicts[k][0]["gers_old"] for k, (r, word, a) in verdicts.items() if word == "new" and r["class"] == "back"}
    used = set(places)
    for g in sorted(fresh - taken) + sorted(back_new):
        if g in before and before[g].id not in used:
            p = dataclasses.replace(before[g])
        else:
            while True:
                u = guid()
                pid = u.hex[:12]
                if pid not in used:
                    break
            p = place_ids.Place(str(u), pid, g, "", "", "", "", since=release)
        used.add(p.id)
        take(p, g)
        p.state, p.successors = "live", ()
        places[p.id] = p
        (minted_new if g in new_rows or g in back_new else minted_refused).append(p.id)
    live_by_gers = {q.gers: x for x, q in places.items() if q.state == "live"}
    for pid, toks in pending.items():
        succ = []
        for t in toks:
            sid = live_by_gers.get(t) if GERS.fullmatch(t) else t
            if not sid or sid not in places:
                raise SystemExit(f"{pid}: successor {t} is not a place after the release")
            succ.append(sid)
        places[pid].successors = tuple(succ)

    out = place_ids.Registry()
    for pid in sorted(places):
        out.add(places[pid])
    bad = out.check()
    lost_ids = [i for i, p in reg.places.items() if i not in out.places or out.places[i].guid != p.guid]
    live_gers = {p.gers for p in out.places.values() if p.state == "live"}
    if lost_ids:
        bad.append(f"{len(lost_ids):,} places lost their id, e.g. {lost_ids[:3]}")
    if live_gers != set(rel):
        bad.append(f"the live GERS ids are not the release's places: {len(live_gers - set(rel)):,} extra, "
                   f"{len(set(rel) - live_gers):,} missing")
    if bad:
        raise SystemExit("not written:\n  " + "\n  ".join(bad[:20]))
    tmp = here / "registry.next.tsv.gz"
    tmp.unlink(missing_ok=True)
    out.save(tmp)
    os.replace(tmp, staged)
    names = former.read_text(encoding="utf-8") if former.exists() else "id\tname\tuntil\n"
    names += "".join(f"{i}\t{place_ids._clean(n)}\t{r}\n" for i, n, r in renamed)
    (here / "former-names.tsv").write_text(names, encoding="utf-8", newline="\n")
    summary = {"release": release, "registry": str(registry), "places": len(out.places),
               "live": len(live_gers), "same": same, "ended": ended, "revived": revived,
               "minted": len(minted_new), "minted after a same proposal was turned down": len(minted_refused),
               "renamed": len(renamed), "applied": dt.datetime.now().isoformat(timespec="seconds")}
    (here / "apply.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")
    log(f"staged registry {staged}: {len(out.places):,} places, {len(live_gers):,} live; same {same:,}, ended {ended:,}, "
        f"revived {revived:,}, minted {len(minted_new):,} (+{len(minted_refused):,} whose same proposal was turned down), "
        f"former names +{len(renamed):,}. The live registry is untouched: back the folder up "
        f"(archive_backup.py --only place-ids).")
    return summary


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--registry", type=Path, default=place_ids.REGISTRY)
    ap.add_argument("--root", type=Path, default=RELEASES, help="the releases folder (a rehearsal: somewhere in .scratch)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("narrow")
    n.add_argument("release")
    n.add_argument("--src", type=Path, help="a local world pull (division.parquet, division_area.parquet) instead of S3")
    p = sub.add_parser("propose")
    p.add_argument("release")
    p.add_argument("--old", help="the release the registry is on (default: config/places.json's pin)")
    s = sub.add_parser("status")
    s.add_argument("release")
    a = sub.add_parser("accept")
    a.add_argument("release")
    a.add_argument("--class", dest="classes", action="append", required=True, choices=CLASSES)
    j = sub.add_parser("judge")
    j.add_argument("release")
    j.add_argument("key", help="the row's key: our id, or a new GERS id")
    j.add_argument("verdict", help="same <gers> | ended [s1,s2] | new | revive")
    j.add_argument("--note", default="")
    y = sub.add_parser("apply")
    y.add_argument("release")
    a = ap.parse_args(argv)
    if a.cmd == "narrow":
        narrow(a.release, a.src, a.root)
    elif a.cmd == "propose":
        old = a.old or json.loads((ROOT / "config" / "places.json").read_text(encoding="utf-8"))["overture"]
        propose(a.release, old, a.registry, a.root)
    elif a.cmd == "status":
        log(status_text(read_rows(folder(a.release, a.root) / "proposals.tsv")))
    elif a.cmd == "accept":
        accept(a.release, a.classes, a.root)
    elif a.cmd == "judge":
        judge(a.release, a.key, a.verdict, a.note, a.root)
    else:
        apply(a.release, a.registry, a.root / ".." / "former-names.tsv" if a.root != RELEASES else FORMER, a.root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
