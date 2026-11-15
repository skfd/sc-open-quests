package openquests

import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals

/** [NodeStore.indexOf] finds a node through its table of id stretches: every id of the file at its own
 *  position, and -1 for the ids between, before and after them. */
class NodeStoreTest {
    private fun storeOf(ids: LongArray, blockSize: Int): NodeStore {
        val blocks = ids.toList().chunked(blockSize).map { chunk ->
            NodeBlock(keep = false, dict = null).also { b -> for (id in chunk) b.add(id, pack((id % 900).toInt(), (id % 1800).toInt()), 1, 0) }
        }
        return NodeStore(blocks + NodeBlock(keep = false, dict = null), null)
    }

    private fun check(ids: LongArray, blockSize: Int = 8000) {
        val store = storeOf(ids, blockSize)
        assertEquals(ids.size, store.count)
        val held = ids.toHashSet()
        for ((i, id) in ids.withIndex()) {
            assertEquals(i, store.indexOf(id), "node $id")
            assertEquals(pack((id % 900).toInt(), (id % 1800).toInt()), store[id])
            for (near in longArrayOf(id - 1, id + 1, id - 255, id + 255, id - 256, id + 256, id + 257)) {
                if (near !in held) { assertEquals(-1, store.indexOf(near), "node $near is not in the file"); assertEquals(NO_COORD, store[near]) }
            }
        }
        for (id in longArrayOf(Long.MIN_VALUE, -1, 0, ids.first() - 1, ids.last() + 1, Long.MAX_VALUE)) {
            if (id !in held) assertEquals(-1, store.indexOf(id), "node $id is not in the file")
        }
    }

    @Test fun `every id is found at its position and no other id is`() {
        val r = Random(7)
        // dense runs, gaps of every size around a stretch's 256 ids, and a far jump (a file's ids span the planet's)
        val ids = ArrayList<Long>()
        var id = 1_000L
        repeat(60_000) {
            id += when (r.nextInt(12)) { 0 -> 255L; 1 -> 256L; 2 -> 257L; 3 -> r.nextLong(1, 5_000); 4 -> if (r.nextInt(400) == 0) 3_000_000_000L else 1L; else -> 1L }
            ids += id
        }
        check(ids.toLongArray())
        check(ids.toLongArray(), blockSize = 1)
    }

    @Test fun `one node, two nodes at a stretch's edges, negative ids, and no node at all`() {
        check(longArrayOf(42))
        check(longArrayOf(0, 255, 256, 511, 512))
        check(longArrayOf(-700, -256, -1, 0, 1, 13_000_000_000L))
        val empty = NodeStore(listOf(NodeBlock(keep = false, dict = null)), null)
        assertEquals(0, empty.count)
        assertEquals(-1, empty.indexOf(5))
        assertEquals(NO_COORD, empty[5])
    }
}
