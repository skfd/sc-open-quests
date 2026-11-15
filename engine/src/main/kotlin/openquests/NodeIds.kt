package openquests

import de.westnordost.streetcomplete.data.osm.mapdata.MapData
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import openquests.fast.LongSet
import openquests.fast.eachNodeId

/**
 * The node ids of some ways, for the one question SC's quests put to such a set: `id in it`. It is no
 * `Set` on purpose: a port that iterates it or asks its size does not compile, so the rule that makes
 * these (NODE_IDS in port_area_quests.py) cannot change a result it was not written for.
 */
sealed interface NodeIds {
    operator fun contains(id: Long): Boolean
}

/** SC's own set: `ways.flatMapTo(HashSet()) { it.nodeIds }`. */
private class HashedNodeIds(val ids: HashSet<Long>) : NodeIds {
    override fun contains(id: Long) = id in ids
}

/**
 * The same set on a city's map data, where a node is known by its place in the map data's nodes: a bit
 * at that place, and the ids of nodes the map data lacks in [others] (a way at the edge of the data has
 * some), so every id is answered as SC's `HashSet<Long>` answers it, whoever asks.
 */
private class MarkedNodeIds(private val mapData: ArrayMapData) : NodeIds {
    private val marks = LongArray((mapData.nodes.size + 63) ushr 6)
    private var others: LongSet? = null

    fun add(id: Long) {
        val p = mapData.nodePosition(id)
        if (p >= 0) marks[p ushr 6] = marks[p ushr 6] or (1L shl p)
        else if (KEEP_OTHER_NODE_IDS) (others ?: LongSet().also { others = it }).add(id)
    }

    override fun contains(id: Long): Boolean {
        val p = mapData.nodePosition(id)
        return if (p >= 0) marks[p ushr 6] and (1L shl p) != 0L else others?.contains(id) == true
    }
}

/** Both, under `-Dopenquests.verifyFast=true`: every answer of the marks held against SC's set. */
private class CheckedNodeIds(private val marked: NodeIds, private val hashed: HashedNodeIds, mapData: ArrayMapData) : NodeIds {
    init {
        for (node in mapData.nodes) contains(node.id)
        for (id in hashed.ids) contains(id)
    }

    override fun contains(id: Long): Boolean {
        val answer = id in marked
        check(answer == (id in hashed)) { "node ids as marks: node $id is ${if (answer) "in" else "not in"} the marks, and SC's set says otherwise" }
        return answer
    }
}

/** `-Dopenquests.nodeMarks=false`: every port keeps SC's `HashSet<Long>` on a city's map data too. */
val NODE_MARKS = System.getProperty("openquests.nodeMarks") != "false"

/** A test's switch: false drops the ids of nodes the map data lacks, to show a test (and verifyFast)
 *  fails on a set that knows only the map data's own nodes. */
@Volatile var KEEP_OTHER_NODE_IDS = true

private fun hashed(ways: Iterator<Way>): HashedNodeIds {
    val ids = HashSet<Long>()
    for (way in ways) ids.addAll(way.nodeIds)
    return HashedNodeIds(ids)
}

private fun nodeIds(mapData: MapData, ways: () -> Iterator<Way>): NodeIds {
    if (mapData !is ArrayMapData || !NODE_MARKS) return hashed(ways())
    val marked = MarkedNodeIds(mapData)
    for (way in ways()) way.eachNodeId { marked.add(it) }
    return if (VERIFY_FAST) CheckedNodeIds(marked, hashed(ways()), mapData) else marked
}

/**
 * What a port's `.flatMapTo(HashSet()) { it.nodeIds }` became (NODE_IDS in port_area_quests.py): the node
 * ids of these ways, as marks by place on a city's map data and as SC's `HashSet` on any other.
 */
fun Iterable<Way>.nodeIdsIn(mapData: MapData): NodeIds = nodeIds(mapData) { iterator() }

fun Sequence<Way>.nodeIdsIn(mapData: MapData): NodeIds = nodeIds(mapData) { iterator() }
