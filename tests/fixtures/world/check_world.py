"""Drive world place pages against this fixture (needs `pip install playwright`).

    python -m http.server 8771 --bind 127.0.0.1          # from the repo root, in another shell
    python tests/fixtures/world/check_world.py [port] [screenshot.png]

The fixture (DESIGN.md, "World places published: the files") publishes 2026-11-01..02 in schema 2 (token "t1",
back 11-01): Thiergarten (a neighbourhood of Plauen, Saxony; Plauen is not a counted city), Plauen with four
children, and Germany under world. Pages read the site's own docs/data and docs/places. Also checks that pages without world data
read exactly as with the app.js of HEAD (served in its place). Exits 1 if a check failed.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
port = sys.argv[1] if len(sys.argv) > 1 else "8771"
shot = sys.argv[2] if len(sys.argv) > 2 else None
SHOW = bool(os.environ.get("SHOW_ERRORS"))   # print every console error and page error as it happens
BASE = f"http://127.0.0.1:{port}/docs/"
W = "world=../tests/fixtures/world/"
SX = "de/3e1aa55a1b9b"
THIER, PLAUEN, VOGT, DE = "1dfbf4ad13ac", "99f5bf7c532f", "a28f853e0825", "567d16987209"
repo = Path(__file__).resolve().parents[3]
old_app = subprocess.run(["git", "show", "HEAD:docs/app.js"], cwd=repo, capture_output=True, check=True).stdout

failed = False


def check(ok, what):
    global failed
    failed |= not ok
    print(("ok  " if ok else "FAIL"), what)


def load_error(e):   # the browser's own line for a file that is not there or a host that does not answer
    return e.startswith("Failed to load resource")


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1200, "height": 1500}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))

    requests = []
    page.on("request", lambda r: requests.append(r.url))
    if SHOW:
        page.on("console", lambda m: m.type == "error" and print("    console:", m.text))
        page.on("pageerror", lambda e: print("    pageerror:", e))

    def asked(part):   # the world files the page asked for, by a piece of the URL
        return [u.split("/tests/fixtures/world/")[1] for u in requests if "/tests/fixtures/world/" in u and part in u]

    def go(query, settle=400):
        errors.clear()
        requests.clear()
        page.goto(f"{BASE}?{query}", wait_until="networkidle")
        page.wait_for_timeout(settle)

    def text(sel):
        return page.inner_text(sel)

    def world_page():
        return page.is_visible("#view-city") and not page.is_visible("#view-places")

    # Thiergarten: its own place file, the whole series
    go(f"{W}&place={THIER}&in={SX}")
    tiles = text("#tiles")
    check(world_page(), "Thiergarten draws in the place page")
    check(text("#place-name") == "Thiergarten" and "neighbourhood" in text("#place-kind"), "Thiergarten: name and kind")
    check("As of Nov 2, 2026" in text("#place-asof"), "Thiergarten: as of the latest date: " + text("#place-asof"))
    crumbs = text("#place-crumbs")
    check(all(n in crumbs for n in ("Germany", "Saxony", "Vogtlandkreis", "Plauen")), "Thiergarten: crumbs " + crumbs.replace("\n", " "))
    # default selection: bench 10, housenumber 41, opening hours 5 (aged 4); way lit is off by default
    check("Open quests\n56\n4 more than the day before" in tiles, "Thiergarten: open 56, +4 on the day before")
    check("Need mapping\n52" in tiles and "Aged, need resurvey\n4" in tiles, "Thiergarten: mapping 52, aged 4")
    check("Since Nov 1\n+4" in tiles, "Thiergarten: change since the first date")
    check("Most open\n41" in tiles, "Thiergarten: most open 41")
    check(page.locator("#chart-total .uplot canvas").count() > 0, "Thiergarten: chart drawn")
    body = text("#quest-table tbody")
    check("Not offered in Thiergarten" in body, "Thiergarten: a quest the app leaves out of DE is grouped as not offered")
    fuel = page.locator("#quest-table tr", has_text="AddFuelSelfService")
    check(fuel.count() == 1 and "only in" in fuel.inner_text(), "Thiergarten: AddFuelSelfService says where it is offered")
    house = page.locator("#quest-table tr", has_text="AddHousenumber").inner_text()
    check("41" in house and "+1" in house, "Thiergarten: AddHousenumber 41, +1")
    # AddRoadName: counted by the world, offered in DE, not in the file: 0 open, so it is in the series (the table
    # folds quests with nothing open away); AddFuelSelfService, not offered in DE, stays out
    got = page.evaluate("() => [hist.quests.AddRoadName, hist.quests.AddFuelSelfService === undefined, hist.dates]")
    check(got == [{"open": [0, 0], "agedOnly": [0, 0]}, True, ["2026-11-01", "2026-11-02"]],
          f"Thiergarten: a counted quest missing from the place file is 0 on both days: {got}")
    check(asked("latest.json") == ["latest.json"], f"Thiergarten: latest.json asked without ?v {asked('latest.json')}")
    check(asked("place/") == [f"place/1d/{THIER}.json?v=t1"], f"Thiergarten: its place file asked with ?v=t1 {asked('place/')}")
    check(asked("children/") == [], f"Thiergarten: no children file asked, its parent's neither {asked('children/')}")
    check(not errors, f"Thiergarten: no console errors {errors}")
    if shot:
        page.screenshot(path=shot, full_page=False)

    # the decoder over a longer span: `from` starts the series later, a point past latest.date is not read
    got = page.evaluate("""() => {
      const latest = { first: "2026-11-29", date: "2026-12-03", quests: ["AddHousenumber", "AddBenchBackrest"] };
      const quests = { AddHousenumber: [[0, 10, 0], [2, 12, 0], [4, 9, 0], [5, 99, 9]], AddWayLit: [[3, 4, 1], [7, 5, 5]] };
      const row = (s) => s && [s.dates, s.quests.AddHousenumber.open, s.quests.AddWayLit.open, s.quests.AddWayLit.agedOnly,
                               s.quests.AddBenchBackrest.open, s.meta.length];
      return [row(worldSeries(latest, { quests }, "DE")), row(worldSeries(latest, { from: 2, quests }, "DE")),
              row(worldSeries(latest, { from: 4, quests }, "DE")), worldSeries(latest, { from: 5, quests }, "DE")];
    }""")
    days = ["2026-11-29", "2026-11-30", "2026-12-01", "2026-12-02", "2026-12-03"]
    check(got[0] == [days, [10, 10, 12, 12, 9], [0, 0, 0, 4, 4], [0, 0, 0, 1, 1], [0, 0, 0, 0, 0], 5],
          f"the series from change points, a point past the newest day not read: {got[0]}")
    check(got[1] == [days[2:], [12, 12, 9], [0, 4, 4], [0, 1, 1], [0, 0, 0], 3], f"from 2 starts the series on day 2: {got[1]}")
    check(got[2] == [days[4:], [9], [4], [1], [0], 1] and got[3] is None,
          f"from the newest day is one day, from past it is not counted: {got[2:]}")

    # the same on the page: Thiergarten's file changed on its way to the page
    thier = json.loads((Path(__file__).parent / "place" / "1d" / f"{THIER}.json").read_text(encoding="utf-8"))

    def served(change):
        def handle(route):
            seen.append(route.request.url)
            route.fulfill(body=json.dumps(change(json.loads(json.dumps(thier)))), content_type="application/json")
        return handle

    def with_file(change, what):
        seen.clear()
        page.route(f"**/place/1d/{THIER}.json*", served(change))   # the * takes the ?v
        go(f"{W}&place={THIER}&in={SX}")
        page.unroute(f"**/place/1d/{THIER}.json*")
        check(len(seen) == 1, f"{what}: the changed file was the one served {seen}")

    seen = []

    def newer(f):   # a publish after the latest.json in hand: day 2 exists in the file only
        f["quests"]["AddHousenumber"].append([2, 999, 50])
        f["quests"]["AddRoadName"] = [[2, 77, 7]]
        return f
    with_file(newer, "clip")
    check(text("#tiles") == tiles, "clip: a place file with points past latest.date shows the same tiles")
    check(text("#quest-table tbody") == body, "clip: and the same quest table")

    def late(f):
        f["from"] = 1
        return f
    with_file(late, "from 1")
    t = text("#tiles")
    check(world_page() and "Open quests\n56" in t and "Since Nov 1" not in t and "the day before" not in t,
          "from 1: Thiergarten's series is Nov 2 alone, 56 open with no change to show\n      " + t.replace("\n", " / ")[:200])

    def later(f):
        f["from"] = 2
        return f
    with_file(later, "from 2")
    check(page.is_visible("#view-places") and "Not counted yet" in text("#place-page"), "from 2, past latest.date: not counted")

    # Plauen: its children from children/<self>
    go(f"{W}&place={PLAUEN}&in={SX}")
    page.mouse.wheel(0, 4000)
    page.wait_for_timeout(300)
    tiles = text("#tiles")
    check(world_page() and "Open quests\n1,078\n17 fewer than the day before" in tiles, "Plauen: open 1,078, −17")
    kids = text("#place-children")
    want = ["Thiergarten\tneighbourhood\t56\t+4", "Altstadt\tmacrohood\t25\t−5", "Haselbrunn\tmacrohood\t4\t±0", "Jößnitz\tlocality\t3\t+1"]
    check(all(w in kids for w in want), "Plauen: children with open and change\n      " + kids[:400].replace("\n", " / "))
    check("Since Nov 1" in kids and "Open quests in each on Nov 2" in kids, "Plauen: the change is since back, the counts on the newest day")
    check(f"Inside Plauen" in kids, "Plauen: the name layer's children still listed")
    check(asked("place/") == [f"place/99/{PLAUEN}.json?v=t1"] and asked("children/") == [f"children/99/{PLAUEN}.json?v=t1"],
          f"Plauen: its place and children files asked with ?v=t1, no other {asked('place/') + asked('children/')}")
    check(not errors, f"Plauen: no console errors {errors}")
    # tick and pin: the numbers stay the world's
    page.locator("#quest-table tr", has_text="AddHousenumber").locator("input[type=checkbox]").click()
    page.wait_for_timeout(300)
    check(world_page() and text("#place-name") == "Plauen" and "Open quests\n198" in text("#tiles"), "Plauen: unticking AddHousenumber gives 198")
    page.locator("#quest-table tr", has_text="AddCycleway").locator("button.pin-btn").click()
    page.wait_for_timeout(300)
    check(world_page() and page.locator("#multiples .card .uplot").count() == 1 and "pin=AddCycleway" in page.url, "Plauen: a pin charts on the world page")
    check("world=../tests/fixtures/world/" in page.url, "Plauen: the link keeps ?world=")
    page.locator("#place-children a", has_text="Thiergarten").first.click()
    page.wait_for_timeout(600)
    check(world_page() and text("#place-name") == "Thiergarten" and f"place={THIER}" in page.url, "Plauen: a child's link opens its world page")
    check(not errors, f"Plauen: no console errors after ticks and links {errors}")

    # Germany: its own place file; its parent is world, whose children file the page does not read
    go(f"{W}&place={DE}")
    tiles = text("#tiles")
    check(world_page() and "Open quests\n609,100" in tiles, "Germany: open 609,100 from its place file")
    kids = text("#place-children")
    check("Saxony\tregion\t39,900\t−100" in kids, "Germany: Saxony 39,900, −100")
    check(asked("place/") == [f"place/56/{DE}.json?v=t1"] and asked("children/") == [f"children/56/{DE}.json?v=t1"],
          f"Germany: its place and children files asked with ?v=t1 {asked('place/') + asked('children/')}")
    check(not any("world.json" in u for u in requests), "Germany: no request for children/world.json")
    check(not errors, f"Germany: no console errors {errors}")

    # not counted by the world: as before (only the 404 for its place file in the console)
    go(f"{W}&place={VOGT}&in={SX}")
    check(page.is_visible("#view-places") and "Not counted yet" in text("#place-page"), "Vogtlandkreis: not counted, as before")
    check(all(load_error(e) for e in errors), f"Vogtlandkreis: only the missing file in the console {errors}")
    # the world host does not answer
    go(f"world=http://127.0.0.1:9/&place={THIER}&in={SX}", settle=1000)
    check(page.is_visible("#view-places") and "Not counted yet" in text("#place-page"), "no world host: not counted, as before")
    check(all(load_error(e) for e in errors), f"no world host: only the failed request in the console {errors}")

    # a world page, then a counted city: the city's own numbers
    go(f"{W}&place={THIER}&in={SX}")
    page.goto(f"{BASE}?{W}&city=guelph", wait_until="networkidle")
    page.wait_for_timeout(400)
    check(text("#place-name") == "Guelph" and "Open quests over time in Guelph" in text("#chart-title"), "Guelph after a world page")

    # "Change place" on a world page: the city chosen replaces it
    go(f"{W}&place={THIER}&in={SX}")
    page.click("#place-change")
    page.fill("#city-search", "Guelph")
    page.keyboard.press("Enter")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    check(text("#place-name") == "Guelph" and "city=guelph" in page.url and "place=" not in page.url
          and page.is_visible("#view-city") and "Open quests over time in Guelph" in text("#chart-title"),
          "Change place on a world page opens Guelph")
    check(not errors, f"Change place: no console errors {errors}")

    # pages without world data read as with HEAD's app.js
    NONE = "world=../tests/fixtures/world/none/"
    same = [f"city=guelph", "city=toronto&pin=AddBusStopShelter,AddBenchBackrest", "city=toronto&part=b9ec4292cfec",
            "view=compare&city=ottawa", "view=places", "place=d5654a875adf", f"place={DE}", "place=eb1eed766420",
            f"place={THIER}&in={SX}", f"place={PLAUEN}&in={SX}", "place=000000000000"]

    def snapshot(query):
        go(f"{NONE}&{query}")
        page.mouse.wheel(0, 20000)
        was, now = None, text("main")
        for _ in range(20):   # the parts card loads as it nears the screen: wait until the page holds still
            if now == was:
                break
            page.wait_for_timeout(500)
            was, now = now, text("main")
        return now, [e for e in errors if not load_error(e)]

    new = {q: snapshot(q) for q in same}
    page.route("**/docs/app.js", lambda route: route.fulfill(body=old_app, content_type="text/javascript"))
    for q in same:
        before = snapshot(q)
        check(before[0] == new[q][0] and not new[q][1], f"unchanged without world data: {q}" + (f" {new[q][1]}" if new[q][1] else ""))
    browser.close()

sys.exit(1 if failed else 0)
