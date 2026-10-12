package openquests.fast

import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.geometry.ElementPolylinesGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.MapDataWithGeometry
import de.westnordost.streetcomplete.osm.ALL_PATHS
import de.westnordost.streetcomplete.osm.ALL_ROADS
import de.westnordost.streetcomplete.quests.max_height.bridgeFilter
import de.westnordost.streetcomplete.quests.max_height.tunnelFilter
import de.westnordost.streetcomplete.util.ktx.containsAny
import de.westnordost.streetcomplete.util.math.intersects
/**
 * SC's AddMaxHeight.getApplicableElements (ported/.../AddMaxHeight.kt), with one change: the bridges
 * a road is checked against come from a [BoundsGrid] instead of the whole list. SC's `intersects`
 * returns false when the bounds do not intersect, so the result is the same; on a whole city the
 * original compares every road with every bridge. Filters copied verbatim.
 */
object FastAddMaxHeight : FastTwin {
    override val name = "AddMaxHeight"
    override val usesAge = false
    override val sourceSha256 = "df2647c98340fd2f0386b672be78e6be6deae69c939016ec68296d57ff861c10"

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
        val roadsNodeIds = mapData.ways
            .filter { allRoadsFilter.matches(it) }
            .flatMapTo(HashSet()) { it.nodeIds }

        val pathNodeIds = mapData.ways
            .filter { allPathsFilter.matches(it) }
            .flatMapTo(HashSet()) { it.nodeIds }

        val nodesWithoutHeight = mapData.nodes
            .filter { it.id in roadsNodeIds && nodeFilter.matches(it) }

        val electrifiedRailwayNodeIds = mapData.ways
            .filter { electrifiedRailwaysFilter.matches(it) }
            .flatMapTo(HashSet()) { it.nodeIds }

        val railwayCrossingNodesWithoutHeight = mapData.nodes
            .filter {
                (it.id in roadsNodeIds || it.id in pathNodeIds)
                && it.id in electrifiedRailwayNodeIds
                && railwayCrossingsFilter.matches(it)
            }

        val roadsWithoutHeight = mapData.ways.filter { roadsWithoutMaxHeightFilter.matches(it) }

        val tunnelsWithoutHeight = roadsWithoutHeight.filter { tunnelFilter.matches(it) }

        val bridges = mapData.ways.filter { bridgeFilter.matches(it) }
        // the change: bridges by bounds (a bridge without geometry never matches, as in SC)
        val bridgeGrid = BoundsGrid<Int>()
        for ((i, bridge) in bridges.withIndex()) {
            mapData.getWayGeometry(bridge.id)?.let { bridgeGrid.insert(it.bounds, i) }
        }

        val waysBelowBridgesWithoutHeight = roadsWithoutHeight.filter { way ->
            val layer = way.tags["layer"]?.toIntOrNull() ?: 0
            val geometry = mapData.getWayGeometry(way.id) as? ElementPolylinesGeometry

            geometry != null && bridgeGrid.query(geometry.bounds).any { i ->
                val bridge = bridges[i]
                val bridgeGeometry = mapData.getWayGeometry(bridge.id)
                val bridgeLayer = bridge.tags["layer"]?.toIntOrNull() ?: 0

                bridgeLayer > layer
                    && !bridge.nodeIds.toSet().containsAny(way.nodeIds)
                    && bridgeGeometry != null && bridgeGeometry.intersects(geometry)
            }
        }

        return nodesWithoutHeight +
            railwayCrossingNodesWithoutHeight +
            tunnelsWithoutHeight +
            waysBelowBridgesWithoutHeight
    }
}
