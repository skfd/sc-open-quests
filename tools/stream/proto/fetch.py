"""Download the minute diffs and the changeset feed files covering one UTC day.

Usage: fetch.py 2026-11-08
The range is found from the feeds' own state files, not by arithmetic alone.
"""
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

S = Path(__file__).parent
UA = {"User-Agent": "quest-stream-replay/0.1"}
BASE = "https://planet.openstreetmap.org/replication"


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def path(seq):
    s = f"{seq:09d}"
    return f"{s[:3]}/{s[3:6]}/{s[6:]}"


def minute_time(seq):
    t = get(f"{BASE}/minute/{path(seq)}.state.txt").decode()
    m = re.search(r"timestamp=(\S+)", t)
    return datetime.strptime(m[1].replace("\\", ""), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def changeset_time(seq):
    t = get(f"{BASE}/changesets/{path(seq)}.state.txt").decode()
    m = re.search(r"last_run: (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", t)
    return datetime.strptime(m[1], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def first_after(when, head_seq, head_time, time_of):
    """Smallest sequence whose time is after `when`; sequences are about a minute apart."""
    seq = head_seq - int((head_time - when).total_seconds() // 60)
    while time_of(seq) > when:
        seq -= max(1, int((time_of(seq) - when).total_seconds() // 60))
    while time_of(seq) <= when:
        seq += 1
    return seq


def fetch(kind, seq, ext):
    out = S / kind / f"{seq}.{ext}"
    if not out.exists():
        data = get(f"{BASE}/{'minute' if kind == 'minute' else 'changesets'}/{path(seq)}.{ext}")
        out.write_bytes(data)
    return seq


day = datetime.strptime(sys.argv[1], "%Y-%m-%d").replace(tzinfo=timezone.utc)
end = day + timedelta(days=1)

head = get(f"{BASE}/minute/state.txt").decode()
head_seq = int(re.search(r"sequenceNumber=(\d+)", head)[1])
head_time = minute_time(head_seq)
m_first = first_after(day, head_seq, head_time, minute_time)
m_last = first_after(end, head_seq, head_time, minute_time) - 1
print(f"minute diffs {m_first} ({minute_time(m_first)}) .. {m_last} ({minute_time(m_last)}): {m_last - m_first + 1} files")

chead = get(f"{BASE}/changesets/state.yaml").decode()
c_seq = int(re.search(r"sequence: (\d+)", chead)[1])
c_time = changeset_time(c_seq)
c_first = first_after(day, c_seq, c_time, changeset_time)
c_last = first_after(end + timedelta(hours=2), c_seq, c_time, changeset_time) - 1
print(f"changeset files {c_first} .. {c_last}: {c_last - c_first + 1} files (to two hours past the day)")

(S / "minute").mkdir(exist_ok=True)
(S / "changesets").mkdir(exist_ok=True)
(S / "range.txt").write_text(f"{m_first} {m_last} {c_first} {c_last}\n")
with ThreadPoolExecutor(6) as pool:
    done = sum(1 for _ in pool.map(lambda s: fetch("minute", s, "osc.gz"), range(m_first, m_last + 1)))
    print(f"minute files: {done}")
    done = sum(1 for _ in pool.map(lambda s: fetch("changesets", s, "osm.gz"), range(c_first, c_last + 1)))
    print(f"changeset files: {done}")
