"""Time share-card renders in a local Worker. NOT RUN YET (2026-11-23). Needs a gap: it refuses to start
beside the world loop or the city task. Windows fonts are copied for the local run only (git-ignored,
never deployed). Writes cloudflare/bench/out/results.json and the PNGs to look at.
"""
import json
import shutil
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = Path("C:/Users/kk/Code/sc-open-quests")
WRANGLER = MAIN / "cloudflare/node_modules/wrangler/bin/wrangler.js"
BASE, N = "http://127.0.0.1:8793", 15


def powershell(cmd: str) -> str:
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True).stdout.strip()


def busy() -> str:
    if (MAIN / ".scratch/planet-cut/RUNNING").exists():
        return "the world loop is running"
    state = powershell("(Get-ScheduledTask kk-SCOpenQuests).State")
    return "" if state in ("Ready", "Disabled") else f"the city task is {state or 'unreadable'}"


def get(path: str) -> tuple[float, bytes]:
    t = time.perf_counter()
    body = urllib.request.urlopen(BASE + path, timeout=60).read()
    return (time.perf_counter() - t) * 1000, body


def memory_mb() -> float:
    return round(float(powershell("(Get-Process workerd | Measure-Object WorkingSet64 -Maximum).Maximum") or 0) / 2**20, 1)


if why := busy():
    sys.exit(f"not now: {why}")
(HERE / "fonts").mkdir(exist_ok=True)
(HERE / "out").mkdir(exist_ok=True)
shutil.copy("C:/Windows/Fonts/segoeui.ttf", HERE / "fonts/ui.ttf")
shutil.copy("C:/Windows/Fonts/simhei.ttf", HERE / "fonts/cjk.ttf")
subprocess.run("npm install --no-audit --no-fund", cwd=HERE, shell=True, check=True)
server = subprocess.Popen(["node", str(WRANGLER), "dev", "--port", "8793", "--ip", "127.0.0.1"], cwd=HERE,
                          stdout=open(HERE / "out/dev.log", "w"), stderr=subprocess.STDOUT)
try:
    for _ in range(60):
        try:
            get("/noop")
            break
        except OSError:
            time.sleep(1)
    res = {"noop_ms": statistics.median(get("/noop")[0] for _ in range(N)), "memory_before_mb": memory_mb(), "cases": []}
    for i in range(6):
        for w in (1200, 600):
            first, png = get(f"/?i={i}&w={w}")
            runs = sorted(get(f"/?i={i}&w={w}")[0] for _ in range(N))
            (HERE / f"out/{i}-{w}.png").write_bytes(png)
            res["cases"].append({"case": i, "width": w, "first_ms": round(first), "median_ms": round(runs[N // 2]),
                                 "max_ms": round(runs[-1]), "bytes": len(png), "memory_mb": memory_mb()})
            if why := busy():
                sys.exit(f"stopped: {why}")
    (HERE / "out/results.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(res, indent=1))
finally:
    subprocess.run(["taskkill", "/PID", str(server.pid), "/T", "/F"], capture_output=True)   # the whole tree
