"""The page's hero tile against the Worker's title, for the same link, on a local `wrangler dev`."""
import re
import sys
import urllib.request

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8791"
LINKS = [
    "?city=toronto",
    "?city=toronto&part=dbb37f753302",
    "?city=toronto&off=AddHousenumber,AddPathSurface",
    "?city=berlin&base=all",
    "?place=be76926172b2&in=ca/eb1eed766420",
    "?place=dbb37f753302&in=ca/eb1eed766420",
    "?place=9fc3a6b4bdda&in=ca/eb1eed766420",
]


def title_of(link: str) -> str:
    html = urllib.request.urlopen(f"{BASE}/{link}", timeout=30).read().decode("utf-8")
    return re.search(r'<meta property="og:title" content="(.*?)">', html).group(1)


bad = 0
with sync_playwright() as p:
    browser = p.chromium.launch(args=["--disable-web-security"])
    for link in LINKS:
        page = browser.new_page()
        page.goto(f"{BASE}/{link}")
        page.wait_for_function(
            "() => { const v = document.querySelector('#tiles .tile.hero .value'); return v && /\\d/.test(v.textContent); }",
            timeout=60000)
        hero = page.inner_text("#tiles .tile.hero .value").strip()
        name = page.inner_text("#place-name").strip() if page.query_selector("#place-name") else ""
        weeks = page.inner_text("#tiles .tile:nth-child(4)").replace("\n", " | ")
        url = page.url.split("/", 3)[3]
        title = title_of(link)
        ok = title.startswith(hero + " open StreetComplete") or f" {hero} StreetComplete" in title
        bad += not ok
        print(f"{'ok  ' if ok else 'MISS'} {link}\n     page: {hero} | {name} | {weeks} | now {url}\n     card: {title}")
        page.close()
    browser.close()
sys.exit(1 if bad else 0)
