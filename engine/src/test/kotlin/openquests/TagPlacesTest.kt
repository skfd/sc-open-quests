package openquests

import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals

/** [TagChunk.addPlaces] keeps an element's tags by their places in a block's string table: the same numbers as
 *  [TagChunk.add] of the map made of those strings, whichever of the two each element of a block takes. */
class TagPlacesTest {
    @Test fun `tags by their places give the numbers the map of their strings gives`() {
        val r = Random(5)
        val dictA = TagDict(); val dictB = TagDict()
        repeat(30) {
            // a block's table: some strings twice, at two places (a writer need not make them one)
            val strings = Array(r.nextInt(2, 60)) { "s${r.nextInt(40)}" }
            val byMap = TagChunk(dictA); val byPlace = TagChunk(dictB)
            repeat(r.nextInt(1, 80)) {
                // an element's tags: distinct keys (by string), any values
                val keys = ArrayList<Int>(); val seen = HashSet<String>()
                repeat(r.nextInt(0, 6)) { val k = r.nextInt(strings.size); if (seen.add(strings[k])) keys += k }
                val vals = keys.map { r.nextInt(strings.size) }
                val map = TagMap(keys.size).also { m -> for (i in keys.indices) m.add(strings[keys[i]], strings[vals[i]]) }
                assertEquals(keys.size, map.size)
                byMap.add(map)
                when (r.nextInt(3)) {
                    0 -> byPlace.addPlaces(strings, keys, vals)
                    1 -> { // a dense node's: keys and values side by side, somewhere in a longer list
                        val pad = List(r.nextInt(0, 4)) { 0 }
                        val keysVals = pad + keys.indices.flatMap { listOf(keys[it], vals[it]) } + listOf(0)
                        byPlace.addPlaces(strings, keysVals, pad.size, pad.size + keys.size * 2)
                    }
                    else -> byPlace.add(map)
                }
                assertEquals(byMap.n, byPlace.n)
            }
            // the same strings in the same order, whatever number each dictionary gave them
            val a = dictA.strings(); val b = dictB.strings()
            assertContentEquals(List(byMap.n) { a[byMap.kv[it]] }, List(byPlace.n) { b[byPlace.kv[it]] })
        }
    }
}
