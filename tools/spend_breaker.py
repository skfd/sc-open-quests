"""Spend breaker: keep the Cloudflare hosting under $50 a month.

    python tools/spend_breaker.py            check: print the estimate; past TRIP_USD, trip
    python tools/spend_breaker.py --dry-run  estimate and say what a trip would do; change nothing
    python tools/spend_breaker.py --status   print the latch and the estimate
    python tools/spend_breaker.py --reset    owner only: clear the latch and turn the data domain back on
    python tools/spend_breaker.py --reset --force   the same while the estimate is still past the line
    python tools/spend_breaker.py --dry-run --simulate-class-a 12000000   pretend extra operations happened

What costs money here is R2 alone. The site is Workers static assets on Workers Free (free and unlimited,
no bill), egress is free, and r2.dev access is off on every bucket. R2 bills past a monthly free tier with
no cap of its own: Cloudflare's spending limits cover Workers and Durable Objects only, and budget alerts
only send email. So this script is the cap.

The estimate comes from the account's GraphQL analytics (R2 operations by action, R2 storage per bucket),
priced from developers.cloudflare.com/r2/pricing (read 2026-11-19). It errs high: any action not on the
Class B or free lists is priced as Class A, units round up as Cloudflare rounds them, storage is the
window's peak for the whole month, and the window is the stricter of the calendar month and the trailing
30 days (the billing period starts on the purchase date, not the 1st).

A trip does two things and the latch keeps them until the owner runs --reset:
  1. turns off public access on sc-data.comentality.com (the one public R2 surface; the bucket keeps its
     files and the domain stays attached), so readers stop costing reads;
  2. writes the latch file, and every publisher that calls gate() refuses to write to R2.

Publishers call gate(planned_class_a=N) before writing: it refuses if the latch is set, or if the estimate
plus N more Class A writes would pass TRIP_USD. strict=True (the world data publisher) also refuses when
the analytics cannot be read; the site publish and the archive backup cannot reach $50 on their own, so
they log the failure and go on.

Run hourly by Task Scheduler (kk-SCOpenQuests-spend) and at the start of each publish.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cloud_publish  # noqa: E402  (read_env)

TRIP_USD = 40.0      # under the owner's $50: analytics lag, an hourly check, and costs this cannot see
WARN_USD = 20.0
DATA_BUCKET = "sc-open-quests-data"
DATA_DOMAIN = "sc-data.comentality.com"
LATCH = Path(os.environ.get("SC_OPEN_QUESTS_SPEND_LATCH",
                            Path.home() / ".config" / "sc-open-quests" / "spend-breaker.json"))
API = "https://api.cloudflare.com/client/v4"

# R2 Standard, developers.cloudflare.com/r2/pricing (read 2026-11-19)
PRICE_A = 4.50       # $ per million Class A
PRICE_B = 0.36       # $ per million Class B
PRICE_GB = 0.015     # $ per GB-month
FREE_A = 1_000_000
FREE_B = 10_000_000
FREE_GB = 10
CLASS_B = {"HeadBucket", "HeadObject", "GetObject", "UsageSummary", "GetBucketEncryption",
           "GetBucketLocation", "GetBucketCors", "GetBucketLifecycleConfiguration"}
FREE_OPS = {"DeleteObject", "DeleteBucket", "AbortMultipartUpload"}


class Tripped(RuntimeError):
    """The breaker refuses: the latch is set, or the planned writes would pass the trip line."""


def log(msg: str) -> None:
    print(f"[spend] {msg}", flush=True)


# ---- pricing (pure) ----

def classify(action: str) -> str:
    if action in FREE_OPS:
        return "free"
    if action in CLASS_B:
        return "B"
    return "A"       # Class A by list, and anything unknown: price it high


def price(class_a: int, class_b: int, storage_bytes: int) -> dict:
    """Dollars past the free tier, with Cloudflare's rounding up to the next million or GB."""
    a = math.ceil(max(0, class_a - FREE_A) / 1e6) * PRICE_A
    b = math.ceil(max(0, class_b - FREE_B) / 1e6) * PRICE_B
    gb = math.ceil(max(0.0, storage_bytes / 1e9 - FREE_GB)) * PRICE_GB
    return {"class_a": class_a, "class_b": class_b, "storage_gb": round(storage_bytes / 1e9, 3),
            "usd_a": round(a, 2), "usd_b": round(b, 2), "usd_storage": round(gb, 2),
            "usd": round(a + b + gb, 2)}


def tally(op_groups: list[dict], storage_groups: list[dict]) -> tuple[int, int, int]:
    """(Class A, Class B, storage bytes) from the GraphQL groups. Storage: each bucket's peak, summed."""
    ops = {"A": 0, "B": 0, "free": 0}
    for g in op_groups:
        ops[classify(g["dimensions"]["actionType"])] += int(g["sum"]["requests"])
    peak: dict[str, int] = {}
    for g in storage_groups:
        b = g["dimensions"]["bucketName"]
        size = int(g["max"]["payloadSize"] or 0) + int(g["max"]["metadataSize"] or 0)
        peak[b] = max(peak.get(b, 0), size)
    return ops["A"], ops["B"], sum(peak.values())


# ---- Cloudflare ----

def _call(env: dict, method: str, url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {env['CLOUDFLARE_API_TOKEN']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


QUERY = """query($a:String!,$s:Time!,$e:Time!){viewer{accounts(filter:{accountTag:$a}){
r2OperationsAdaptiveGroups(limit:10000,filter:{datetime_geq:$s,datetime_leq:$e}){sum{requests} dimensions{actionType}}
r2StorageAdaptiveGroups(limit:10000,filter:{datetime_geq:$s,datetime_leq:$e}){max{payloadSize metadataSize} dimensions{bucketName}}
}}}"""


def usage(env: dict, start: dt.datetime, end: dt.datetime) -> tuple[int, int, int]:
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    d = _call(env, "POST", f"{API}/graphql", {"query": QUERY, "variables": {
        "a": env["CLOUDFLARE_ACCOUNT_ID"], "s": start.strftime(fmt), "e": end.strftime(fmt)}})
    if d.get("errors"):
        raise RuntimeError(f"R2 analytics: {d['errors']}")
    acc = d["data"]["viewer"]["accounts"][0]
    return tally(acc["r2OperationsAdaptiveGroups"], acc["r2StorageAdaptiveGroups"])


def estimate(env: dict, now: dt.datetime | None = None, extra_a: int = 0, extra_b: int = 0) -> dict:
    """The stricter of the calendar month and the trailing 30 days."""
    now = now or dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    windows = {"month": now.replace(day=1, hour=0, minute=0, second=0),
               "30 days": now - dt.timedelta(days=30)}
    best = None
    for name, start in windows.items():
        a, b, s = usage(env, start, now)
        p = price(a + extra_a, b + extra_b, s)
        p["window"] = name
        if best is None or p["usd"] > best["usd"]:
            best = p
    best["at"] = now.isoformat()
    return best


def set_domain(env: dict, enabled: bool) -> None:
    url = f"{API}/accounts/{env['CLOUDFLARE_ACCOUNT_ID']}/r2/buckets/{DATA_BUCKET}/domains/custom/{DATA_DOMAIN}"
    d = _call(env, "PUT", url, {"enabled": enabled})
    if not d.get("success") or d.get("result", {}).get("enabled") is not enabled:
        raise RuntimeError(f"could not set {DATA_DOMAIN} enabled={enabled}: {d.get('errors')}")


def domain_enabled(env: dict) -> bool | None:
    url = f"{API}/accounts/{env['CLOUDFLARE_ACCOUNT_ID']}/r2/buckets/{DATA_BUCKET}/domains/custom"
    for dom in _call(env, "GET", url).get("result", {}).get("domains", []):
        if dom["domain"] == DATA_DOMAIN:
            return bool(dom.get("enabled"))
    return None


# ---- latch ----

def latched(path: Path = LATCH) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"reason": f"unreadable latch file {path}"}   # unreadable counts as tripped


def write_latch(info: dict, path: Path = LATCH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(info, f, indent=2)
        f.write("\n")


def describe(p: dict) -> str:
    return (f"${p['usd']:.2f} ({p['window']}): Class A {p['class_a']:,} ${p['usd_a']:.2f}, "
            f"Class B {p['class_b']:,} ${p['usd_b']:.2f}, storage {p['storage_gb']} GB ${p['usd_storage']:.2f}")


# ---- what publishers call ----

def gate(planned_class_a: int = 0, strict: bool = False, env: dict | None = None,
         estimator=estimate, latch: Path = LATCH) -> None:
    """Raise Tripped if R2 writes must not happen now. Call before a run writes to R2."""
    held = latched(latch)
    if held:
        raise Tripped(f"spend breaker is tripped since {held.get('tripped_at', '?')} "
                      f"({held.get('reason', '')}); the owner clears it: python tools/spend_breaker.py --reset")
    try:
        p = estimator(env or cloud_publish.read_env(), extra_a=planned_class_a)
    except Exception as e:   # noqa: BLE001  lenient callers must never lose a day's publish to this
        if strict:
            raise Tripped(f"spend unknown (R2 analytics failed: {e}); a strict publisher does not write blind")
        log(f"WARNING: spend unknown (R2 analytics failed: {e}); going on, this run cannot reach the line alone")
        return
    if p["usd"] >= TRIP_USD:
        raise Tripped(f"estimate with this run's {planned_class_a:,} writes is {describe(p)}, "
                      f"at or past the ${TRIP_USD:.0f} line")
    log(f"ok: {describe(p)} with this run's {planned_class_a:,} planned writes; line ${TRIP_USD:.0f}")


# ---- the hourly check ----

def trip(env: dict, p: dict, dry_run: bool, latch: Path = LATCH, cut=set_domain) -> None:
    reason = f"estimate {describe(p)} reached ${TRIP_USD:.0f}"
    if dry_run:
        log(f"WOULD TRIP: {reason}; would turn off {DATA_DOMAIN} and set the latch {latch}")
        return
    info = {"tripped_at": p["at"], "reason": reason, "estimate": p, "domain_disabled": False}
    write_latch(info, latch)              # first, so publishers stop even if the cut fails
    try:
        cut(env, False)
        info["domain_disabled"] = True
        write_latch(info, latch)
        log(f"TRIPPED: {reason}; {DATA_DOMAIN} public access OFF; R2 publishing refused until --reset")
    except (RuntimeError, OSError, urllib.error.URLError) as e:
        log(f"TRIPPED: {reason}; latch set, but turning off {DATA_DOMAIN} FAILED: {e}")
        raise


def check(dry_run: bool = False, extra_a: int = 0, extra_b: int = 0, env: dict | None = None,
          estimator=estimate, latch: Path = LATCH, cut=set_domain) -> int:
    """0 under the line, 2 tripped (now or before)."""
    env = env or cloud_publish.read_env()
    p = estimator(env, extra_a=extra_a, extra_b=extra_b)
    held = latched(latch)
    if held:
        log(f"latched since {held.get('tripped_at')}: {held.get('reason')}; now {describe(p)}")
        if not held.get("domain_disabled") and not dry_run:
            cut(env, False)                  # an earlier cut failed: try again
            held["domain_disabled"] = True
            write_latch(held, latch)
            log(f"{DATA_DOMAIN} public access OFF (retry)")
        return 2
    if p["usd"] >= TRIP_USD:
        trip(env, p, dry_run, latch, cut)
        return 2
    level = "WARN" if p["usd"] >= WARN_USD else "ok"
    log(f"{level}: {describe(p)}; trips at ${TRIP_USD:.0f}")
    return 0


def reset(env: dict, latch: Path = LATCH, force: bool = False) -> None:
    held = latched(latch)
    p = estimate(env)
    log(f"now {describe(p)}")
    if p["usd"] >= TRIP_USD and not force:
        # the trailing 30 days can stay over the line into a new billing period
        log(f"still at or past ${TRIP_USD:.0f}; the next hourly check would trip again. If the bill says "
            "otherwise (a new period), --reset --force, and raise TRIP_USD to keep it from re-tripping.")
        raise SystemExit(2)
    set_domain(env, True)
    if latch.exists():
        latch.unlink()
    log(f"reset: {DATA_DOMAIN} public access ON, latch cleared" + (f" (was: {held.get('reason')})" if held else ""))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--status", action="store_true")
    p.add_argument("--reset", action="store_true", help="owner: clear the latch, turn the data domain on")
    p.add_argument("--force", action="store_true", help="with --reset: even if the estimate is past the line")
    p.add_argument("--simulate-class-a", type=int, default=0, help="add pretend Class A ops (needs --dry-run)")
    p.add_argument("--simulate-class-b", type=int, default=0, help="add pretend Class B ops (needs --dry-run)")
    a = p.parse_args()
    if (a.simulate_class_a or a.simulate_class_b) and not a.dry_run:
        p.error("--simulate-* only with --dry-run")
    try:
        env = cloud_publish.read_env()
        if a.reset:
            reset(env, force=a.force)
            return 0
        if a.status:
            held = latched()
            log(f"latch: {json.dumps(held) if held else 'clear'}; {DATA_DOMAIN} enabled: {domain_enabled(env)}")
            log(describe(estimate(env)))
            return 2 if held else 0
        return check(dry_run=a.dry_run, extra_a=a.simulate_class_a, extra_b=a.simulate_class_b, env=env)
    except (RuntimeError, OSError, urllib.error.URLError) as e:
        log(f"FAILED: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
