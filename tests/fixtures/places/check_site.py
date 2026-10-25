"""Drive the place pages of a test site and screenshot them (needs `pip install playwright`).

    python tests/fixtures/places/make_test_site.py <dir>
    python -m http.server 8765 --bind 127.0.0.1 --directory <dir>     # in another shell
    python tests/fixtures/places/check_site.py [out-dir]

Prints each page's console errors; exits 1 if there were any or a check failed.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8765/docs/"
out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
out.mkdir(parents=True, exist_ok=True)
ON, PEI, BE = "ca/eb1eed766420", "ca/5847d360c128", "de/59f212f34e73"
PAGES = [   # name, query, text that must be on the page
    ("city-unchanged", "city=toronto&pin=AddBusStopShelter,AddBenchBackrest", "Open quests over time in Toronto"),
    ("compare-unchanged", "view=compare&city=ottawa", "Cities compared"),
    ("places-root", "view=places", "Countries"),
    ("country-canada", "place=d5654a875adf", "places counted"),
    ("region-ontario", "place=eb1eed766420", "places counted"),
    ("city-toronto", f"place=9fc3a6b4bdda&in={ON}", "Parts of Toronto"),
    ("part-annex", f"place=b9ec4292cfec&in={ON}", "Quests in Annex"),
    ("part-annex-ticks", f"place=b9ec4292cfec&in={ON}&base=none&on=AddBenchBackrest", "1 of"),
    ("not-counted", f"place=bac51b596c88&in={ON}", "Ask for this place"),
    ("berlin", "place=59f212f34e73", "Open Berlin"),
    ("not-found", "place=000000000000", "cannot find"),
]

failed = False
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1200, "height": 1400}, device_scale_factor=1)
    errors, requests = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("request", lambda r: requests.append(r.url))
    for name, query, want in PAGES:
        errors.clear(); requests.clear()
        page.goto(f"{BASE}?data=data&{query}", wait_until="networkidle")
        page.wait_for_timeout(300)
        page.screenshot(path=str(out / f"{name}.png"), full_page=True)
        text = page.inner_text("main")
        ok = want in text and not errors
        failed |= not ok
        shards = sorted({u.split("/places/")[1] for u in requests if "/places/" in u})
        print(("ok  " if ok else "FAIL"), name, page.url.split("?")[1], "| places files:", shards)
        for e in errors:
            print("     page error:", e)
    # search: index names with no country chosen, then a country's places (accent-blind)
    page.goto(f"{BASE}?data=data&view=places", wait_until="networkidle")
    page.fill("#place-search", "ontar")
    page.wait_for_timeout(400)
    r1 = page.inner_text("#place-results")
    page.select_option("#place-scope", "de")
    page.fill("#place-search", "kopenick")
    page.wait_for_timeout(1500)
    page.screenshot(path=str(out / "search-de.png"), full_page=False)
    r2 = page.inner_text("#place-results")
    page.select_option("#place-scope", "ca")
    page.fill("#place-search", "annex")
    page.wait_for_timeout(1500)
    r3 = page.inner_text("#place-results")
    page.screenshot(path=str(out / "search-ca.png"), full_page=False)
    page.click("#place-results a >> nth=0")
    page.wait_for_timeout(800)
    for label, got, want in [("index", r1, "Ontario"), ("de", r2, "Köpenick"), ("ca", r3, "Annex\ncounted\nneighbourhood\nToronto · Ontario · Canada")]:
        ok = want in got
        failed |= not ok
        print(("ok  " if ok else "FAIL"), "search", label, "|", got.replace("\n", " / ")[:160])
    print("after picking:", page.url.split("?")[1], "| errors:", errors)
    failed |= bool(errors)
    browser.close()
sys.exit(1 if failed else 0)
