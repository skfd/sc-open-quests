"""Write design/project-card.svg: one 1200x630 card for the project, from docs/data. An illustration; nothing reads it.

Quests on by default, summed over the counted cities on the last date all of them have. Orange is resurvey. The hills
are the same sum on every date all of them have, from zero. Standard library only; the PNG beside it is a screenshot.
"""
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
OUT = ROOT / "design" / "project-card.svg"
W, H = 1200, 630
LAV, ORANGE, SOFT, INK = "#9a9aff", "#ff6600", "#cdcdff", "#141442"
# short labels for the types that may lead; a new leader stops the script rather than going unnamed
LABELS = {"AddPathSurface": "path surfaces", "AddHousenumber": "house numbers", "AddRoadSurface": "road surfaces",
          "AddOpeningHours": "opening hours", "AddSidewalk": "sidewalks", "CheckShopExistence": "shops still there?",
          "AddCycleway": "cycleways", "AddTactilePavingCrosswalk": "tactile paving"}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def millions(n, places=1):
    return f"{n / 1e6:.{places}f}M"


def numbers():
    cities = {c["id"]: c for c in load(DATA / "cities.json")["cities"]}
    quests = [q["name"] for q in load(DATA / "quests.json")["quests"] if not q["defaultDisabled"]]
    hist = {cid: load(DATA / "history" / f"{cid}.json") for cid in cities}
    for cid, c in cities.items():       # the series must be the one the site prints
        h = hist[cid]
        last = sum(h["quests"][n]["open"][-1] for n in quests if n in h["quests"])
        if last != c["open"]:
            raise SystemExit(f"{cid}: history says {last}, cities.json {c['open']}")
    dates = sorted(set.intersection(*(set(h["dates"]) for h in hist.values())))
    totals, types, aged = [], Counter(), Counter()
    for d in dates:
        total = old = 0
        for h in hist.values():
            i = h["dates"].index(d)
            for n in quests:
                v = h["quests"].get(n)
                if v is None:
                    continue
                total += v["open"][i]   # a None, not counted, stops the script here
                old += v["agedOnly"][i]
                if d == dates[-1]:
                    types[n] += v["open"][i]
                    aged[n] += v["agedOnly"][i]
        totals.append((total, old))
    return cities, dates, totals, types, aged


def t(x, y, s, size, fill="#fff", weight=400, anchor="start"):
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}">{s}</text>')


def split(x, y, total, aged, size=25):
    """A dot, a number, a word, twice, in one line of text so that no font can make them collide."""
    part = lambda colour, n, word: (f'<tspan fill="{colour}">●</tspan> <tspan font-weight="700" fill="#fff">{millions(n)}'
                                    f'</tspan> {word}')
    return t(x, y, part(LAV, total - aged, "to map") + "&#160;&#160; " + part(ORANGE, aged, "to resurvey"), size, SOFT)


def icon(name, x, y, size):
    index = load(ROOT / "docs" / "icons" / "index.json")["quests"]
    svg = (ROOT / "docs" / "icons" / index[name]["icon"]).read_text(encoding="utf-8")
    box = re.search(r'viewBox="([^"]+)"', svg).group(1)
    body = re.sub(r"(?s)^.*?<svg\b[^>]*>|</svg>\s*$", "", svg)
    return f'<svg x="{x:g}" y="{y:g}" width="{size}" height="{size}" viewBox="{box}">{body}</svg>'


def hills(dates, totals, height):
    first, last = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
    top = max(a for a, _ in totals)
    xs = [(date.fromisoformat(s) - first).days / (last - first).days * W for s in dates]
    up = [f"{x:.0f},{H - a / top * height:.1f}" for x, (a, _) in zip(xs, totals)]
    low = [f"{x:.0f},{H - (a - g) / top * height:.1f}" for x, (a, g) in zip(xs, totals)]
    return (f'<polygon fill="{ORANGE}" points="{" ".join(up + low[::-1])}"/>'
            f'<polygon fill="{LAV}" points="{" ".join(low)} {W},{H} 0,{H}"/>')


def main():
    cities, dates, totals, types, aged = numbers()
    total, old = totals[-1]
    first, last = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
    big = millions(total)
    strong = lambda s: f'<tspan font-weight="700" fill="#fff">{s}</tspan>'
    out = [hills(dates, totals, 150),
           t(48, 80, "Open StreetComplete quests", 36, weight=700),
           t(44, 206, big, 118, weight=800),
           t(48, 250, f"in {len(cities)} cities on {last.day} {last:%b %Y}", 26, SOFT),
           split(48, 310, total, old, 25),
           t(48, 356, strong(sum(k > 0 for k in types.values())) + " quest types", 25, SOFT),
           t(48, 402, strong(millions(total - totals[0][0])) + f" more than in {first:%b %Y}", 25, SOFT)]
    top = types.most_common(6)
    for i, (q, k) in enumerate(top):
        x, y, full = 620, 40 + i * 70, 340
        w, g = k / top[0][1] * full, aged[q] / top[0][1] * full
        out += [icon(q, x, y, 54), t(x + 72, y + 21, LABELS[q], 22),
                f'<rect x="{x + 72}" y="{y + 31}" width="{w - g:.1f}" height="18" fill="{LAV}"/>'
                f'<rect x="{x + 72 + w - g:.1f}" y="{y + 31}" width="{g:.1f}" height="18" fill="{ORANGE}"/>',
                t(W - 48, y + 50, millions(k, 2), 27, weight=700, anchor="end")]
    out += [t(48, 604, f"{first:%b %Y}: {millions(totals[0][0])}", 26, INK, 700),
            t(W - 48, 604, f"{last:%b %Y}: {big}", 26, INK, 700, "end"),
            t(W / 2, 604, "data © OpenStreetMap contributors", 20, INK, anchor="middle")]
    OUT.write_text(f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI, -apple-system, '
                   'Roboto, Helvetica, Arial, sans-serif"><defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
                   '<stop stop-color="#2b2b80"/><stop offset="1" stop-color="#141442"/></linearGradient></defs>'
                   f'<rect width="{W}" height="{H}" fill="url(#bg)"/>{"".join(out)}</svg>\n', encoding="utf-8", newline="\n")
    print(dates[-1], totals[0], totals[-1], [(LABELS[q], k, aged[q]) for q, k in top])


if __name__ == "__main__":
    main()
