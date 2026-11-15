package openquests

import de.westnordost.streetcomplete.data.osm.geometry.ElementGeometry
import de.westnordost.streetcomplete.data.osm.geometry.ElementPointGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.BoundingBox
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Relation
import de.westnordost.streetcomplete.data.osm.mapdata.RelationMember
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import de.westnordost.streetcomplete.osm.kerb.findAllKerbNodes
import de.westnordost.streetcomplete.quests.building_entrance.AddEntrance
import de.westnordost.streetcomplete.quests.crossing_kerb_height.AddCrossingKerbHeight
import de.westnordost.streetcomplete.quests.cycleway.AddCycleway
import de.westnordost.streetcomplete.quests.kerb_height.AddKerbHeight
import de.westnordost.streetcomplete.quests.tactile_paving.AddTactilePavingKerb
import openquests.custom.AreaQuest
import openquests.fast.FastAddCrossingKerbHeight
import openquests.fast.FastAddCycleway
import openquests.fast.FastAddEntrance
import openquests.fast.FastAddKerbHeight
import openquests.fast.FastAddTactilePavingKerb
import openquests.fast.KERB_NODES
import kotlin.random.Random
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.time.Clock

/**
 * The twins that know a node by its place in the map data instead of keeping sets of ids (the kerb search,
 * AddEntrance, AddCrossingKerbHeight) and AddCycleway's, against SC's own code on small random map data
 * made to hit their rules: few node ids, so ways share ends and inner nodes; ways of one node, closed
 * ways, ways with a node the map data lacks, ways with no geometry; the tags the rules read. The same
 * elements in the same order, now and with the clock long ago.
 */
class NodeSetTwinsTest {
    @AfterTest fun restore() = EngineClock.install(Clock.System.now())

    private val places = listOf(LatLon(52.52, 13.40), LatLon(50.85, 4.35), LatLon(52.37, 4.90), LatLon(51.51, -0.12),
        LatLon(43.65, -79.38), LatLon(35.68, 139.69), LatLon(0.0, -30.0))

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

        val nodeCount = 120 + r.nextInt(200)
        val nodes = List(nodeCount) { i ->
            val tags = if (r.nextInt(100) < 55) emptyMap() else tagsOf(
                "barrier" to arrayOf("kerb", "kerb", "bollard", "gate"),
                "kerb" to arrayOf("raised", "lowered", "flush", "yes", "unknown", "no", "rolled"),
                "kerb:left" to arrayOf("raised"), "kerb:right" to arrayOf("lowered"),
                "tactile_paving" to arrayOf("yes", "no", "unknown", "incorrect"),
                "highway" to arrayOf("crossing", "crossing", "traffic_signals"),
                "foot" to arrayOf("no", "yes"), "crossing:continuous" to arrayOf("yes", "no"),
                "entrance" to arrayOf("main", "yes"), "noexit" to arrayOf("yes"), "railway" to arrayOf("level_crossing"),
                "addr:housenumber" to arrayOf("1", "2"), "ref" to arrayOf("7"), "name" to arrayOf("x"), "level" to arrayOf("0"),
                "shop" to arrayOf("bakery"), "source" to arrayOf("survey"), "wheelchair" to arrayOf("yes"),
                "check_date:kerb" to arrayOf("2012-05-01", "2024-03-01"), "kerb:check_date" to arrayOf("2015-01-01"),
                "check_date:tactile_paving" to arrayOf("2013-01-01", "2025-01-01"),
                chance = 12)
            Node(i + 1L, places[r.nextInt(places.size)], tags, 1 + r.nextInt(3), stamp())
        }
        // ids up to nodeCount + 6: the last few are nodes the map data lacks
        fun nodeId() = 1L + r.nextInt(nodeCount + 6)
        val ways = List(150 + r.nextInt(250)) { i ->
            val n = pick(1, 2, 2, 3, 3, 4, 5, 6, 9)
            val ids = MutableList(n) { nodeId() }
            if (n > 2 && r.nextInt(6) == 0) ids[n - 1] = ids[0]
            val kind = r.nextInt(100)
            val tags = when {
                kind < 30 -> tagsOf(
                    "highway" to arrayOf("footway", "footway", "path", "cycleway", "steps", "pedestrian"),
                    "footway" to arrayOf("crossing", "crossing", "sidewalk", "sidewalk", "traffic_island", "access_aisle", "link"),
                    "foot" to arrayOf("yes", "designated", "no"), "area" to arrayOf("yes"), "access" to arrayOf("private", "no", "yes"),
                    "tunnel" to arrayOf("yes", "no"), "covered" to arrayOf("yes", "no"), "location" to arrayOf("roof", "underground"),
                    chance = 45).let { if (it.containsKey("highway") || r.nextInt(3) == 0) it else TagMap(1).apply { add("highway", "footway") } }
                kind < 62 -> tagsOf(
                    "highway" to arrayOf("residential", "residential", "service", "primary", "secondary", "tertiary", "unclassified", "living_street", "busway", "track", "construction"),
                    "construction" to arrayOf("residential", "footway"), "service" to arrayOf("driveway", "alley"),
                    "access" to arrayOf("private", "no", "yes"), "area" to arrayOf("yes"),
                    "sidewalk" to arrayOf("no", "none", "both", "separate"), "sidewalk:both" to arrayOf("no", "yes"),
                    "sidewalk:left" to arrayOf("no", "yes"), "sidewalk:right" to arrayOf("none", "yes"),
                    "cycleway" to arrayOf("lane", "track", "no", "shared_lane", "opposite", "opposite_lane", "separate", "something", "shared", "share_busway"),
                    "cycleway:left" to arrayOf("lane", "track", "no", "separate", "shared_lane", "bogus"),
                    "cycleway:right" to arrayOf("lane", "track", "no", "advisory_lane"),
                    "cycleway:both" to arrayOf("lane", "no", "separate", "shared_lane"),
                    "cycleway:lane" to arrayOf("advisory", "exclusive", "pictogram"), "cycleway:both:lane" to arrayOf("advisory", "exclusive"),
                    "cycleway:left:lane" to arrayOf("advisory", "pictogram"),
                    "oneway" to arrayOf("yes", "-1", "no"), "oneway:bicycle" to arrayOf("no", "yes"),
                    "bicycle" to arrayOf("no", "designated", "use_sidepath", "yes"), "bicycle_road" to arrayOf("yes"),
                    "sidewalk:bicycle" to arrayOf("yes"), "maxspeed" to arrayOf("20", "30", "50", "70"),
                    "surface" to arrayOf("asphalt", "gravel"), "motorroad" to arrayOf("yes"),
                    "check_date:cycleway" to arrayOf("2015-06-01", "2025-06-01"), "cycleway:check_date" to arrayOf("2011-01-01"),
                    chance = 16).let { if (it.containsKey("highway") || r.nextInt(4) == 0) it else TagMap(it.size + 1).apply { add("highway", "residential"); for ((k, v) in it) add(k, v) } }
                kind < 80 -> tagsOf(
                    "building" to arrayOf("apartments", "retail", "yes", "house", "school", "roof", "no"),
                    "location" to arrayOf("underground"), "layer" to arrayOf("1"), "barrier" to arrayOf("kerb", "kerb", "wall"),
                    chance = 60)
                kind < 90 -> tagsOf("barrier" to arrayOf("kerb"), "tunnel" to arrayOf("yes"), "covered" to arrayOf("yes"),
                    "location" to arrayOf("roof", "rooftop"), chance = 60)
                else -> emptyMap()
            }
            Way(i + 1L, ids, tags, 1 + r.nextInt(3), stamp())
        }
        val wayGeometries: List<ElementGeometry?> = ways.map { if (r.nextInt(12) == 0) null else ElementPointGeometry(places[r.nextInt(places.size)]) }
        val relations = List(30) { i ->
            val members = List(1 + r.nextInt(4)) {
                RelationMember(pick(ElementType.WAY, ElementType.WAY, ElementType.NODE), 1L + r.nextInt(ways.size + 5), pick("outer", "inner", ""))
            }
            val tags = tagsOf("type" to arrayOf("multipolygon", "multipolygon", "site"),
                "building" to arrayOf("apartments", "retail", "yes", "hospital"), "layer" to arrayOf("1"), chance = 75)
            Relation(i + 1L, members, tags, 1, stamp())
        }
        return ArrayMapData(BoundingBox(LatLon(-90.0, -180.0), LatLon(90.0, 180.0)), nodes, ways, wayGeometries,
            relations, List(relations.size) { null })
    }

    private fun keys(es: Iterable<de.westnordost.streetcomplete.data.osm.mapdata.Element>) = es.map { it.type to it.id }

    @Test fun `each twin gives its port's elements in the port's order, at both clocks`() {
        EngineClock.install(parseToday("2026-11-15T00:00:00Z"))
        val twins: List<Pair<AreaQuest, AreaQuest>> = listOf(
            FastAddEntrance to AddEntrance, FastAddCrossingKerbHeight to AddCrossingKerbHeight, FastAddCycleway to AddCycleway,
            FastAddKerbHeight to AddKerbHeight, FastAddTactilePavingKerb to AddTactilePavingKerb)
        val found = IntArray(twins.size + 1)
        for (seed in 1..400) {
            val md = mapData(seed)
            val kerbs = KERB_NODES.of(md)
            assertEquals(md.findAllKerbNodes().toList().map { it.id }, kerbs.map { it.id }, "kerb nodes, seed $seed")
            found[twins.size] += kerbs.size
            for ((i, pair) in twins.withIndex()) {
                val (twin, port) = pair
                assertEquals(port.name, twin.name)
                val now = keys(twin.getApplicableElements(md))
                assertEquals(keys(port.getApplicableElements(md)), now, "${twin.name}, seed $seed")
                found[i] += now.size
                EngineClock.at(EngineClock.LONG_AGO) {
                    assertEquals(keys(port.getApplicableElements(md)), keys(twin.getApplicableElements(md)), "${twin.name} long ago, seed $seed")
                }
            }
        }
        // a test in which every twin and the kerb search find something, and not everything
        for ((i, n) in found.withIndex()) assertTrue(n > 200, "${twins.getOrNull(i)?.first?.name ?: "kerb nodes"} found $n elements over all seeds")
    }
}
