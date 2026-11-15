package openquests

import de.westnordost.streetcomplete.data.osm.geometry.ElementGeometry
import de.westnordost.streetcomplete.data.osm.geometry.ElementPointGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.BoundingBox
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.MapDataWithGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Relation
import de.westnordost.streetcomplete.data.osm.mapdata.RelationMember
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import de.westnordost.streetcomplete.quests.barrier_opening.AddBarrierOpening
import de.westnordost.streetcomplete.quests.barrier_type.AddStileType
import de.westnordost.streetcomplete.quests.bollard_type.AddBollardType
import de.westnordost.streetcomplete.quests.building_entrance_reference.AddEntranceReference
import de.westnordost.streetcomplete.quests.crossing_island.AddCrossingIsland
import de.westnordost.streetcomplete.quests.crossing_markings.AddCrossingMarkings
import de.westnordost.streetcomplete.quests.crossing_signals.AddCrossingSignals
import de.westnordost.streetcomplete.quests.railway_crossing.AddRailwayCrossingBarrier
import de.westnordost.streetcomplete.quests.step_count.AddStepCountStile
import de.westnordost.streetcomplete.quests.tactile_paving.AddTactilePavingCrosswalk
import de.westnordost.streetcomplete.quests.traffic_signals_sound.AddTrafficSignalsSound
import de.westnordost.streetcomplete.quests.traffic_signals_vibrate.AddTrafficSignalsVibration
import openquests.custom.AreaQuest
import openquests.fast.FAST_TWINS
import openquests.ported.AREA_QUESTS
import java.io.File
import kotlin.random.Random
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlin.time.Clock

/**
 * [NodeIds], which the ports keep in place of SC's `HashSet<Long>` of some ways' node ids (NODE_IDS in
 * port_area_quests.py): every id answered as the HashSet answers it, and each port that has one giving the
 * same elements in the same order on a city's map data (marks by place) as on the same data seen as any
 * other map data (SC's set). Small random map data with few node ids, so ways share nodes, some of them
 * nodes the map data lacks.
 */
class NodeIdsTest {
    @AfterTest fun restore() { EngineClock.install(Clock.System.now()); KEEP_OTHER_NODE_IDS = true }

    private val place = LatLon(52.52, 13.40)

    private fun mapData(seed: Int): ArrayMapData {
        val r = Random(seed)
        fun <T> pick(vararg v: T) = v[r.nextInt(v.size)]
        fun tagsOf(vararg choices: Pair<String, Array<String>>, chance: Int): Map<String, String> {
            val t = TagMap(choices.size)
            for ((k, values) in choices) if (r.nextInt(100) < chance) t.add(k, values[r.nextInt(values.size)])
            return t
        }
        val year = 365L * 24 * 3600 * 1000
        fun stamp() = 1_262_304_000_000L + r.nextLong(17 * year) // 2010 to 2026

        val nodeCount = 150 + r.nextInt(200)
        val nodes = List(nodeCount) { i ->
            val tags = when (r.nextInt(10)) {
                0, 1, 2 -> emptyMap()
                3, 4 -> tagsOf(
                    "highway" to arrayOf("crossing", "crossing", "crossing", "traffic_signals"),
                    "crossing" to arrayOf("traffic_signals", "island", "unmarked"), "crossing:signals" to arrayOf("yes", "no"),
                    "crossing:island" to arrayOf("yes"), "crossing:markings" to arrayOf("zebra"), "foot" to arrayOf("no"),
                    "crossing:continuous" to arrayOf("yes"), "tactile_paving" to arrayOf("yes", "no", "unknown"),
                    "traffic_signals:sound" to arrayOf("no", "yes"), "traffic_signals:vibration" to arrayOf("no", "yes"),
                    chance = 30).let { if (it.containsKey("highway")) it else TagMap(1).apply { add("highway", "crossing") } }
                5 -> tagsOf("railway" to arrayOf("level_crossing", "level_crossing", "crossing"),
                    "crossing:barrier" to arrayOf("no", "full"), "crossing:chicane" to arrayOf("yes"), chance = 55)
                6, 7 -> tagsOf(
                    "barrier" to arrayOf("bollard", "bollard", "stile", "stile", "gate", "block", "cycle_barrier"),
                    "bollard" to arrayOf("rising"), "stile" to arrayOf("stepover", "ladder", "squeezer"),
                    "cycle_barrier" to arrayOf("single", "double"), "access" to arrayOf("private", "yes"),
                    "wheelchair" to arrayOf("no"), "maxwidth" to arrayOf("1"), "step_count" to arrayOf("2"), chance = 45)
                else -> tagsOf("entrance" to arrayOf("main", "main", "staircase", "yes"), "ref" to arrayOf("7"),
                    "name" to arrayOf("x"), "addr:flats" to arrayOf("1-9"), "noref" to arrayOf("yes"), chance = 40)
                    .let { if (r.nextInt(3) > 0 && !it.containsKey("entrance")) TagMap(1).apply { add("entrance", "main") } else it }
            }
            Node(i + 1L, place, tags, 1 + r.nextInt(3), stamp())
        }
        // ids up to nodeCount + 8: the last few are nodes the map data lacks
        fun nodeId() = 1L + r.nextInt(nodeCount + 8)
        val ways = List(120 + r.nextInt(200)) { i ->
            val n = pick(1, 2, 2, 3, 3, 4, 5, 6, 9)
            val ids = MutableList(n) { nodeId() }
            if (n > 2 && r.nextInt(6) == 0) ids[n - 1] = ids[0]
            val tags = when (r.nextInt(10)) {
                0 -> emptyMap()
                1, 2 -> tagsOf("building" to arrayOf("apartments", "apartments", "yes"), "ruins" to arrayOf("yes"), chance = 70)
                3 -> tagsOf("railway" to arrayOf("rail", "rail", "tram", "disused"), "embedded" to arrayOf("yes"),
                    "abandoned:railway" to arrayOf("rail"), chance = 50)
                else -> tagsOf(
                    "highway" to arrayOf("residential", "service", "service", "footway", "footway", "path", "cycleway", "cycleway",
                        "steps", "pedestrian", "construction", "primary"),
                    "service" to arrayOf("driveway", "alley"), "access" to arrayOf("private", "no", "yes"),
                    "foot" to arrayOf("yes", "designated", "permissive", "no", "private"), "area" to arrayOf("yes"),
                    "oneway" to arrayOf("yes", "no"), "footway" to arrayOf("traffic_island", "sidewalk"),
                    "ramp:wheelchair" to arrayOf("yes"), chance = 22)
                    .let { if (it.containsKey("highway") || r.nextInt(5) == 0) it else TagMap(it.size + 1).apply { add("highway", "residential"); for ((k, v) in it) add(k, v) } }
            }
            // some ways keep their ids as the engine's own list, as a city's ways do
            Way(i + 1L, if (r.nextBoolean()) LongArrayAsList(ids.toLongArray()) else ids, tags, 1 + r.nextInt(3), stamp())
        }
        val wayGeometries: List<ElementGeometry?> = ways.map { if (r.nextInt(12) == 0) null else ElementPointGeometry(place) }
        val relations = List(20) { i ->
            val members = List(1 + r.nextInt(4)) {
                RelationMember(pick(ElementType.WAY, ElementType.WAY, ElementType.NODE), 1L + r.nextInt(ways.size + 5), pick("outer", "inner"))
            }
            Relation(i + 1L, members, tagsOf("type" to arrayOf("multipolygon"), "building" to arrayOf("apartments"), chance = 80), 1, stamp())
        }
        return ArrayMapData(BoundingBox(LatLon(-90.0, -180.0), LatLon(90.0, 180.0)), nodes, ways, wayGeometries,
            relations, List(relations.size) { null })
    }

    private fun keys(es: Iterable<Element>) = es.map { it.type to it.id }

    private val ports: List<AreaQuest> = listOf(AddBollardType, AddBarrierOpening, AddStileType, AddEntranceReference,
        AddCrossingIsland, AddCrossingMarkings, AddCrossingSignals, AddRailwayCrossingBarrier, AddStepCountStile,
        AddTactilePavingCrosswalk, AddTrafficSignalsSound, AddTrafficSignalsVibration)

    /** every id from 0 to past the last one a way names: of the map data, of no way, of a way only */
    private fun disagreements(md: ArrayMapData, r: Random): Int {
        val some = md.ways.filter { r.nextInt(3) == 0 }
        val sc = some.flatMapTo(HashSet()) { it.nodeIds }
        val ours = listOf(some.nodeIdsIn(md), some.asSequence().nodeIdsIn(md))
        return (0L..md.nodes.size + 12).count { id -> ours.any { (id in it) != (id in sc) } }
    }

    @Test fun `every id is answered as SC's HashSet answers it, also one of no node of the map data`() {
        var lacking = 0
        for (seed in 1..200) {
            val md = mapData(seed)
            assertEquals(0, disagreements(md, Random(seed)), "seed $seed")
            lacking += md.ways.sumOf { w -> w.nodeIds.count { md.getNode(it) == null } }
        }
        assertTrue(lacking > 500, "ways name $lacking nodes the map data lacks")
        // the test's own check: a set that knows only the map data's nodes is caught
        KEEP_OTHER_NODE_IDS = false
        assertTrue((1..200).sumOf { disagreements(mapData(it), Random(it)) } > 100)
    }

    @Test fun `each port gives on a city's map data what it gives with SC's set, in the same order, at both clocks`() {
        EngineClock.install(parseToday("2026-11-15T00:00:00Z"))
        val found = IntArray(ports.size)
        for (seed in 1..300) {
            val md = mapData(seed)
            // the same data as some other map data: no marks, no candidates by key, SC's HashSet
            val plain = object : MapDataWithGeometry by md {}
            for ((i, port) in ports.withIndex()) {
                val now = keys(port.getApplicableElements(md))
                assertEquals(keys(port.getApplicableElements(plain)), now, "${port.name}, seed $seed")
                found[i] += now.size
                EngineClock.at(EngineClock.LONG_AGO) {
                    assertEquals(keys(port.getApplicableElements(plain)), keys(port.getApplicableElements(md)), "${port.name} long ago, seed $seed")
                }
            }
        }
        for ((i, n) in found.withIndex()) assertTrue(n > 100, "${ports[i].name} found $n elements over all seeds")
    }

    @Test fun `the ports that keep NodeIds are the ones tested here, and none of them has a fast twin`() {
        val root = File("engine/src/main/kotlin/ported")
        val marked = root.walkTopDown().filter { it.extension == "kt" && ".nodeIdsIn(mapData)" in it.readText() }
            .map { it.nameWithoutExtension }.toSet()
        assertEquals(ports.map { it.name }.toSet(), marked)
        for (name in marked) {
            assertTrue(name in AREA_QUESTS)
            // a twin is held against its port, which must then be SC's code as it is: rerun the script
            assertFalse(name in FAST_TWINS, "$name has a fast twin and a port that keeps NodeIds")
        }
    }

    @Test fun `under verifyFast a wrong answer of the marks stops the run`() {
        for (seed in 1..20) mapData(seed).let { md -> nodeIds(md, verify = true) { md.ways.iterator() } }
        KEEP_OTHER_NODE_IDS = false
        assertFailsWith<IllegalStateException> {
            for (seed in 1..20) mapData(seed).let { md -> nodeIds(md, verify = true) { md.ways.iterator() } }
        }
    }
}
