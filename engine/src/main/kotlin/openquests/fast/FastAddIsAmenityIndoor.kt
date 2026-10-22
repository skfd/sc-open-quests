package openquests.fast

import de.westnordost.osmfeatures.Feature
import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.geometry.ElementPolygonsGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.BoundingBox
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.MapDataWithGeometry
import de.westnordost.streetcomplete.util.math.LatLonRaster
import de.westnordost.streetcomplete.util.math.contains
import de.westnordost.streetcomplete.util.math.isCompletelyInside
import de.westnordost.streetcomplete.util.math.isInMultipolygon
import openquests.custom.ScFeatures

/**
 * SC's AddIsAmenityIndoor.getApplicableElements (ported/.../AddIsAmenityIndoor.kt), with one change:
 * a node is checked against the buildings from a [BoundsGrid] whose bounds can hold it, instead of
 * every building. SC's check is false for a building whose bounds do not contain the node, so the
 * result is the same. Filters copied verbatim.
 */
object FastAddIsAmenityIndoor : FastTwin {
    override val name = "AddIsAmenityIndoor"
    override val usesAge = false
    override val sourceSha256 = "c427676015f721f598738468f1dc3de82f7632c93fc113dfb47de3e8962484ec"

    private val getFeature: (Element) -> Feature? = ScFeatures::getFeature

    private val nodesFilter by lazy { """
        nodes with
          (
            emergency ~ defibrillator|fire_extinguisher|fire_hose|first_aid_kit
            or amenity ~ atm|bicycle_repair_station|drinking_water|telephone|parcel_locker|library_dropoff|luggage_locker|locker|post_box|public_bookcase|give_box|ticket_validator|shower|vending_machine
            or amenity = clock and display != sundial
          )
          and access !~ private|no
          and !indoor and !location and !level and !level:ref
          and covered != yes
    """.toElementFilterExpression() }

    private val nodesOnWalls by lazy { """
        nodes with
          emergency ~ defibrillator|fire_extinguisher|fire_hose
    """.toElementFilterExpression() }

    private val buildingFilter by lazy { """
        ways, relations with
          building and building != roof
    """.toElementFilterExpression() }

    override fun getApplicableElements(mapData: MapDataWithGeometry): Iterable<Element> {
        val bbox = mapData.boundingBox ?: return listOf()
        val nodes = mapData.nodes.filter { nodesFilter.matches(it) && getFeature(it) != null }
        val buildings = mapData.filter { buildingFilter.matches(it) }.toMutableList()

        val buildingGeometriesById = buildings.associate {
            it.id to mapData.getGeometry(it.type, it.id) as? ElementPolygonsGeometry
        }

        val nodesPositions = LatLonRaster(bbox, 0.0005)
        for (node in nodes) {
            nodesPositions.insert(node.position)
        }

        buildings.removeAll { building ->
            val buildingBounds = buildingGeometriesById[building.id]?.bounds
            (buildingBounds == null || !buildingBounds.isCompletelyInside(bbox) || nodesPositions.getAll(buildingBounds).count() == 0)
        }

        // the change: the remaining buildings by bounds
        val buildingGrid = BoundsGrid<Element>()
        for (building in buildings) {
            buildingGeometriesById[building.id]?.let { buildingGrid.insert(it.bounds, building) }
        }

        val result = nodes.filter {
            nodesOnWalls.matches(it) ||
            buildingGrid.query(BoundingBox(it.position, it.position)).any { building ->
                val buildingGeometry = buildingGeometriesById[building.id]

                if (buildingGeometry != null && buildingGeometry.bounds.contains(it.position)) {
                    it.position.isInMultipolygon(buildingGeometry.polygons)
                } else {
                    false
                }
            }
        }

        return result
    }
}
