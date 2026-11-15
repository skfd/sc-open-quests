"""Two PBFs object for object, in file order: type, id, version, timestamp, place, tags (in order), a way's refs,
a relation's members with roles; and the headers' replication timestamp. Written for the Rust read (tilestore read)
against the Python one (tilestore.py read); exits 1 if anything differs.

  pbfcmp.py A.osm.pbf B.osm.pbf
"""
import itertools
import json
import sys

import osmium


def rows(path):
    for o in osmium.FileProcessor(path):
        tags = [(t.k, t.v) for t in o.tags]
        ts = int(o.timestamp.timestamp()) if o.timestamp.year > 1970 else 0
        if o.is_node():
            yield ("n", o.id, o.version, ts, o.location.x, o.location.y, tags)
        elif o.is_way():
            yield ("w", o.id, o.version, ts, [n.ref for n in o.nodes], tags)
        elif o.is_relation():
            yield ("r", o.id, o.version, ts, [(m.type, m.ref, m.role) for m in o.members], tags)


def main():
    a, b = sys.argv[1], sys.argv[2]
    ha = osmium.io.Reader(a, osmium.osm.NOTHING).header()
    hb = osmium.io.Reader(b, osmium.osm.NOTHING).header()
    out = {"stampA": ha.get("osmosis_replication_timestamp"), "stampB": hb.get("osmosis_replication_timestamp"),
           "objects": 0, "n": 0, "w": 0, "r": 0, "different": 0, "examples": []}
    for x, y in itertools.zip_longest(rows(a), rows(b)):
        out["objects"] += 1
        if x is not None:
            out[x[0]] += 1
        if x != y:
            out["different"] += 1
            if len(out["examples"]) < 5:
                out["examples"].append({"a": str(x)[:300], "b": str(y)[:300]})
    out["equal"] = out["different"] == 0 and out["stampA"] == out["stampB"]
    print(json.dumps(out, indent=1))
    sys.exit(0 if out["equal"] else 1)


if __name__ == "__main__":
    main()
