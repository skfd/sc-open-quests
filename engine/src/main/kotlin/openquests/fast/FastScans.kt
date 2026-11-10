package openquests.fast

import de.westnordost.osmfeatures.Feature
import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.geometry.ElementPolygonsGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.MapDataWithGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import de.westnordost.streetcomplete.osm.LAST_CHECK_DATE_KEYS
import de.westnordost.streetcomplete.osm.getLastCheckDateKeys
import de.westnordost.streetcomplete.quests.socket.ChargingStationSocket
import de.westnordost.streetcomplete.quests.socket.INVALID_CHARGING_STATION_SOCKETS
import de.westnordost.streetcomplete.util.math.contains
import de.westnordost.streetcomplete.util.math.isInMultipolygon
import openquests.candidates
import openquests.custom.ScFeatures

/*
 * Twins of the age quests whose only cost was walking every element of the map data, four times each (a
 * cell of 15M nodes: 3-4 s of CPU a walk). The one change in each: a scan asks for its filter's candidates
 * by key first (KeyIndex.kt), which leaves out only elements the filter cannot match, in the same order.
 * Filters and helpers copied verbatim.
 */

/**
 * SC's CheckExistence.getApplicableElements (ported/.../CheckExistence.kt): `mapData.filter { isApplicableTo(it) }`,
 * and `isApplicableTo` starts with `nodesFilter.matches`, so only the nodes that can match it are asked.
 */
object FastCheckExistence : FastTwin {
    override val name = "CheckExistence"
    override val usesAge = true
    override val sourceSha256 = "52a807efa435381e01cefceea92329acb6969ae5daac786f3a69dbf28a5bcc13"

    private val getFeature: (Element) -> Feature? = ScFeatures::getFeature

    private val nodesFilter by lazy { """
        nodes with
          ((
            (
              amenity ~ atm|telephone|parcel_locker|public_bookcase|give_box
              or amenity = vending_machine and vending !~ fuel|parking_tickets|public_transport_tickets
              or barrier = log
            )
            and (${lastChecked(2.0)})
          ) or (
            (
              amenity ~ clock|post_box|bbq|car_sharing|ticket_validator|bicycle_repair_station
              or leisure ~ firepit|fitness_station|picnic_table
              or (leisure = pitch and sport ~ table_tennis|chess|table_soccer|teqball)
              or amenity = grit_bin and seasonal = no
              or amenity = vending_machine and vending ~ parking_tickets|public_transport_tickets
              or tourism = information and information ~ board|terminal|map
              or advertising ~ column|board|poster_box
              or (highway = emergency_access_point or emergency = access_point) and ref
              or emergency ~ life_ring|phone
              or emergency = defibrillator and (indoor = no or access = yes)
              or (
                man_made = surveillance
                and surveillance:type = camera
                and surveillance ~ outdoor|public
                and !highway
              )
            )
            and (${lastChecked(4.0)})
          ) or (
            (
              amenity ~ bench|lounger|waste_basket|toilets|shower|drinking_water
              or amenity = recycling and recycling_type = container
              or man_made = planter
            )
            and (${lastChecked(6.0)})
          ) or (
            amenity ~ bicycle_parking|motorcycle_parking|taxi|shelter
            and (${lastChecked(10.0)})
          ) or (
            (
              traffic_calming ~ bump|mini_bumps|hump|cushion|rumble_strip|dip|double_dip
              or traffic_calming = table and !highway and !crossing
            )
            and (${lastChecked(14.0)})
          ))
          and access !~ no|private
          and (!seasonal or seasonal = no)
          and (!intermittent or intermittent = no)
          and (!permanent or permanent != yes)
          and (!heritage or heritage = no)
          and !listed_status
    """.toElementFilterExpression() }

    // the change: SC walks the whole map data
    override fun getApplicableElements(mapData: MapDataWithGeometry): Iterable<Element> =
        mapData.candidates(mapData.nodes, nodesFilter).filter { isApplicableTo(it) }

    private fun lastChecked(yearsAgo: Double): String = """
        older today -$yearsAgo years
        or ${LAST_CHECK_DATE_KEYS.joinToString(" or ") { "$it < today -$yearsAgo years" }}
    """.trimIndent()

    fun isApplicableTo(element: Element) =
        nodesFilter.matches(element) && getFeature(element) != null
}

/**
 * SC's AddChargingStationSocket.getApplicableElements (ported/.../AddChargingStationSocket.kt). Its two
 * scans, `mapData.filter("nodes with man_made = charge_point")` and `mapData.filter(filter)`, walk the
 * candidates of each filter; SC's `filter(expr)` yields the nodes, then the ways, then the relations the
 * expression includes, which is the order [candidates] keeps.
 */
object FastAddChargingStationSocket : FastTwin {
    override val name = "AddChargingStationSocket"
    override val usesAge = true
    override val sourceSha256 = "7922f3199005aa41078397355bbebfffc6da6cc035467d81ef13befae801c446"

    private val filter by lazy { """
        nodes, ways with
          amenity = charging_station
          and motorcar != no
          and motor_vehicle != no
          and lockable != yes
          and (
            !~"socket:(${ChargingStationSocket.entries.joinToString("|") { it.osmId }})"
            or ~"socket:(${ChargingStationSocket.entries.joinToString("|") { it.osmId }})" ~ "yes"
            or ~"socket:(${INVALID_CHARGING_STATION_SOCKETS.joinToString("|")})"
            or ${getLastCheckDateKeys("socket").joinToString(" or ") { "$it < today -2 years" }}
          )
          and access !~ no|private
    """.toElementFilterExpression() }

    private val chargePointFilter by lazy { "nodes with man_made = charge_point".toElementFilterExpression() }

    override fun getApplicableElements(mapData: MapDataWithGeometry): Iterable<Element> {
        // Individual charge points are nodes per OSM wiki; not quested yet (follow-up).
        val chargePointCenters = mapData
            .candidates(mapData.nodes, chargePointFilter).filter { chargePointFilter.matches(it) } // the change
            .mapNotNull { (it as? Node)?.position }
            .toList()

        return mapData
            .candidates(filter).filter { filter.matches(it) } // the change
            .filter { !it.containsMappedChargePoints(mapData, chargePointCenters)
        }.toList()
    }

    private fun Element.containsMappedChargePoints(
        mapData: MapDataWithGeometry,
        chargePointCenters: List<LatLon>
    ): Boolean {
        if (this !is Way || chargePointCenters.isEmpty()) return false
        val geometry = mapData.getGeometry(type, id) as? ElementPolygonsGeometry ?: return false
        return chargePointCenters.any { pos ->
            geometry.bounds.contains(pos) && pos.isInMultipolygon(geometry.polygons)
        }
    }
}
