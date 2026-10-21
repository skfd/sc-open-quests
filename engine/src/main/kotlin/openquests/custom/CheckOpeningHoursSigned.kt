package openquests.custom

import de.westnordost.osmfeatures.Feature
import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.osm.getLastCheckDateKeys

/** Port of SC quests/opening_hours_signed/CheckOpeningHoursSigned.kt.
 *  getApplicableElements = mapData.filter { isApplicableTo(it) } */
object CheckOpeningHoursSigned : CustomQuest {
    override val name = "CheckOpeningHoursSigned"
    override val elementTypes = setOf(ElementType.NODE, ElementType.WAY, ElementType.RELATION)
    override val usesAge = true

    private val getFeature: (Element) -> Feature? = ScFeatures::getFeature

    private val filter by lazy { """
        nodes, ways, relations with
          opening_hours:signed = no
          and (
            $hasOldOpeningHoursCheckDateFilter
            or older today -2 years
          )
          and access !~ private|no
          and (
            name or brand or noname = yes or name:signed = no
            or amenity ~ recycling|toilets|bicycle_rental|charging_station or leisure = park or barrier
          )
    """.toElementFilterExpression() }

    private val hasOldOpeningHoursCheckDateFilter: String get() =
        getLastCheckDateKeys("opening_hours").joinToString("\nor ") {
            "$it < today -2 years"
        }

    override fun isApplicable(element: Element): Boolean =
        filter.matches(element) && hasName(element)

    private fun hasName(element: Element) = hasProperName(element.tags) || hasFeatureName(element)

    private fun hasProperName(tags: Map<String, String>): Boolean =
        tags.containsKey("name") || tags.containsKey("brand")

    private fun hasFeatureName(element: Element) = getFeature(element)?.name != null
}
