"""Write the release that first offered each quest to docs/data/quest-releases.json, for the site's
"Only quests the app had then" switch.

    git clone --bare --filter=blob:limit=200k https://github.com/streetcomplete/StreetComplete.git <dir>
    python tools/sc_first_release.py <dir>

Reads every stable tag's quest registry with git alone, nothing is built (45 s, 227 MB of clone). A quest's
date is the GitHub release date of docs/data/sc-releases.json, so a step sits on its release line; the tag's
own date where GitHub has no release. Writes {"quests": {"AddPathSurface": {"version": "v6.0", "date":
"2018-07-01"}, ...}} for every quest of the newest data/quests/v*.json, and fails on one it cannot find.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import run  # noqa: E402

OUT = ROOT / "docs" / "data" / "quest-releases.json"
RELEASES = ROOT / "docs" / "data" / "sc-releases.json"

# Where the registry lived: data/QuestTypes.java to v2, then the module, then the v63.3 registry. Some
# tags hold two of them, and only their union is the list.
REGISTRY = re.compile(r"(?:quests/QuestsModule\.kt|quests/QuestModule\.(?:kt|java)|quests/QuestTypesRegistry\.kt|data/QuestTypes\.java)$")
QUEST = re.compile(r"\b((?:Add|Check|Determine|Mark|Specify|Show|Osm|Set|Change|Is|Answer)[A-Z]\w+)\s*(?:\(|\.class)")
UNSTABLE = re.compile(r"beta|alpha|rc", re.I)
STRAY_TAGS = {"v0.3"}   # an ordinary commit of 2017-08-15; the real 0.3 is the tag "0.3"

# A quest under a new name is the same question, so it counts from its predecessor's first release.
# Only a rename, a split or a replacement SC's changelog names. Not AddIsAmenityIndoor, though it took
# over AddIsDefibrillatorIndoor: it asks for far more places than defibrillators, so it counts as new.
PREDECESSOR = {
    "AddIsBuildingUnderground": "IsBuildingUnderground",                         # v10.0, renamed
    "AddWheelchairAccessPublicTransport": "AddWheelChairAccessPublicTransport",  # v14.0, renamed
    "AddWheelchairAccessToilets": "AddWheelChairAccessToilets",                  # v14.0, renamed
    "AddAmenityCover": "AddPicnicTableCover",                                    # v53.0, barbecues added
    "AddCrossingMarkings": "AddCrossingType",                                    # v57.0, split in two
    "AddCrossingSignals": "AddCrossingType",
    "AddMopedAccess": "AddProhibitedForMoped",                                   # v58.1, renamed
    "AddCaravans": "AddCampType",                                                # v63.0, split up
    "AddTents": "AddCampType",
    "AddGeneralAccess": "AddPlaygroundAccess",                                   # v64.0, with AddTowerAccess
    "AddChargingStationSocket": "AddChargingStationCapacity",                    # v64.0, replaced by the two
    "AddChargingStationMotorcar": "AddChargingStationCapacity",
}


def quest_names(source: str, classes: set[str]) -> set[str]:
    """The quests a registry's source names, leaving out whatever has no source file of its own."""
    return set(QUEST.findall(source)) & classes


def first_tags(registries: list[tuple[str, set[str]]]) -> dict[str, str]:
    """Quest name -> the first tag that registers it; registries are oldest first."""
    first = {}
    for tag, quests in registries:
        for q in quests:
            first.setdefault(q, tag)
    return first


def first_releases(names, first: dict[str, str], dates: dict[str, str]) -> dict[str, dict]:
    """The file's quests: each of names with its version and date, through PREDECESSOR."""
    out = {}
    for q in names:
        tag = first.get(PREDECESSOR.get(q, q))
        if tag is None:
            raise SystemExit(f"{q} is in no tag's registry: has the registry moved, or is a tag missing?")
        out[q] = {"version": tag, "date": dates[tag]}
    return out


def read_registries(clone: Path) -> tuple[list[tuple[str, set[str]]], dict[str, str]]:
    """Every stable tag's quests, oldest first, and each tag's own date."""
    def git(*args) -> str:
        return subprocess.run(["git", "-C", str(clone), *args], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", check=True).stdout
    # one process for all the blobs: a git show each takes minutes on Windows
    cat = subprocess.Popen(["git", "-C", str(clone), "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def show(spec: str) -> str:
        cat.stdin.write(spec.encode() + b"\n")
        cat.stdin.flush()
        size = int(cat.stdout.readline().split()[2])
        data = cat.stdout.read(size)
        cat.stdout.read(1)
        return data.decode("utf-8", "replace")

    registries, dates = [], {}
    for line in git("for-each-ref", "--sort=creatordate", "--format=%(refname:short) %(creatordate:short)", "refs/tags").splitlines():
        tag, date = line.split()
        if UNSTABLE.search(tag) or tag in STRAY_TAGS:
            continue
        files = git("ls-tree", "-r", "--name-only", tag).splitlines()
        classes = {f.rsplit("/", 1)[-1].rsplit(".", 1)[0] for f in files if f.endswith((".kt", ".java"))}
        source = " ".join(show(f"{tag}:{f}") for f in files if REGISTRY.search(f))
        registries.append((tag, quest_names(source, classes)))
        dates[tag] = date
    cat.stdin.close()
    cat.wait()
    return registries, dates


def newest_registry() -> Path:
    return max((ROOT / "data" / "quests").glob("v*.json"), key=lambda p: run.version_tuple(p.name))


def main() -> None:
    registries, dates = read_registries(Path(sys.argv[1]))
    dates |= {r["version"]: r["date"] for r in json.loads(RELEASES.read_text(encoding="utf-8"))["releases"]}
    names = [q["name"] for q in json.loads(newest_registry().read_text(encoding="utf-8"))["quests"]]
    quests = first_releases(names, first_tags(registries), dates)
    run.write_json(OUT, {"quests": quests})
    print(f"{len(quests)} quests from {len(registries)} tags -> {OUT}")


if __name__ == "__main__":
    main()
