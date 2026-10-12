package openquests

import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import openquests.custom.CUSTOM_QUESTS
import openquests.custom.ScFeatures
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class CustomQuestsTest {
    @Test fun `every port is pinned in PORTED-QUESTS txt and the other way round`() {
        val pinned = File("engine/PORTED-QUESTS.txt").readLines()
            .filter { it.isNotBlank() && !it.trimStart().startsWith("#") }
            .map { it.trim().split(Regex("\\s+"))[0] }
        assertEquals(pinned.sorted(), CUSTOM_QUESTS.keys.sorted())
    }

    @Test fun `ported quests are counted with the port's age flag and element types`() {
        val registry = Registry.load(File("data/quests/v63.4.json"))
        val sidewalk = registry.quests.single { it.name == "AddSidewalk" }
        assertTrue(sidewalk.isCounted && !sidewalk.isFilter)
        assertEquals(listOf("ways"), sidewalk.elementTypes)
        assertTrue(registry.quests.single { it.name == "AddOpeningHours" }.usesAge)
        assertEquals(138 + CUSTOM_QUESTS.size, registry.countedQuests.size)
    }

    @Test fun `SC's feature dictionary resolves from the bundled en-CA presets`() {
        assertEquals("en-CA", java.util.Locale.getDefault().toLanguageTag())
        assertEquals("Bakery", ScFeatures.getFeature(Node(1, LatLon(0.0, 0.0), mapOf("shop" to "bakery")))?.name)
        assertEquals(null, ScFeatures.getFeature(Node(1, LatLon(0.0, 0.0), mapOf("fixme" to "x"))))
        val placeName = CUSTOM_QUESTS.getValue("AddPlaceName")
        assertTrue(placeName.isApplicable(Node(1, LatLon(0.0, 0.0), mapOf("shop" to "bakery"))))
        assertFalse(placeName.isApplicable(Node(1, LatLon(0.0, 0.0), mapOf("shop" to "bakery", "name" to "Bread"))))
    }

    @Test fun `a port keeps only what getApplicableElements returns`() {
        val tags = mapOf("amenity" to "recycling", "recycling_type" to "container", "recycling:clothes" to "yes")
        val bin = CUSTOM_QUESTS.getValue("AddClothingBinOperator")
        assertTrue(bin.isApplicable(Node(1, LatLon(0.0, 0.0), tags)))
        // getApplicableElements only looks at nodes
        assertFalse(bin.isApplicable(Way(1, listOf(1, 2, 3, 1), tags)))
    }
}
