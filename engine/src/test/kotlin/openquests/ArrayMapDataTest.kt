package openquests

import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals

class ArrayMapDataTest {
    /** what a real HashMap gives: the order [hashMapOrder] stands in for */
    private fun assertOrderOfHashMap(ids: LongArray) {
        val map = HashMap<Long, Int>()
        for (i in ids.indices) map[ids[i]] = i
        val order = hashMapOrder(ids)
        assertEquals(map.keys.toList(), order.map { ids[it] }, "${ids.size} ids")
    }

    @Test fun `iterates as a HashMap filled in the same order`() {
        val random = Random(1)
        for (size in listOf(0, 1, 12, 13, 24, 25, 1000, 200_000)) {
            assertOrderOfHashMap(LongArray(size) { 1000L + it })
            assertOrderOfHashMap(LongArray(size) { 12_000_000_000L + it * 7L })
            assertOrderOfHashMap(LongArray(size) { random.nextLong(1, 14_000_000_000L) }.distinct().toLongArray())
        }
    }

    @Test fun `finds every id and no other`() {
        val random = Random(2)
        val ids = LongArray(100_000) { random.nextLong(1, 14_000_000_000L) }.distinct().toLongArray()
        val index = LongIndex(ids)
        for (i in ids.indices) assertEquals(i, index[ids[i]])
        val known = ids.toHashSet()
        repeat(100_000) {
            val id = random.nextLong(1, 14_000_000_000L)
            if (id !in known) assertEquals(-1, index[id])
        }
        assertEquals(-1, LongIndex(LongArray(0))[5])
    }
}
