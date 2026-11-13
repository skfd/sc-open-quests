package openquests

import de.westnordost.streetcomplete.data.osm.mapdata.BoundingBox
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.util.math.LatLonRaster
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

/** A world cell reaching the North Pole: SC's LatLonRaster rounds its north edge up past latitude 90 and
 *  throws; rasterBox keeps it on the globe (the world count of 2026-11-12, f116 and five more). */
class PoleRasterTest {
    // f116c12's shape: a 3.3 degree wide cell whose padded box ends at the pole
    private val box = BoundingBox(89.90001, 17.0, 90.0, 20.3)  // south edge off the 0.0005 grid, as cells are

    @Test fun scRasterDiesAtThePole() {
        assertFailsWith<IllegalArgumentException> { LatLonRaster(box, 0.0005) }
    }

    @Test fun rasterBoxBuildsAndStillFindsPoints() {
        val r = LatLonRaster(rasterBox(box), 0.0005)
        val p = LatLon(89.95, 18.0)
        r.insert(p)
        assertEquals(listOf(p), r.getAll(BoundingBox(89.94, 17.9, 89.96, 18.1)).toList())
    }

    @Test fun boxesOffThePoleAreUntouched() {
        val toronto = BoundingBox(43.5, -79.7, 43.9, -79.1)
        assertEquals(toronto, rasterBox(toronto))
    }
}
