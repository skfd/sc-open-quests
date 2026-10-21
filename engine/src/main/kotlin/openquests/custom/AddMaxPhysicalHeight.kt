package openquests.custom

import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import de.westnordost.streetcomplete.osm.ALL_ROADS
import de.westnordost.streetcomplete.osm.MOTORWAYS

/** Port of SC quests/max_height/AddMaxPhysicalHeight.kt. getApplicableElements =
 *  mapData.nodes.filter { nodeFilter.matches(it) } + mapData.ways.filter { wayFilter.matches(it) } */
object AddMaxPhysicalHeight : CustomQuest {
    override val name = "AddMaxPhysicalHeight"
    override val elementTypes = setOf(ElementType.NODE, ElementType.WAY)
    override val usesAge = false

    private val nodeFilter by lazy { """
        nodes with
          (
            barrier = height_restrictor
            or amenity = parking_entrance and parking ~ underground|multi-storey
          )
          and (
            maxheight = below_default
            or source:maxheight ~ ".*estimat.*"
            or maxheight:signed = no and !maxheight
          )
          and maxheight != default
          and !maxheight:physical
          and access !~ private|no
          and vehicle !~ private|no
    """.toElementFilterExpression() }

    private val wayFilter by lazy { """
        ways with
          highway ~ ${(ALL_ROADS - MOTORWAYS).joinToString("|")}
          and (
            maxheight = below_default
            or source:maxheight ~ ".*estimat.*"
            or maxheight:signed = no and !maxheight
          )
          and maxheight != default
          and !maxheight:physical
          and access !~ private|no
          and vehicle !~ private|no
          and motorroad != yes
          and motorway != yes
          and expressway != yes
    """.toElementFilterExpression() }

    override fun isApplicable(element: Element): Boolean =
        element is Node && nodeFilter.matches(element) || element is Way && wayFilter.matches(element)
}
