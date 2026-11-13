"""How many node ids hold a place in the store: the planet's live nodes."""
import sys, time
import numpy as np
m = np.memmap(sys.argv[1], dtype=np.int32, mode="r").reshape(-1, 2)
t = time.time(); live = 0; top = 0
STEP = 1 << 27
for a in range(0, m.shape[0], STEP):
    x = np.asarray(m[a:a + STEP, 0])
    ok = x != 2147483647
    n = int(ok.sum()); live += n
    if n:
        top = a + int(np.flatnonzero(ok)[-1])
print(f"{m.shape[0]:,} slots, {live:,} hold a place ({100 * live / m.shape[0]:.1f}%), highest id {top:,}; {time.time() - t:.0f} s")
