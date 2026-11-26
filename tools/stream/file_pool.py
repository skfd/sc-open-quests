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


SMALL_BATCH = 256          # small files to one job of the pool
SMALL_BATCH_CHARS = 4 << 20  # or fewer, once their text is this long


def _write_batch(batch: list) -> None:
    for path, text in batch:
        path.write_text(text, encoding="utf-8")


class SmallFiles:
    """many small text files (a world day's 558,000 boundary and parts files, 624 s on one thread): the caller
    makes each file's text, in its own order, and `put`s it; the files are written through the pool, a batch to a
    job. Each is written by the call the serial loop made (`path.write_text(text, encoding="utf-8")`), so its bytes
    are the same; with a width of 1 `put` makes that call itself and there is no pool. Use as a context: on leaving
    it every file is written, or the first failure of a write is raised.
    Memory: at most 2 * width batches wait or are being written, and one is being filled: (2 * width + 1) batches of
    SMALL_BATCH files or SMALL_BATCH_CHARS of text, whichever is less (under 40 MB of text at a width of 4)."""

    def __init__(self, width: int | None = None):
        self.width = FILE_POOL if width is None else width
        self.ex = None
        self.cur: list = []
        self.chars = 0
        self.pending: deque = deque()
        if self.width > 1:
            from concurrent.futures import ThreadPoolExecutor
            self.ex = ThreadPoolExecutor(self.width)

    def put(self, path, text: str) -> None:
        if self.ex is None:
            path.write_text(text, encoding="utf-8")
            return
        self.cur.append((path, text))
        self.chars += len(text)
        if len(self.cur) >= SMALL_BATCH or self.chars >= SMALL_BATCH_CHARS:
            self._send()

    def _send(self) -> None:
        while len(self.pending) >= 2 * self.width:
            self.pending.popleft().result()
        self.pending.append(self.ex.submit(_write_batch, self.cur))
        self.cur, self.chars = [], 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.ex is None:
            return False
        try:
            if exc_type is None:
                if self.cur:
                    self._send()
                while self.pending:
                    self.pending.popleft().result()
        finally:
            self.ex.shutdown(wait=True, cancel_futures=True)
        return False
