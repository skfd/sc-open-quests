package openquests

import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.File
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class TagMapTest {
    private fun tagMap(vararg tags: Pair<String, String>) = TagMap(tags.size).apply { for ((k, v) in tags) add(k, v) }

    @Test fun `behaves as a map of the same tags`() {
        val tags = arrayOf("highway" to "residential", "name" to "Main St", "lanes" to "2")
        val map = tagMap(*tags)
        val plain = hashMapOf(*tags)
        assertEquals<Map<String, String>>(plain, map)
        assertEquals<Map<String, String>>(map, plain)
        assertEquals(plain.hashCode(), map.hashCode())
        assertEquals(3, map.size)
        assertEquals("2", map["lanes"])
        assertNull(map["surface"])
        assertTrue(map.containsKey("name"))
        assertFalse(map.containsKey("surface"))
        assertEquals(plain.keys, map.keys)
        assertEquals(plain.values.toSet(), map.values.toSet())
        assertEquals(plain.entries.map { it.key to it.value }.toSet(), map.entries.map { it.key to it.value }.toSet())
        assertEquals(plain, map.toMutableMap())
    }

    @Test fun `a key given twice keeps the last value`() {
        val map = tagMap("a" to "1", "b" to "2", "a" to "3")
        assertEquals(2, map.size)
        assertEquals("3", map["a"])
    }

    @Test fun `grows past its capacity`() {
        val map = TagMap(1)
        for (i in 0 until 100) map.add("k$i", "v$i")
        assertEquals(100, map.size)
        for (i in 0 until 100) assertEquals("v$i", map["k$i"])
    }

    @Test fun `an empty key and value are tags`() {
        val map = tagMap("" to "")
        assertEquals("", map[""])
        assertTrue(map.containsKey(""))
    }

    private fun both(filter: String, tags: Map<String, String>, timestamp: Long = 0L): Pair<Boolean, Boolean> {
        val expression = filter.toElementFilterExpression()
        val fast = TagMap(tags.size).apply { for ((k, v) in tags) add(k, v) }
        return expression.matches(Node(1, LatLon(0.0, 0.0), HashMap(tags), 1, timestamp)) to
            expression.matches(Node(1, LatLon(0.0, 0.0), fast, 1, timestamp))
    }

    @Test fun `what can hold without a key is not rejected`() {
        for (filter in listOf(
            "nodes with !a", "nodes with a != b", "nodes with a !~ b|c", "nodes with older today -1 years",
            "nodes with !(a and b)", "nodes with b or !a", "nodes with ~x|y !~ z",
        )) {
            val (plain, fast) = both(filter, mapOf("other" to "tag"))
            assertTrue(plain, filter)
            assertEquals(plain, fast, filter)
        }
    }

    @Test fun `an element with none of the keys is rejected`() {
        assertEquals(false to false, both("nodes with a and (b or c = 1)", mapOf("a" to "1")))
        assertEquals(true to true, both("nodes with a and (b or c = 1)", mapOf("a" to "1", "c" to "1")))
        // `a older ...` means the tag a, older than that
        assertEquals(false to false, both("nodes with a older today -1 years", mapOf("other" to "tag")))
    }

    /** every filter of the registry, on tags made of its own keys and values: the fast reject and the
     *  plain evaluation agree, also for the age tests */
    @Test fun `the fast reject changes no result of any quest filter`() {
        val quests = Json.parseToJsonElement(File("data/quests/v64.1.json").readText()).jsonObject["quests"]!!.jsonArray
        val filters = quests.mapNotNull { it.jsonObject["elementFilter"]?.jsonPrimitive?.content }
        assertTrue(filters.size > 100)
        val random = Random(1)
        var matched = 0
        for (filter in filters) {
            val expression = filter.toElementFilterExpression()
            val words = Regex("[a-zA-Z_:]+").findAll(filter).map { it.value }.distinct().toList()
            repeat(300) {
                val tags = HashMap<String, String>()
                repeat(random.nextInt(1, 8)) { tags[words.random(random)] = words.random(random) }
                val fast = TagMap(tags.size).apply { for ((k, v) in tags) add(k, v) }
                val ts = random.nextLong(0, 1_800_000_000_000L)
                val results = listOf(
                    Way(1, listOf(1, 2), tags, 1, ts) to Way(1, listOf(1, 2), fast, 1, ts),
                    Node(1, LatLon(0.0, 0.0), tags, 1, ts) to Node(1, LatLon(0.0, 0.0), fast, 1, ts),
                )
                for ((a, b) in results) {
                    val expected = expression.matches(a)
                    assertEquals(expected, expression.matches(b), "$filter on $tags")
                    if (expected) matched++
                }
            }
        }
        assertTrue(matched > 1000, "the elements hardly match anything: $matched")
    }
}
