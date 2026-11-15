package openquests

import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals

/** [firstSeen] gives a map data's nodes in the order they first come, which decides the order SC's quests
 *  meet them in: its two ways (marks in a bit set for a city, a sort for a tile) against a plain set. */
class FirstSeenTest {
    private fun plain(first: IntArray, rest: List<IntArray>): IntArray =
        LinkedHashSet<Int>().also { s -> first.forEach(s::add); rest.forEach { r -> r.forEach(s::add) } }.toIntArray()

    private fun check(first: IntArray, rest: List<IntArray>, limit: Int) {
        val expected = plain(first, rest)
        val total = first.size + rest.sumOf { it.size }
        assertContentEquals(expected, firstSeenByBits(first, rest, limit, total), "by bits")
        assertContentEquals(expected, firstSeenBySort(first, rest, total), "by sort")
        assertContentEquals(expected, firstSeen(first, rest, limit), "the one chosen")
    }

    @Test fun `random numbers, many of them repeated, in the order they first come`() {
        val r = Random(11)
        repeat(300) {
            val limit = r.nextInt(1, 5_000)
            val first = IntArray(r.nextInt(0, 40)) { r.nextInt(limit) }
            val rest = List(r.nextInt(0, 60)) { IntArray(r.nextInt(0, 12)) { r.nextInt(limit) } }
            check(first, rest, limit)
        }
    }

    @Test fun `nothing, one number, the ends of the range, and a range far wider than what is asked`() {
        check(IntArray(0), emptyList(), 0)
        check(IntArray(0), emptyList(), 1_000)
        check(intArrayOf(0), emptyList(), 1)
        check(intArrayOf(63, 64, 0, 127, 128, 63), listOf(intArrayOf(128, 129, 0), IntArray(0), intArrayOf(64)), 130)
        // few numbers of a wide range: firstSeen sorts; many: it marks bits. Both sides of the line.
        check(intArrayOf(999_999, 5), listOf(intArrayOf(5, 7, 999_999, 0)), 1_000_000)
        val many = IntArray(5_000) { (it * 7919) % 1_000_000 }
        check(many, listOf(many.reversedArray()), 1_000_000)
    }
}
