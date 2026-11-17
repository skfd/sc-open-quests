"""How many of the big-polygon rule's open cases (fork E's planet day 5172) the store's context resolves, measured where
a clip store has the data: the Europe clip of 11-07 cut into a store, asked by `store_context.py day` around diff 5172.

  python tools/stream/tilecheck/ctx5172.py --ctx DIR --diff 5172.osc.gz --nodes planet.loc --plan plan.json --out OUT

The cover runs on the whole planet diff twice, without and with the Europe store's answers (node places from the planet
node file, read only; no state rows: they do not change these counts). The answers exist only for Europe: outside it a
way or node is not in the clip's store, and the cover falls back as it does without them (today's refs as the old
ones, tags unknown). Per class: how many cases, how many in Europe (the clip's store holds the element), how many of
those resolved. The planet store holds every element, so outside Europe the same code is projected to resolve them."""
import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/stream"))
import stream as S  # noqa: E402
import store_context as SC  # noqa: E402
import world_tier2 as W  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", type=Path, required=True)
    ap.add_argument("--diff", type=Path, required=True)
    ap.add_argument("--nodes", type=Path, required=True)
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    t = time.time()
    last_node, last_way, last_rel, _ = S.read_diff(a.diff)
    print(f"diff: {len(last_node):,} nodes, {len(last_way):,} ways, {len(last_rel):,} relations, {time.time() - t:.0f} s", flush=True)
    old_places = W.NodeFile(a.nodes)
    new_places = W.NodeFile(a.nodes, overlay={n: (v[4] if v[2] else None) for n, v in last_node.items()})
    dc = SC.DayContext.load(a.ctx, last_node, last_way, last_rel, W.contained_kind, W.wanted_relation)
    h = dc.hooks(W.container_kind)
    eu_ways = set(dc.b.ways) | set(dc.a.ways)
    eu_nodes = {n for n, i in dc.b.nodes.items() if i["tags"] is not None}

    # the hooks with the clip's fallbacks: outside Europe a way's old refs are today's, as without the store
    def old_refs(w):
        r = dc.old_refs(w)
        if r is not None:
            return r
        v = last_way[w]
        return v[4] if v[2] and v[4] else None

    cells = W.plan_cells(json.loads(a.plan.read_text(encoding="utf-8")))
    res = {}
    for label, kw in (("rule", {}), ("rule + Europe store", {"old_refs": old_refs, "old_tags": h["old_tags"],
                                                              "old_node_tags": h["old_node_tags"],
                                                              "member_refs": h["member_refs"],
                                                              "extra_candidates": h["extra_candidates"]})):
        t = time.time()
        boxed: set = set()
        codes, stats, secs = W.cover(last_node, last_way, last_rel, old_places, new_places, None, boxed_out=boxed, **kw)
        rects = W.rectangles(codes, cells)
        res[label] = {"stats": {k: v for k, v in stats.items()}, "rectangles": sum(len(r) for r in rects.values()),
                      "km2": round(W.rect_km2(rects), 1), "seconds": round(time.time() - t, 1)}
        print(label, json.dumps(res[label]), flush=True)

    # the classes, counted directly
    c = Counter()
    for w, v in last_way.items():
        if v[0] > 1 or not v[2]:  # it existed the day before: its old ring's tags are a question
            c["existing ways changed"] += 1
            if w in eu_ways:
                c["  in Europe"] += 1
                if dc.old_tags("w", w) is not None:
                    c["  in Europe, old tags known"] += 1
    for n, v in last_node.items():
        if not v[2]:
            c["deleted nodes"] += 1
            if n in eu_nodes:
                c["  deleted, in Europe"] += 1
                ot = dc.old_node_tags(n)
                c["  deleted, in Europe, untagged the day before"] += int(not ot)
                c["  deleted, in Europe, a container read it"] += int(bool(W.contained_kind(ot)))
    c["store container boxes (Europe)"] = len(h["extra_candidates"])
    kinds = Counter(x[2] for x in h["extra_candidates"])
    out = {"cover": res, "classes": dict(c), "containerBoxesByReason": dict(kinds),
           "addressNodesKnown": int(len(h["address_nodes"]))}
    (a.out / "ctx5172.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
