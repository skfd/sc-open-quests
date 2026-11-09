package openquests.fast

import openquests.candidates
import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.geometry.ElementGeometry
import de.westnordost.streetcomplete.data.osm.geometry.ElementPolylinesGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.MapDataWithGeometry
import de.westnordost.streetcomplete.osm.ALL_PATHS
import de.westnordost.streetcomplete.osm.ALL_ROADS
import de.westnordost.streetcomplete.quests.max_height.bridgeFilter
import de.westnordost.streetcomplete.quests.max_height.tunnelFilter
import de.westnordost.streetcomplete.util.ktx.containsAny
import de.westnordost.streetcomplete.util.math.intersect
import de.westnordost.streetcomplete.util.math.intersects
/**
 * SC's AddMaxHeight.getApplicableElements (ported/.../AddMaxHeight.kt), with two changes. The bridges
 * a road is checked against come from a [BoundsGrid] instead of the whole list, each with its geometry,
 * layer and node set worked out once: SC's `intersects` returns false when the bounds do not
 * intersect, so the result is the same; on a whole city the original compares every road with every
 * bridge. And a node's tag filter comes before the node id
 * sets, not after: both are pure tests joined by `&&`, and the filter rejects nearly every node without
 * boxing its id and hashing it into a set (42% of the quest's time in London). Filters copied verbatim.
 */
object FastAddMaxHeight : FastTwin {
    override val name = "AddMaxHeight"
    override val usesAge = false
    override val sourceSha256 = "723f092d98d20f5cd94801fd7f255bf34d93be01a89135c314ae7f17822bc74d"

    private val nodeFilter by lazy { """
        nodes with
          (
            barrier = height_restrictor
            or amenity = parking_entrance and parking ~ underground|multi-storey
          )
          and $noMaxHeight
    """.toElementFilterExpression() }

    private val roadsWithoutMaxHeightFilter by lazy { """
        ways with
          (
            highway ~ motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|unclassified|residential|living_street|track|road|busway
            or (highway = service and access !~ private|no and vehicle !~ private|no)
          )
          and $noMaxHeight
          and (access !~ private|no or (foot and foot !~ private|no))
    """.toElementFilterExpression() }

    private val railwayCrossingsFilter by lazy { """
        nodes with
          railway = level_crossing
          and $noMaxHeight
    """.toElementFilterExpression() }

    private val electrifiedRailwaysFilter by lazy { """
        ways with
          railway and railway != tram
          and electrified = contact_line
    """.toElementFilterExpression() }

    private val allRoadsFilter by lazy { """
        ways with
          highway ~ ${ALL_ROADS.joinToString("|")}
          and (access !~ private|no or (foot and foot !~ private|no))
    """.toElementFilterExpression() }

    private val allPathsFilter by lazy { """
        ways with
          highway ~ ${ALL_PATHS.joinToString("|")}
          and (access !~ private|no or (foot and foot !~ private|no))
    """.toElementFilterExpression() }

    private val noMaxHeight = """
        !maxheight
        and !maxheight:signed
        and !maxheight:physical
        and (!maxheight:forward or !maxheight:backward)
        and !maxheight:lanes
    """

    override fun getApplicableElements(mapData: MapDataWithGeometry): Iterable<Element> {
        val roadsNodeIds = mapData.candidates(mapData.ways, allRoadsFilter)
            .filter { allRoadsFilter.matches(it) }
            .flatMapTo(HashSet()) { it.nodeIds }

        val pathNodeIds = mapData.candidates(mapData.ways, allPathsFilter)
            .filter { allPathsFilter.matches(it) }
            .flatMapTo(HashSet()) { it.nodeIds }

        val nodesWithoutHeight = mapData.candidates(mapData.nodes, nodeFilter)
            .filter { nodeFilter.matches(it) && it.id in roadsNodeIds }

        val electrifiedRailwayNodeIds = mapData.candidates(mapData.ways, electrifiedRailwaysFilter)
            .filter { electrifiedRailwaysFilter.matches(it) }
            .flatMapTo(HashSet()) { it.nodeIds }

        val railwayCrossingNodesWithoutHeight = mapData.candidates(mapData.nodes, railwayCrossingsFilter)
            .filter {
                railwayCrossingsFilter.matches(it)
                && (it.id in roadsNodeIds || it.id in pathNodeIds)
                && it.id in electrifiedRailwayNodeIds
            }

        val roadsWithoutHeight = mapData.candidates(mapData.ways, roadsWithoutMaxHeightFilter).filter { roadsWithoutMaxHeightFilter.matches(it) }

        val tunnelsWithoutHeight = roadsWithoutHeight.filter { tunnelFilter.matches(it) }

        val bridges = mapData.candidates(mapData.ways, bridgeFilter).filter { bridgeFilter.matches(it) }
        // the change: bridges by bounds (a bridge without geometry never matches, as in SC), and what SC
        // works out again for every road and bridge pair (the bridge's geometry, layer and node set) once
        // per bridge
        class Bridge(val geometry: ElementGeometry, val layer: Int, val nodeIds: Set<Long>)
        val bridgeGrid = BoundsGrid<Bridge>()
        for (bridge in bridges) {
            val geometry = mapData.getWayGeometry(bridge.id) ?: continue
            bridgeGrid.insert(geometry.bounds,
                Bridge(geometry, bridge.tags["layer"]?.toIntOrNull() ?: 0, bridge.nodeIds.toSet()))
        }

        val waysBelowBridgesWithoutHeight = roadsWithoutHeight.filter { way ->
            val layer = way.tags["layer"]?.toIntOrNull() ?: 0
            val geometry = mapData.getWayGeometry(way.id) as? ElementPolylinesGeometry

            // SC's order, plus the bounds test `intersects` starts with moved ahead of the node set
            geometry != null && bridgeGrid.query(geometry.bounds).any { bridge ->
                bridge.layer > layer
                    && bridge.geometry.bounds.intersect(geometry.bounds)
                    && !bridge.nodeIds.containsAny(way.nodeIds)
                    && bridge.geometry.intersects(geometry)
            }
        }

        return nodesWithoutHeight +
            railwayCrossingNodesWithoutHeight +
            tunnelsWithoutHeight +
            waysBelowBridgesWithoutHeight
    }
}
