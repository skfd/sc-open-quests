package openquests

import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

/** OSM allows 255 code points in a tag key or value; v64.0 counted UTF-16 units (patch codepoints). */
class TagLengthTest {
    // 255 code points, 256 UTF-16 units: an emoji outside the BMP is two
    private val emoji255 = "📄" + "a".repeat(254)
    private val over = "a".repeat(256)

    @Test fun `a value of 255 code points with an emoji in it is a valid element`() {
        assertEquals(256, emoji255.length)
        Node(1, LatLon(55.5, 37.7), mapOf("description" to emoji255))
    }

    @Test fun `a value of 256 code points is still invalid to SC`() {
        assertFailsWith<IllegalArgumentException> { Node(1, LatLon(55.5, 37.7), mapOf("description" to over)) }
    }

    @Test fun `fitTags leaves out only the tags that are too long`() {
        val tags = mapOf("shop" to "electronics", "description" to over, "note" to emoji255)
        assertEquals(mapOf("shop" to "electronics", "note" to emoji255), fitTags("test", "node", 1, tags))
        Node(1, LatLon(55.5, 37.7), fitTags("test", "node", 1, tags))
    }

    @Test fun `fitTags hands back the same map when every tag fits`() {
        val tags = mapOf("shop" to "electronics")
        kotlin.test.assertSame(tags, fitTags("test", "node", 1, tags))
    }
}
