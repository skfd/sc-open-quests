package openquests

import de.westnordost.streetcomplete.data.osm.mapdata.BoundingBox
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.util.math.contains
import openquests.fast.NearBounds
import openquests.fast.PointGrid
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertTrue

/** The level twins' grid must give exactly the points SC's BoundingBox.contains holds, in index order. */
class PointGridTest {
    private val random = Random(7)
    // Moscow-ish points, some on cell edges (0.002 degrees) and some near the 180th meridian
    private val points = List(5000) { LatLon(55.7 + random.nextDouble(0.1), 37.5 + random.nextDouble(0.2)) } +
        List(200) { LatLon(55.7 + 0.002 * random.nextInt(50), 37.5 + 0.002 * random.nextInt(100)) } +
        List(200) { LatLon(random.nextDouble(-10.0, 10.0), if (random.nextBoolean()) 179.99 else -179.99) }
    private val grid = PointGrid(points)

    private fun check(b: BoundingBox) =
        assertContentEquals(points.indices.filter { points[it] in b }.toIntArray(), grid.inBounds(b), "$b")

    @Test fun `random boxes, edges included`() {
        repeat(500) {
            val lat = 55.7 + random.nextDouble(0.1); val lon = 37.5 + random.nextDouble(0.2)
            check(BoundingBox(lat, lon, lat + random.nextDouble(0.01), lon + random.nextDouble(0.02)))
        }
        check(BoundingBox(55.71, 37.52, 55.73, 37.56)) // on cell edges
        check(BoundingBox(55.72, 37.54, 55.72, 37.54)) // one point wide
    }

    @Test fun `a box across the 180th meridian, and one larger than the grid`() {
        check(BoundingBox(-5.0, 179.9, 5.0, -179.9))
        check(BoundingBox(-80.0, -170.0, 80.0, 170.0))
    }

    /** NearBounds may say yes too often, never no for a point one of the boxes contains */
    private fun checkNear(boxes: List<BoundingBox>, mustReject: Boolean) {
        val near = NearBounds(boxes)
        var rejected = 0
        for (p in points) {
            if (boxes.any { p in it }) assertTrue(near.mayHold(p), "$p") else if (!near.mayHold(p)) rejected++
        }
        if (mustReject) assertTrue(rejected > points.size / 2, "rejected $rejected of ${points.size}")
    }

    @Test fun `near bounds holds every point a box contains and drops most others`() {
        checkNear(List(40) {
            val lat = 55.7 + random.nextDouble(0.1); val lon = 37.5 + random.nextDouble(0.2)
            BoundingBox(lat, lon, lat + random.nextDouble(0.004), lon + random.nextDouble(0.004))
        } + BoundingBox(55.71, 37.52, 55.72, 37.53) + BoundingBox(55.75, 37.6, 55.75, 37.6), mustReject = true)
        checkNear(emptyList(), mustReject = true)
        // across the 180th meridian, or too large for a cell set: everywhere
        checkNear(listOf(BoundingBox(-5.0, 179.9, 5.0, -179.9)), mustReject = false)
        checkNear(listOf(BoundingBox(-80.0, -170.0, 80.0, 170.0)), mustReject = false)
    }
}
