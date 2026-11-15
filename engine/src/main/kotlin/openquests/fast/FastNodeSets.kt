package openquests.fast

import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.data.osm.mapdata.MapDataWithGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import de.westnordost.streetcomplete.quests.building_entrance.AddEntrance
import de.westnordost.streetcomplete.quests.crossing_kerb_height.AddCrossingKerbHeight
import openquests.ArrayMapData
import openquests.LongArrayAsList
import openquests.candidates
import java.util.BitSet

// Twins of the quests whose SC code gathers the node ids of some ways into a `HashSet<Long>` (an object per
// id, millions in a city) and then asks it about the map data's nodes. On a city's map data a node is known
// by its place in the map data's nodes, so "is a node of such a way" is a mark at that place. An id that is
// not a node of the map data is asked of no set by SC's code either: its questions are about the map data's
// own nodes.

/** a way's node id at [i], without making an object of it where the list is the engine's own */
internal fun List<Long>.at(i: Int): Long = if (this is LongArrayAsList) long(i) else this[i]

internal inline fun Way.eachNodeId(f: (Long) -> Unit) {
    val ids = nodeIds
    for (i in 0 until ids.size) f(ids.at(i))
}

/** [mark] set in [marks] at the place of each of the way's nodes that the map data holds */
private fun ArrayMapData.markNodesOf(way: Way, marks: ByteArray, mark: Int) = way.eachNodeId { id ->
    val p = nodePosition(id)
    if (p >= 0) marks[p] = (marks[p].toInt() or mark).toByte()
}

/**
 * SC's AddEntrance.getApplicableElements (ported/.../AddEntrance.kt) on a city's map data, the same nodes
 * in the same order. Its three sets of node ids (of buildings, of incoming paths, of excluded ways) are
 * three marks per node, and the nodes with the first two and not the third are then asked what SC asks
 * them, in the map data's order. The buildings are looked for among the ways and relations that hold the
 * key (SC's code offers the filter every node too; it takes none). On any other map data: the port.
 * Filters and `couldBeAnEntrance` copied verbatim.
 */
object FastAddEntrance : FastTwin {
    override val name = "AddEntrance"
    override val usesAge = false
    override val sourceSha256 = "e79624bde1f83e2b04d14342c9e285d86da623b250bbfd399dc9e3e56459d8a9"

    private val withoutEntranceFilter by lazy { """
        nodes with
          !entrance and !barrier and noexit != yes and !railway
    """.toElementFilterExpression() }

    private val buildingFilter by lazy { """
        ways, relations with
          building
          and building !~ yes|no|service|shed|house|detached|terrace|semi|semidetached_house|roof|carport|construction
          and location != underground
          and !layer
    """.toElementFilterExpression() }

    private val incomingWaysFilter by lazy { """
        ways with
          highway ~ path|footway|steps|cycleway
          and area != yes
          and access !~ private|no
    """.toElementFilterExpression() }

    private val excludedWaysFilter by lazy { """
        ways with
          (tunnel and tunnel != no)
          or (covered and covered != no)
          or location ~ roof|rooftop
    """.toElementFilterExpression() }

    private const val BUILDING = 1
    private const val INCOMING = 2
    private const val EXCLUDED = 4

    override fun getApplicableElements(mapData: MapDataWithGeometry): Iterable<Element> {
        if (mapData !is ArrayMapData) return AddEntrance.getApplicableElements(mapData)
        val nodes = mapData.nodes
        val marks = ByteArray(nodes.size)

        for (way in mapData.candidates(mapData.ways, buildingFilter)) {
            if (buildingFilter.matches(way)) mapData.markNodesOf(way, marks, BUILDING)
        }
        for (relation in mapData.candidates(mapData.relations, buildingFilter)) {
            // SC's getMultipolygonNodeIds
            if (!buildingFilter.matches(relation) || relation.tags["type"] != "multipolygon") continue
            for (member in relation.members) {
                if (member.type != ElementType.WAY) continue
                mapData.getWay(member.ref)?.let { mapData.markNodesOf(it, marks, BUILDING) }
            }
        }
        for (way in mapData.candidates(mapData.ways, incomingWaysFilter)) {
            if (incomingWaysFilter.matches(way)) mapData.markNodesOf(way, marks, INCOMING)
        }
        for (way in mapData.candidates(mapData.ways, excludedWaysFilter)) {
            if (excludedWaysFilter.matches(way)) mapData.markNodesOf(way, marks, EXCLUDED)
        }

        val out = ArrayList<Element>()
        for (p in marks.indices) {
            if (marks[p].toInt() != (BUILDING or INCOMING)) continue
            val node = nodes[p]
            if (node.couldBeAnEntrance() && withoutEntranceFilter.matches(node)) out += node
        }
        return out
    }

    private fun Node.couldBeAnEntrance(): Boolean = tags.isEmpty() || tags.keys.all { key ->
        key.startsWith("addr:") || key in keysRelatedToAddress
    }

    private val keysRelatedToAddress = setOf("ref", "level", "name", "source", "source:addr")
}

/** The nodes of the ways AddCrossingKerbHeight excludes, as a bit per node of the map data. The filter
 *  reads no clock, and the quest's runs (now, the other resurvey settings, long ago) each gathered them. */
private val CROSSING_KERB_EXCLUDED = PerMapData("crossing kerbs: excluded ways' nodes") { mapData ->
    val bits = BitSet()
    if (mapData is ArrayMapData) {
        for (way in mapData.candidates(mapData.ways, crossingKerbExcludedWaysFilter)) {
            if (crossingKerbExcludedWaysFilter.matches(way)) way.eachNodeId { id ->
                val p = mapData.nodePosition(id)
                if (p >= 0) bits.set(p)
            }
        }
    }
    bits
}

private val crossingKerbExcludedWaysFilter by lazy { """
    ways with
      highway and access ~ private|no
      or highway ~ footway|path|cycleway
      or highway = service and service = driveway
      or sidewalk:both ~ none|no
      or sidewalk ~ none|no
      or (sidewalk:left ~ none|no and sidewalk:right ~ none|no)
""".toElementFilterExpression() }

/**
 * SC's AddCrossingKerbHeight.getApplicableElements (ported/.../AddCrossingKerbHeight.kt) on a city's map
 * data: the excluded ways' nodes come from [CROSSING_KERB_EXCLUDED], found once for the quest's runs, and
 * are a bit per node instead of a set of ids. The same crossings in the same order. On any other map
 * data: the port. Filters copied verbatim.
 */
object FastAddCrossingKerbHeight : FastTwin {
    override val name = "AddCrossingKerbHeight"
    override val usesAge = true
    override val sourceSha256 = "aa362b68f55c11340e2f2ec441e0e5e4b9e84cae4f08f9a66d1891a31e7aa25c"
    override val shared = listOf(CROSSING_KERB_EXCLUDED)

    private val crossingFilter by lazy { """
        nodes with
          highway = crossing
          and foot != no
          and crossing:continuous != yes
          and (!kerb:left or !kerb:right)
          and (
            !kerb
            or kerb ~ yes|unknown
            or kerb = raised and kerb older today -8 years
            or kerb !~ no|rolled and kerb older today -12 years
          )
    """.toElementFilterExpression() }

    override fun getApplicableElements(mapData: MapDataWithGeometry): Iterable<Element> {
        if (mapData !is ArrayMapData) return AddCrossingKerbHeight.getApplicableElements(mapData)
        val excluded = CROSSING_KERB_EXCLUDED.of(mapData)
        return mapData.candidates(mapData.nodes, crossingFilter)
            .filter { crossingFilter.matches(it) && !excluded.get(mapData.nodePosition(it.id)) }
    }
}
