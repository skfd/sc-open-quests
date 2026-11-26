package openquests

import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals

/** The lists made once for all cities against the loop per city they replace: the same lists in the same order. */
class CityListsTest {
    @Test fun `partsByCity gives each city the parts a filter per city gives, in the parts' order`() {
        val rnd = Random(3)
        val polygon = Polygon(doubleArrayOf(0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0))
        for (cityCount in listOf(0, 1, 7, 300)) {
            // cities without parts, cities with many, parts in no order of their city, a part of no city
            val parts = List(if (cityCount == 0) 0 else 2000) {
                Part(it, "p$it", if (it % 97 == 0) cityCount + 5 else (rnd.nextInt(cityCount) * rnd.nextInt(1, 3)) % cityCount, polygon)
            }
            val got = partsByCity(cityCount, parts)
            assertEquals(cityCount, got.size)
            for (c in 0 until cityCount) {
                assertContentEquals(parts.filter { it.city == c }.map { it.index }.toIntArray(), got[c], "city $c of $cityCount")
            }
        }
    }
}
