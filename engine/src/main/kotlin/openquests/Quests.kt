package openquests

import de.westnordost.streetcomplete.data.elementfilter.ElementFilterExpression
import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.osm.BUILDINGS_WITH_LEVELS
import de.westnordost.streetcomplete.osm.surface.INVALID_SURFACES
import de.westnordost.streetcomplete.osm.surface.INVALID_SURFACES_FOR_TRACKTYPES
import de.westnordost.streetcomplete.osm.surface.PAVED_SURFACES
import de.westnordost.streetcomplete.osm.surface.UNPAVED_SURFACES

class SpikeQuest(val name: String, val elementFilter: String, val note: String = "") {
    val filter: ElementFilterExpression = elementFilter.toElementFilterExpression()
}

/*
 * Spike only: elementFilter strings copied verbatim from StreetComplete v63.4
 * (app/src/androidMain/kotlin/de/westnordost/streetcomplete/quests/<quest>/<Quest>.kt), including
 * the Kotlin string templates, so that the splicing of constants happens the same way as in the app.
 * The real pipeline should take the resolved strings from SC's quest registry instead.
 */

// private in AddWayLit's companion object (v63.4)
private val LIT_RESIDENTIAL_ROADS = arrayOf(
    "residential", "living_street", "pedestrian", "busway"
)
private val LIT_NON_RESIDENTIAL_ROADS = arrayOf(
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
    "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified", "service"
)
private val LIT_WAYS = arrayOf("footway", "cycleway", "steps")

// osm/maxspeed/MaxSpeedUtils.kt (v63.4), not vendored because it drags in osm/Ways etc.
private val MAX_SPEED_TYPE_KEYS = setOf(
    "source:maxspeed",
    "zone:maxspeed",
    "maxspeed:type",
    "zone:traffic",
    "maxspeed", // in Russia, Serbia, ...
)

val SPIKE_QUESTS = listOf(
    SpikeQuest("AddBenchBackrest", """
        nodes, ways with
          amenity = bench
          and (!area or area = no)
          and !backrest
          and !bench:type
          and (!seasonal or seasonal = no)
          and access !~ private|no
    """),
    SpikeQuest("AddBusStopShelter", """
        nodes, ways, relations with
        (
          public_transport = platform
          or (highway = bus_stop and public_transport != stop_position)
          or highway = hitchhiking
        )
        and physically_present != no and naptan:BusStopType != HAR
        and access !~ no|private
        and !covered
        and location !~ underground|indoor
        and indoor != yes
        and tunnel != yes
        and (!level or level >= 0)
        and (!shelter or shelter older today -4 years)
    """),
    SpikeQuest("AddBenchStatusOnBusStop", """
        nodes, ways, relations with
        (
          public_transport = platform
          or (highway = bus_stop and public_transport != stop_position)
          or highway = hitchhiking
        )
        and physically_present != no and naptan:BusStopType != HAR
        and access !~ no|private
        and (!bench or bench older today -4 years)
    """),
    SpikeQuest("AddRoadSurface", """
        ways with (
          highway ~ ${listOf(
            "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link",
            "unclassified", "residential", "living_street", "pedestrian", "track", "busway",
            ).joinToString("|")
          }
          or highway = service and service !~ driveway|slipway
        )
        and (
          !surface
          or surface ~ ${INVALID_SURFACES.joinToString("|")}
          or (
            surface ~ paved|unpaved
            and !surface:note
            and !note:surface
            and !check_date:surface
          )
          or surface ~ ${UNPAVED_SURFACES.joinToString("|")} and surface older today -6 years
          or surface older today -12 years
          ${INVALID_SURFACES_FOR_TRACKTYPES.entries.joinToString("\n") { (tracktype, surfaces) ->
              "or tracktype = $tracktype and surface ~ ${surfaces.joinToString("|")}"
          }}
        )
        and (access !~ private|no or (foot and foot !~ private|no))
        and ice_road != yes
    """),
    SpikeQuest("AddWayLit", """
        ways with
        (
          highway ~ ${LIT_RESIDENTIAL_ROADS.joinToString("|")}
          or highway ~ ${LIT_NON_RESIDENTIAL_ROADS.joinToString("|")} and
          (
            sidewalk ~ both|left|right|yes|separate
            or sidewalk:both = yes
            or sidewalk:left = yes
            or sidewalk:right = yes
            or ~"${MAX_SPEED_TYPE_KEYS.joinToString("|")}" ~ ".*:(urban|.*zone.*|nsl_restricted)"
            or maxspeed <= 60
          )
          or highway ~ ${LIT_WAYS.joinToString("|")}
          or highway = path and (foot = designated or bicycle = designated)
        )
        and
        (
          !lit
          or lit = no and lit older today -8 years
          or lit older today -16 years
        )
        and (access !~ private|no or (foot and foot !~ private|no))
        and indoor != yes
        and ~path|footway|cycleway !~ link
    """, note = "default-disabled in the app"),
    SpikeQuest("AddRecyclingType", "nodes, ways with amenity = recycling and !recycling_type"),
    SpikeQuest("AddBuildingLevels", """
        ways, relations with
           building ~ ${BUILDINGS_WITH_LEVELS.joinToString("|")}
           and (
             !building:levels
             or !roof:levels and !roof:height and roof:shape and roof:shape != flat
           )
           and !(height and roof:height)
           and !building:min_level
           and !man_made
           and location != underground
           and ruins != yes
    """, note = "default-disabled in the app"),
    SpikeQuest("AddFireHydrantType", "nodes with emergency = fire_hydrant and !fire_hydrant:type"),
    SpikeQuest("AddBikeParkingCapacity", """
        nodes, ways with
         amenity = bicycle_parking
         and access !~ private|no
         and bicycle_parking !~ floor|informal
         and (
           !capacity
           or (
             bicycle_parking ~ stands|wall_loops|safe_loops|handlebar_holder
             and capacity older today -8 years
           )
         )
    """),
    SpikeQuest("AddBikeParkingCover", """
        nodes, ways with
        (
            amenity = bicycle_parking
            or amenity = charging_station and bicycle ~ yes|designated and !lockable and motorcar=no
        )
        and access !~ private|no
        and !covered
        and bicycle_parking !~ shed|lockers|building
    """),
    SpikeQuest("AddHandrail", """
        ways with highway = steps
         and (!indoor or indoor = no)
         and access !~ private|no
         and (!conveying or conveying = no)
         and (
           !handrail and !handrail:center and !handrail:left and !handrail:right
           or handrail = no and handrail older today -4 years
           or handrail older today -8 years
           or older today -8 years
         )
    """),
    SpikeQuest("AddStepsRamp", """
        ways with highway = steps
         and (!indoor or indoor = no)
         and access !~ private|no
         and surface ~ ${PAVED_SURFACES.joinToString("|")}
         and !sac_scale
         and (!conveying or conveying = no)
         and ramp != separate
         and (
           !ramp
           or (ramp = yes and !ramp:stroller and !ramp:bicycle and !ramp:wheelchair)
           or ramp = no and ramp older today -4 years
           or ramp older today -8 years
         )
    """),
)
