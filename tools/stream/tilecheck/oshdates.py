"""Dates worth testing a history-file reader at (tilestore at, against osmium time-filter): where an object's
timestamps run backwards, the moments at which osmium's rule gives two versions of it; and a few timestamps of
versions that replace a visible one, to test a date equal to a version's own second.

  oshdates.py X.osh.pbf > dates.json
"""
import json
import sys

import osmium


def main():
    out = {"versions": 0, "backwards": 0, "doubles": [], "exact": []}
    run = []  # the versions of the object being read: (timestamp, visible, version)
    key = None

    def close():
        ts = [r[0] for r in run]
        for i in range(1, len(run)):
            if ts[i] < ts[i - 1]:
                out["backwards"] += 1
        # two versions at once: version i and a later one j, both visible, both at the date by the rule
        live = []
        for i, (t, vis, _) in enumerate(run):
            end = ts[i + 1] if i + 1 < len(run) else float("inf")
            if vis and t < end:
                live.append((t, end, i))
        for a in range(len(live)):
            for b in range(a + 1, len(live)):
                lo, hi = max(live[a][0], live[b][0]), min(live[a][1], live[b][1])
                if lo < hi and len(out["doubles"]) < 50:
                    out["doubles"].append({"object": key, "versions": [run[live[a][2]][2], run[live[b][2]][2]],
                                           "from": lo, "before": hi if hi != float("inf") else None})

    for o in osmium.FileProcessor(sys.argv[1]):
        k = ("n" if o.is_node() else "w" if o.is_way() else "r") + str(o.id)
        if k != key:
            if run:
                close()
            run, key = [], k
        t = int(o.timestamp.timestamp())
        if run and run[-1][1] and o.visible and len(out["exact"]) < 2000 and out["versions"] % 9973 == 0:
            out["exact"].append({"object": k, "version": o.version, "at": t})
        run.append((t, o.visible, o.version))
        out["versions"] += 1
    if run:
        close()
    out["exact"] = out["exact"][:: max(1, len(out["exact"]) // 5)][:5]
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
