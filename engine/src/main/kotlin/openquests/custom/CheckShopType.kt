package openquests.custom

import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.osm.LAST_CHECK_DATE_KEYS
import de.westnordost.streetcomplete.osm.places.isDisusedPlace
import de.westnordost.streetcomplete.osm.places.isPlace

/** Port of SC quests/shop_type/CheckShopType.kt. getApplicableElements = mapData.filter { isApplicableTo(it) } */
object CheckShopType : CustomQuest {
    override val name = "CheckShopType"
    override val elementTypes = setOf(ElementType.NODE, ElementType.WAY)
    override val usesAge = true

    private val filter by lazy { """
        nodes, ways with
          !man_made
          and !historic
          and !military
          and !power
          and !tourism
          and !attraction
          and !amenity
          and !leisure
          and !aeroway
          and !railway
          and !craft
          and !healthcare
          and (!office or office = vacant)
          and (!shop or shop = vacant)
          and (
            older today -1 years
            or ${LAST_CHECK_DATE_KEYS.joinToString(" or ") { "$it < today -1 years" }}
          )
    """.toElementFilterExpression() }

    override fun isApplicable(element: Element): Boolean =
        element.isDisusedPlace() &&
        filter.matches(element) &&
        /* elements tagged like "shop=ice_cream + disused:amenity=bank" should not appear as quests.
         *  This is arguably a tagging mistake, but that mistake should not lead to all the tags of
         *  this element being cleared when the quest is answered */
        !element.isPlace()
}
