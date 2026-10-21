package openquests

import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import openquests.custom.CUSTOM_QUESTS
import openquests.custom.ScFeatures
import openquests.fast.FAST_TWINS
import openquests.ported.AREA_QUESTS
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
            .filter { !it.startsWith("helper:") } // androidMain helper files copied for the area quests
        assertEquals(pinned.sorted(), (CUSTOM_QUESTS.keys + AREA_QUESTS.keys).sorted())
    }

    @Test fun `every fast twin copies the pinned version of its SC file`() {
        val sha = File("engine/PORTED-QUESTS.txt").readLines()
            .filter { it.isNotBlank() && !it.trimStart().startsWith("#") }
            .associate { it.trim().split(Regex("\\s+")).let { f -> f[0] to f.last() } }
        for (twin in FAST_TWINS.values) {
            assertTrue(twin.name in AREA_QUESTS, "${twin.name} has a twin but no port")
            assertEquals(sha[twin.name], twin.sourceSha256, "SC's ${twin.name} moved on: redo its fast twin")
        }
    }

    @Test fun `ported quests are counted with the port's age flag and element types`() {
        val registry = Registry.load(File("data/quests/v64.0.json"))
        val sidewalk = registry.quests.single { it.name == "AddSidewalk" }
        assertTrue(sidewalk.isCounted && !sidewalk.isFilter)
        assertEquals(listOf("ways"), sidewalk.elementTypes)
        assertTrue(registry.quests.single { it.name == "AddOpeningHours" }.usesAge)
        assertEquals(140 + CUSTOM_QUESTS.size + AREA_QUESTS.size, registry.countedQuests.size) // 140 filter quests in v64.0
        assertTrue(registry.quests.single { it.name == "AddCrossing" }.area != null)
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
