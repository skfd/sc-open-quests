"""The world day's passes over its files, a few files at a time (HANDOFF, "Performance review of the traces and
logs", (3)): tier 1's rewrite, the tier 2 delta's two passes, the counts, the old rows, the engine's small files.

FILE_POOL files are worked on at once (WORLD_FILE_POOL; 1 is the serial loop these passes were, no pool made).
The work may end in any order; `ordered` gives the results back in the files' order, on the caller's thread, so
whatever is built from them (sums, the day's record, the sets of new rows) is built as the serial loop built it.

Memory: the loop's own Python reached 17 GB of commit on 2026-11-24, so no pass may hold every file's rows. A
worker reads its file, does its work, writes, and returns small values; `ordered` starts a file only when the
caller has taken the result before it and come back for the next, so at most `width` items are in work or waiting
to be taken at any moment (the one the caller holds among them).
"""
from __future__ import annotations

import os
from collections import deque

FILE_POOL = int(os.environ.get("WORLD_FILE_POOL", "4"))


def ordered(fn, items, width: int | None = None):
    """fn(item) for every item, yielded in the items' order; `width` threads (FILE_POOL when None). An item is
    taken from `items` and started only when there is room, so `items` may be a generator that makes its
    arguments late. A failure is raised where its result would have been yielded; what was not started is not."""
    width = FILE_POOL if width is None else width
    if width <= 1:
        for x in items:
            yield fn(x)
        return
    from concurrent.futures import ThreadPoolExecutor
    it = iter(items)
    pending: deque = deque()
    with ThreadPoolExecutor(width) as ex:
        try:
            for x in it:
                pending.append(ex.submit(fn, x))
                if len(pending) >= width:
                    break
            while pending:
                r = pending.popleft().result()
                yield r
                del r  # the caller is back: its item is done with, the next may start
                for x in it:
                    pending.append(ex.submit(fn, x))
                    break
        finally:
            for f in pending:
                f.cancel()
