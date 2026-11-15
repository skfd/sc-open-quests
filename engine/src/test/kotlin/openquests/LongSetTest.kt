package openquests

import openquests.fast.LongSet
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals

/** [LongSet] against a `HashSet<Long>` through the same adds, removals and questions. */
class LongSetTest {
    @Test fun `it holds what a HashSet holds after the same adds and removals`() {
        for (seed in 1..20) {
            val r = Random(seed)
            val set = LongSet(if (seed % 2 == 0) 4 else 5000)
            val model = HashSet<Long>()
            // few distinct ids, so that most removals hit and runs of neighbours form and close again
            val span = if (seed % 3 == 0) 60L else 20_000L
            fun id() = when (r.nextInt(10)) { 0 -> r.nextLong(); 1 -> -r.nextLong(span); else -> r.nextLong(span) * if (seed % 4 == 0) 4096L else 1L }
            repeat(60_000) {
                val k = id()
                if (k == Long.MIN_VALUE) return@repeat
                when (r.nextInt(3)) {
                    0 -> assertEquals(model.add(k), set.add(k), "add $k")
                    1 -> assertEquals(model.remove(k), set.remove(k), "remove $k")
                    else -> assertEquals(k in model, k in set, "contains $k")
                }
                assertEquals(model.size, set.size)
            }
            for (k in model) assertEquals(true, k in set)
            val copy = set.copy()
            for (k in model.toList().take(model.size / 2)) { set.remove(k) }
            for (k in model) assertEquals(true, k in copy, "a copy keeps what the set it was made from loses")
            assertEquals(model.size, copy.size)
        }
    }

    @Test fun `the id that marks an empty place is in no set`() {
        val set = LongSet()
        assertEquals(false, Long.MIN_VALUE in set)
        assertEquals(false, set.remove(Long.MIN_VALUE))
        set.add(0)
        assertEquals(true, 0L in set)
        assertEquals(1, set.size)
    }
}
