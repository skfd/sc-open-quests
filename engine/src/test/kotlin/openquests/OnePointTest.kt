package openquests

import de.westnordost.streetcomplete.data.osm.geometry.ElementGeometryCreator
import de.westnordost.streetcomplete.data.osm.geometry.ElementPolylinesGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import de.westnordost.streetcomplete.util.math.intersects
import de.westnordost.streetcomplete.util.math.intersectsWith
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** A way whose nodes all share one position gets a polyline of one point from SC; crossing it is false,
 *  not a failed require (patch onepoint; Moscow 2017-12-01 stopped on it in AddMaxHeight). */
class OnePointTest {
    private val creator = ElementGeometryCreator()
    private val p = LatLon(55.75, 37.62)

    @Test fun `SC gives a way of two nodes at one position a polyline of one point`() {
        val g = creator.create(Way(1, listOf(1L, 2L), mapOf("highway" to "service"), 1, 0), listOf(p, p))
        assertEquals(listOf(listOf(p)), (g as ElementPolylinesGeometry).polylines)
    }

    @Test fun `a bridge crossing it does not fail, and does not cross it`() {
        val point = creator.create(Way(1, listOf(1L, 2L), mapOf("highway" to "service"), 1, 0), listOf(p, p))!!
        val bridge = creator.create(Way(2, listOf(3L, 4L), mapOf("highway" to "primary", "bridge" to "yes"), 1, 0),
            listOf(LatLon(55.74, 37.62), LatLon(55.76, 37.62)))!!
        assertFalse(bridge.intersects(point))
        assertFalse(point.intersects(bridge))
    }

    @Test fun `two real polylines still cross`() {
        val a = listOf(LatLon(55.74, 37.62), LatLon(55.76, 37.62))
        val b = listOf(LatLon(55.75, 37.61), LatLon(55.75, 37.63))
        assertTrue(a.intersectsWith(b))
        assertFalse(listOf(p).intersectsWith(b))
    }
}
