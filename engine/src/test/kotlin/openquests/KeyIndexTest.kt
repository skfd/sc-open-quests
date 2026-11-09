package openquests

import de.westnordost.streetcomplete.data.elementfilter.ElementFilterExpression
import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.BoundingBox
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Relation
import de.westnordost.streetcomplete.data.osm.mapdata.RelationMember
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.File
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** Candidates by key ([candidates]) must keep every element a filter matches, in the list's order. */
class KeyIndexTest {
    private val filters: List<ElementFilterExpression> by lazy {
        val quests = Json.parseToJsonElement(File("data/quests/v64.1.json").readText()).jsonObject["quests"]!!.jsonArray
        val fromQuests = quests.mapNotNull { it.jsonObject["elementFilter"]?.jsonPrimitive?.content }
        (fromQuests + listOf(
            "nodes, ways, relations with a and (b or c = 1)",
            "nodes, ways with !a",                       // no clause: the whole list
            "ways with highway ~ footway|path or railway",
            "nodes with a older today -1 years",
        )).map { it.toElementFilterExpression() }
    }

    /** random elements, a third untagged, tags from the keys the filters name and values they test for */
    private fun mapData(seed: Int): ArrayMapData {
        val random = Random(seed)
        val keys = filters.flatMap { f -> f.keyReject.clauses.flatten() }.distinct() + listOf("name", "other")
        val values = listOf("yes", "no", "1", "residential", "footway", "path", "crossing", "designated", "private",
            "traffic_signals", "uncontrolled", "kerb", "lowered", "building", "house", "2020-01-01")
        fun tags(): Map<String, String> {
            if (random.nextInt(3) == 0) return emptyMap()
            val n = 1 + random.nextInt(4)
            return TagMap(n).apply { repeat(n) { add(keys.random(random), values.random(random)) } }
        }
        val nodes = List(3000) { Node(it + 1L, LatLon(0.0, 0.0), tags(), 1, 0) }
        val ways = List(1500) { Way(it + 1L, listOf(1L, 2L, 3L), tags(), 1, 0) }
        val relations = List(300) {
            Relation(it + 1L, listOf(RelationMember(ElementType.WAY, 1L, "outer")), tags(), 1, 0)
        }
        return ArrayMapData(BoundingBox(LatLon(0.0, 0.0), LatLon(1.0, 1.0)), nodes, ways,
            List(ways.size) { null }, relations, List(relations.size) { null })
    }

    @Test fun `every element a filter matches is a candidate, in the same order`() {
        var matched = 0
        var skipped = 0L
        for (seed in 1..3) {
            val md = mapData(seed)
            for (f in filters) {
                for (list in listOf(md.nodes, md.ways, md.relations)) {
                    val expected = list.filter(f::matches)
                    val candidates = md.candidates(list, f)
                    assertEquals(expected, candidates.filter(f::matches), "$f")
                    matched += expected.size
                    skipped += list.size - candidates.size
                }
                assertEquals(md.filter(f::matches), md.candidates(f).filter(f::matches), "$f, whole map data")
            }
        }
        // the test means something only if filters match and candidates leave elements out
        assertTrue(matched > 1000, "matched $matched")
        assertTrue(skipped > 1_000_000, "skipped $skipped")
    }

    @Test fun `an expression with no clause gives the whole list`() {
        val md = mapData(4)
        val f = "nodes with !a".toElementFilterExpression()
        assertEquals(md.nodes, md.candidates(md.nodes, f))
    }
}
