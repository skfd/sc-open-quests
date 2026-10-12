package openquests

import de.westnordost.streetcomplete.data.osm.geometry.ElementGeometryCreator
import de.westnordost.streetcomplete.data.osm.geometry.ElementPolygonsGeometry
import de.westnordost.streetcomplete.data.osm.geometry.ElementPolylinesGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.Relation
import de.westnordost.streetcomplete.data.osm.mapdata.RelationMember
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import kotlin.math.abs
import kotlin.test.Test
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Quest positions come from SC's ElementGeometryCreator (vendored): polygon centroid for areas,
 *  half-length point for lines. */
class GeometryTest {
    private val creator = ElementGeometryCreator()

    // an L-shaped closed ring: its centroid is not the average of its vertices
    private val lRing = listOf(
        LatLon(0.0, 0.0), LatLon(0.0, 2.0), LatLon(1.0, 2.0), LatLon(1.0, 1.0),
        LatLon(3.0, 1.0), LatLon(3.0, 0.0), LatLon(0.0, 0.0),
    )
    private val lIds = LongArrayAsList(longArrayOf(1, 2, 3, 4, 5, 6, 1))

    private fun assertNear(expected: LatLon, actual: LatLon, eps: Double = 1e-9) =
        assertTrue(abs(expected.latitude - actual.latitude) < eps && abs(expected.longitude - actual.longitude) < eps,
            "expected $expected, got $actual")

    @Test fun `closed way with an area tag gets the polygon centroid`() {
        val g = creator.create(Way(1, lIds, mapOf("building" to "yes")), lRing)
        assertIs<ElementPolygonsGeometry>(g)
        // areas 2 (0..1 x 0..2) and 2 (1..3 x 0..1): centroid (0.5,1) and (2,0.5) -> (1.25, 0.75)
        assertNear(LatLon(1.25, 0.75), g.center)
    }

    @Test fun `closed way without an area tag is a line, centre at half its length`() {
        val g = creator.create(Way(1, lIds, mapOf("highway" to "footway")), lRing)
        assertIs<ElementPolylinesGeometry>(g)
        // length 10 units; half is 5: 2 along lat 0, 1 up, 1 along lat 1, then 1 of the 2 up to lat 3
        assertNear(LatLon(2.0, 1.0), g.center, 1e-3)
    }

    @Test fun `open way gets the half-length point, not the vertex average`() {
        val line = listOf(LatLon(43.0, -79.0), LatLon(43.0, -78.99), LatLon(43.0, -78.9))
        val g = creator.create(Way(1, LongArrayAsList(longArrayOf(1, 2, 3)), mapOf("highway" to "residential")), line)
        assertIs<ElementPolylinesGeometry>(g)
        assertNear(LatLon(43.0, -78.95), g.center, 1e-6)
    }

    @Test fun `area=no keeps a closed way a line`() {
        val g = creator.create(Way(1, lIds, mapOf("building" to "yes", "area" to "no")), lRing)
        assertIs<ElementPolylinesGeometry>(g)
    }

    @Test fun `multipolygon relation centre is the centroid of its first outer ring`() {
        val rel = Relation(9, listOf(
            RelationMember(ElementType.WAY, 1, "outer"),
            RelationMember(ElementType.WAY, 2, "outer"),
            RelationMember(ElementType.NODE, 7, "label"),
        ), mapOf("type" to "multipolygon", "landuse" to "grass"))
        // the L ring split into two ways that SC joins back together
        val g = creator.create(rel, mapOf(1L to lRing.subList(0, 4), 2L to lRing.subList(3, 7)))
        assertIs<ElementPolygonsGeometry>(g)
        assertNear(LatLon(1.25, 0.75), g.center)
    }

    @Test fun `relation with only node members has no geometry, so no quest`() {
        val rel = Relation(9, listOf(RelationMember(ElementType.NODE, 7, "stop")), mapOf("type" to "public_transport"))
        assertNull(creator.create(rel, emptyMap()))
    }
}
