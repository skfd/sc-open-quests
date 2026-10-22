package openquests.custom

import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.data.osm.mapdata.Way

/** Port of SC quests/oneway/AddOnewayAerialway.kt.
 *  getApplicableElements = mapData.ways.filter { elementFilter.matches(it) } */
object AddOnewayAerialway : CustomQuest {
    override val name = "AddOnewayAerialway"
    override val elementTypes = setOf(ElementType.WAY)
    override val usesAge = false

    private val elementFilter by lazy { """
        ways with
          aerialway ~ gondola|mixed_lift|chair_lift|t-bar|j-bar|platter
          and !oneway
    """.toElementFilterExpression() }

    override fun isApplicable(element: Element): Boolean = element is Way && elementFilter.matches(element)
}
