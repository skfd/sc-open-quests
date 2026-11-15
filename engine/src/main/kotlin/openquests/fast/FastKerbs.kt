package openquests.fast

import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.MapDataWithGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import de.westnordost.streetcomplete.osm.ALL_PATHS
import de.westnordost.streetcomplete.osm.ALL_ROADS
import de.westnordost.streetcomplete.osm.kerb.couldBeAKerb
import de.westnordost.streetcomplete.osm.kerb.findAllKerbNodes
import openquests.ArrayMapData
import openquests.LongArrayAsList
import openquests.candidates

/** SC's `findAllKerbNodes()` (sc/.../osm/kerb/KerbUtil.kt) once per map data: [fastKerbNodes] on a city's
 *  map data, SC's own code on any other. It reads no clock, and AddKerbHeight and AddTactilePavingKerb both
 *  start from it in each of their four runs: eight identical searches per map data (London about 17 s each). */
val KERB_NODES = PerMapData<List<Node>>("kerb nodes") {
    if (it is ArrayMapData && FAST_KERB_SEARCH) fastKerbNodes(it) else it.findAllKerbNodes().toList()
}

/** `-Dopenquests.fastKerbs=false`: SC's own search instead of [fastKerbNodes]. */
private val FAST_KERB_SEARCH = System.getProperty("openquests.fastKerbs")?.toBoolean() ?: true

/** the pin of SC's osm/kerb/KerbUtil.kt, which [fastKerbNodes] copies (engine/PORTED-QUESTS.txt) */
private val KERB_UTIL_PIN = mapOf("helper:KerbUtil" to "15d05045d6a3813211ddc5ae1e0afe2f66d731f6f588027d32a300248cb6d020")

// SC's KerbUtil.kt keeps these private; copied verbatim
private val footwaysFilter by lazy { """
    ways with
      (
        highway ~ footway|path
        or highway = cycleway and foot ~ yes|designated
      )
      and area != yes
      and access !~ private|no and foot !~ no
""".toElementFilterExpression() }

private val waysFilter by lazy { """
    ways with
      highway ~ ${(ALL_ROADS + ALL_PATHS).joinToString("|")}
      or construction ~ ${(ALL_ROADS + ALL_PATHS).joinToString("|")}
""".toElementFilterExpression() }

private val handledFootwayValues = setOf("sidewalk", "traffic_island", "crossing", "access_aisle")

// only to find the elements that hold the key (candidates by key); the test itself is SC's `tags["barrier"] == "kerb"`
private val kerbWaysFilter by lazy { "ways with barrier = kerb".toElementFilterExpression() }
private val kerbNodesFilter by lazy { "nodes with barrier = kerb".toElementFilterExpression() }

// what is known of a node of the map data, a byte for each by its place in the map data's nodes
private const val CROSS_1 = 1        // an end of one crossing ...
private const val CROSS_MANY = 2     // ... or of more
private const val SIDE_1 = 4         // an end of one sidewalk ...
private const val SIDE_MANY = 8      // ... or of more
private const val DROPPED = 16       // SC's search removes it from the crossing ends
private const val SEEN = 32          // on a footway already
private const val ON_KERB_WAY = 64   // a node of a barrier=kerb way
private const val KERB = 128         // tagged barrier=kerb itself

/**
 * SC's `MapData.findAllKerbNodes()` on a city's map data: the same nodes in the same order. SC's code keeps
 * the footway nodes in a set of whole [Node]s (each hashed with its position and tags), counts the crossing
 * ends in a map of boxed ids from which it then removes every node of every road and path one by one, and
 * looks each of those up again for its `barrier` tag. Here a node is known by its place in the map data:
 *  - the footways' nodes in the ways' order, each once ([SEEN]), kept if it `couldBeAKerb()`: SC's set of
 *    equal nodes is a set of ids, since a map data has one node per id;
 *  - an id that is not a node of this map data cannot be a footway node, so what SC's sets and map hold
 *    of such ids never reaches the result and is not kept;
 *  - `findCrossingKerbEndNodeIds`: SC keeps the ids with exactly one crossing end, of those the ones with
 *    exactly one sidewalk end, and then removes ids by three rules that each look at one way. The counts
 *    ([CROSS_1], [SIDE_1]) and the removals ([DROPPED]) do not depend on each other's order, and SC's early
 *    returns (nothing left) give the empty set, as this does.
 * `-Dopenquests.verifyFast=true` holds AddKerbHeight and AddTactilePavingKerb, which start from this,
 * against their ports, which call SC's search.
 */
private fun fastKerbNodes(m: ArrayMapData): List<Node> {
    val nodes = m.nodes
    val flags = ByteArray(nodes.size)
    fun has(p: Int, f: Int) = (flags[p].toInt() and f) != 0
    fun flag(p: Int, f: Int) { flags[p] = (flags[p].toInt() or f).toByte() }
    fun count(p: Int, one: Int, many: Int) { flag(p, if (has(p, one or many)) many else one) }

    // 1. the footways' nodes that could be a kerb
    val footwayNodes = ArrayList<Node>()
    val footwayAt = IntList()
    for (way in m.candidates(m.ways, footwaysFilter)) if (footwaysFilter.matches(way)) way.eachNodeId { id ->
        val p = m.nodePosition(id)
        if (p >= 0 && !has(p, SEEN)) {
            flag(p, SEEN)
            val node = nodes[p]
            if (node.tags.isEmpty() || node.couldBeAKerb()) { footwayNodes += node; footwayAt.add(p) }
        }
    }

    // 2. the nodes of barrier=kerb ways
    for (way in m.candidates(m.ways, kerbWaysFilter)) if (way.tags["barrier"] == "kerb") way.eachNodeId { id ->
        val p = m.nodePosition(id)
        if (p >= 0) flag(p, ON_KERB_WAY)
    }

    // 3. findCrossingKerbEndNodeIds over the roads and paths
    val anyWays = m.candidates(m.ways, waysFilter).filter { waysFilter.matches(it) }
    var crossings = false
    for (way in anyWays) {
        val footway = way.tags["footway"]
        if ((footway == "crossing" || footway == "access_aisle") && footwaysFilter.matches(way)) {
            way.eachEndNodeId { id -> val p = m.nodePosition(id); if (p >= 0) { count(p, CROSS_1, CROSS_MANY); crossings = true } }
        }
    }
    if (crossings) {
        for (node in m.candidates(m.nodes, kerbNodesFilter)) if (node.tags["barrier"] == "kerb") flag(m.nodePosition(node.id), KERB)
        for (way in anyWays) {
            val footway = way.tags["footway"]
            if ((footway == "sidewalk" || footway == "traffic_island") && footwaysFilter.matches(way)) {
                way.eachEndNodeId { id -> val p = m.nodePosition(id); if (p >= 0) count(p, SIDE_1, SIDE_MANY) }
            }
            // SC drops an end shared with a node inside a way, and both ends of a way with a kerb node inside it
            var kerbInside = false
            val ids = way.nodeIds
            for (i in 1 until ids.size - 1) {
                val p = m.nodePosition(ids.at(i))
                if (p >= 0) { flag(p, DROPPED); if (has(p, KERB)) kerbInside = true }
            }
            // and an end shared with a way that is neither sidewalk nor crossing
            if (kerbInside || footway !in handledFootwayValues) {
                way.eachEndNodeId { id -> val p = m.nodePosition(id); if (p >= 0) flag(p, DROPPED) }
            }
        }
    }

    val out = ArrayList<Node>()
    for (i in footwayNodes.indices) {
        val node = footwayNodes[i]
        val f = flags[footwayAt[i]].toInt()
        val crossingEnd = (f and (CROSS_1 or CROSS_MANY or SIDE_1 or SIDE_MANY or DROPPED)) == (CROSS_1 or SIDE_1)
        if (node.tags["barrier"] == "kerb" || (f and ON_KERB_WAY) != 0 || crossingEnd) out += node
    }
    return out
}

/** SC's `nodeIds.firstAndLast()`: the one node of a way of one node once, else the first and the last (a
 *  closed way's node twice) */
private inline fun Way.eachEndNodeId(f: (Long) -> Unit) {
    val ids = nodeIds
    if (ids.isEmpty()) return
    f(ids.at(0))
    if (ids.size > 1) f(ids.at(ids.size - 1))
}

private class IntList {
    private var a = IntArray(1024)
    var size = 0
        private set
    fun add(v: Int) { if (size == a.size) a = a.copyOf(size * 2); a[size++] = v }
    operator fun get(i: Int) = a[i]
}

/**
 * SC's AddKerbHeight.getApplicableElements (ported/.../AddKerbHeight.kt), with one change: the kerb nodes
 * come from [KERB_NODES] instead of a search of their own. The same nodes in the same order, so the same
 * result. Filter copied verbatim.
 */
object FastAddKerbHeight : FastTwin {
    override val name = "AddKerbHeight"
    override val usesAge = true
    override val sourceSha256 = "a120e53280b83fec54c7be8a68a1815240d4e6d4f983290a9aaad1b3c4c917d3"
    override val shared = listOf(KERB_NODES)
    override val helperSha256 = KERB_UTIL_PIN

    private val eligibleKerbsFilter by lazy { """
        nodes with
          !kerb
          or kerb ~ yes|unknown
          or kerb = raised and kerb older today -8 years
          or kerb !~ no|rolled and kerb older today -12 years
    """.toElementFilterExpression() }

    override fun getApplicableElements(mapData: MapDataWithGeometry): Iterable<Element> =
        KERB_NODES.of(mapData).filter { eligibleKerbsFilter.matches(it) }
}

/**
 * SC's AddTactilePavingKerb.getApplicableElements (ported/.../AddTactilePavingKerb.kt), with one change: the
 * kerb nodes come from [KERB_NODES] instead of a search of their own. Filter copied verbatim.
 */
object FastAddTactilePavingKerb : FastTwin {
    override val name = "AddTactilePavingKerb"
    override val usesAge = true
    override val sourceSha256 = "03bea418f2f0756492fc6771858fd6a8f7c0b846cc081b3a758b7ca9ce71c36f"
    override val shared = listOf(KERB_NODES)
    override val helperSha256 = KERB_UTIL_PIN

    private val eligibleKerbsFilter by lazy { """
        nodes with
          !tactile_paving
          or tactile_paving = unknown
          or tactile_paving = no and tactile_paving older today -8 years
          or tactile_paving = yes and tactile_paving older today -12 years
    """.toElementFilterExpression() }

    override fun getApplicableElements(mapData: MapDataWithGeometry): Iterable<Element> =
        KERB_NODES.of(mapData).filter { eligibleKerbsFilter.matches(it) }
}
