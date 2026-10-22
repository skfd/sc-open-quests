package openquests.custom

import de.westnordost.osmfeatures.Feature
import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.osm.LAST_CHECK_DATE_KEYS
import de.westnordost.streetcomplete.osm.places.isPlace

/** Port of SC quests/shop_type/CheckShopExistence.kt. getApplicableElements = mapData.filter { isApplicableTo(it) } */
object CheckShopExistence : CustomQuest {
    override val name = "CheckShopExistence"
    override val elementTypes = setOf(ElementType.NODE, ElementType.WAY)
    override val usesAge = true

    private val getFeature: (Element) -> Feature? = ScFeatures::getFeature

    // opening hours quest acts as a de facto checker of shop existence, but some people disabled it.
    // separate from CheckExistence as very old shop with opening hours should show
    // opening hours resurvey quest rather than this one (which would cause edit date to be changed
    // and silence all resurvey quests)
    private val filter by lazy { ("""
        nodes, ways with
          !man_made
          and !historic
          and !military
          and !power
          and !attraction
          and !aeroway
          and !railway
          and (
            older today -2 years
            or ${LAST_CHECK_DATE_KEYS.joinToString(" or ") { "$it < today -2 years" }}
          )
    """).toElementFilterExpression() }

    // Apply 'filter' last since it will check the age of almost every element (very slow)
    override fun isApplicable(element: Element): Boolean =
        element.isPlace() &&
        hasName(element) &&
        filter.matches(element)

    private fun hasName(element: Element) = hasProperName(element.tags) || hasFeatureName(element)

    private fun hasProperName(tags: Map<String, String>): Boolean =
        tags.containsKey("name") || tags.containsKey("brand")

    private fun hasFeatureName(element: Element) = getFeature(element)?.name != null
}
