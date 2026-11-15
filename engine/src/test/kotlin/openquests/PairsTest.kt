package openquests

import de.westnordost.streetcomplete.util.ktx.asSequenceOfPairs
import de.westnordost.streetcomplete.util.ktx.asSequenceOfPairsAsInStreetComplete
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse

/** [pairsOf], which stands in for SC's `asSequenceOfPairs` (the `pairs` patch), against SC's own body. */
class PairsTest {
    @Test fun `the same pairs as StreetComplete's sequence, for lists of every small size`() {
        for (n in 0..40) {
            val list = List(n) { it * 7 % 5 }
            assertEquals(list.asSequenceOfPairsAsInStreetComplete().toList(), list.asSequenceOfPairs().toList(), "size $n")
            assertEquals(list.asSequenceOfPairsAsInStreetComplete().toList(), pairsOf(list).toList(), "size $n")
        }
        assertEquals(listOf(null to 1, 1 to null), pairsOf(listOf(null, 1, null)).toList())
    }

    @Test fun `it can be walked twice, reads the source when first asked, and ends as an iterator ends`() {
        val list = mutableListOf(1, 2, 3)
        val pairs = pairsOf(list)
        val ours = pairs.iterator()
        val theirs = list.asSequenceOfPairsAsInStreetComplete().iterator()
        list.add(4) // after iterator(), before the first pair: both read the list only now
        assertEquals(theirs.asSequence().toList(), ours.asSequence().toList())
        assertEquals(listOf(1 to 2, 2 to 3, 3 to 4), pairs.toList())
        assertEquals(pairs.toList(), pairs.toList())
        assertFalse(ours.hasNext())
        assertFailsWith<NoSuchElementException> { ours.next() }
        assertFailsWith<NoSuchElementException> { pairsOf(listOf(1)).iterator().next() }
    }

    @Test fun `it takes as many items from the source as StreetComplete's does`() {
        class Counting(val n: Int) : Iterable<Int> {
            val calls = StringBuilder()
            override fun iterator() = object : Iterator<Int> {
                var i = 0
                override fun hasNext(): Boolean { calls.append('h'); return i < n }
                override fun next(): Int { calls.append('n'); return i++ }
            }
        }
        for (n in 0..6) {
            val a = Counting(n); val b = Counting(n)
            for (p in a.asSequenceOfPairsAsInStreetComplete()) { }
            for (p in pairsOf(b)) { }
            assertEquals(a.calls.toString().count { it == 'n' }, b.calls.toString().count { it == 'n' }, "size $n")
        }
    }
}
