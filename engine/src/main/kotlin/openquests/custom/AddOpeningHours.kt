package openquests.custom

import de.westnordost.osm_opening_hours.parser.toOpeningHoursOrNull
import de.westnordost.streetcomplete.data.elementfilter.filters.RelativeDate
import de.westnordost.streetcomplete.data.elementfilter.filters.TagOlderThan
import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.osm.opening_hours.isSupported

/** Port of SC quests/opening_hours/AddOpeningHours.kt. getApplicableElements = mapData.filter { isApplicableTo(it) } */
object AddOpeningHours : CustomQuest {
    override val name = "AddOpeningHours"
    override val elementTypes = setOf(ElementType.NODE, ElementType.WAY, ElementType.RELATION)
    override val usesAge = true

    // 'namedFilterFragment' is for places where 'AddPlaceName' should trigger first, so that object is identified if possible
    // Otherwise, in situation of two shops of the similar type with names A and B following may happen
    // (1) mapper answers for one object with opening hours for shop A
    // (2) this or different mapper may answer that it is named B
    // what would result in incorrect opening hours
    // this filter reduces risk of this happening and also makes this quest less confusing to answer
    private val namedFilterFragment = """
    (
        (
            shop and shop !~ no|vacant
            or amenity = social_facility and social_facility ~ food_bank|clothing_bank|soup_kitchen|dairy_kitchen
            or natural = cave_entrance and fee = yes
            or historic = castle and fee = yes
            or """ +

    // See also AddWheelchairAccessBusiness and AddPlaceName, which has a similar list and uses the
    // same order in the same way for better overview. When adding other tags to the common list
    // keep in mind that they need to be appropriate for all those quests.
    // Independent tags can be added above, or to 'unnamedFilter'.

mapOf(
    "amenity" to arrayOf(
        // common
        "restaurant", "cafe", "ice_cream", "fast_food", "bar", "pub", "biergarten",         // eat & drink
        "food_court", "nightclub", "hookah_lounge",
        "cinema", "planetarium", "casino",                                                  // amenities
        "townhall", "courthouse", "embassy", "community_centre", "youth_centre", "library",
        "ranger_station",                                                                   // civic
        "driving_school", "music_school", "prep_school", "language_school", "dive_centre",  // learning
        "dancing_school", "ski_school", "flight_school", "surf_school", "sailing_school",
        "cooking_school",
        "bank", "bureau_de_change", "money_transfer", "post_office", "marketplace",         // commercial
        "internet_cafe", "payment_centre",
        "car_wash", "car_rental", "fuel",                                                   // car stuff
        "dentist", "doctors", "clinic", "pharmacy", "veterinary", "veterinary_pharmacy",    // health
        "animal_boarding", "animal_shelter", "animal_breeding",                             // animals
        "coworking_space",                                                                  // work

        // name & opening hours
        "boat_rental", "vehicle_inspection", "motorcycle_rental", "crematorium",
        "public_bath", "traffic_park"

        // not ATM because too often it's simply 24/7 and too often it is confused with
        // a bank that might be just next door because the app does not tell the user what
        // kind of object this is about
    ),
    "tourism" to arrayOf(
        // common
        "zoo", "aquarium", "theme_park", "gallery", "museum"
        // and tourism = information, see above
    ),
    "leisure" to arrayOf(
        // common
        "fitness_centre", "golf_course", "water_park", "miniature_golf", "bowling_alley",
        "amusement_arcade", "adult_gaming_centre", "tanning_salon", "sauna",
        "indoor_play",

        // name & opening hours
        "trampoline_park",

        // not sports_centre, dance etc because these are often sports clubs which have no
        // walk-in opening hours but training times
    ),
    "office" to arrayOf(
        // common (AddPlaceName has catchall)
        "insurance", "government", "travel_agent", "tax_advisor", "religion",
        "employment_agency", "diplomatic", "coworking", "energy_supplier",
        "estate_agent", "lawyer", "telecommunication", "educational_institution",
        "association", "ngo", "it", "accountant", "property_management",
        "bail_bond_agent", "financial_advisor", "political_party",
        "private_investigator", "adoption_agency",
    ),
    "craft" to arrayOf(
        // common
        "carpenter", "shoemaker", "tailor", "photographer", "dressmaker",
        "electronics_repair", "key_cutter", "stonemason", "bookbinder",
        "jeweller", "sailmaker", "watchmaker", "clockmaker",
        "locksmith",  "window_construction", "signmaker", "upholsterer",
        "electrician", "boatbuilder",
    ),
    "healthcare" to arrayOf(
        // common
        "pharmacy", "doctor", "clinic", "dentist", "centre", "physiotherapist",
        "laboratory", "alternative", "psychotherapist", "optometrist", "podiatrist",
        "nurse", "counselling", "speech_therapist", "blood_donation", "sample_collection",
        "occupational_therapist", "dialysis", "vaccination_centre", "audiologist",
        "blood_bank", "nutrition_counselling",
    ),
    "waterway" to arrayOf(
        // name & opening hours
        "fuel",
    ),
).map { it.key + " ~ " + it.value.joinToString("|") }.joinToString("\n or ") + "\n" + """
    )
    and (!opening_hours or opening_hours older today -1 years)
    and (
        name
        or brand
        or noname = yes
        or name:signed = no
    ))
    """

    // 'unnamedFilterFragment' finds places are large or rare enough that a user should be able to identify them without a name.

    private val unnamedFilterFragment = """
    (
        (!opening_hours or opening_hours older today -1 years)
        and (
            amenity = bicycle_parking and bicycle_parking = building
            or amenity = parking and parking = multi-storey
            or amenity = recycling and recycling_type = centre
            or amenity = toilets and (fee = yes or toilets:disposal = flush)
            or amenity = shower and (fee = yes or indoor = yes or location = indoor)
            or tourism = information and information ~ office|visitor_centre
            or tower:type = observation and fee = yes
            or leisure = garden and fee = yes
            or leisure = park and fee = yes
        )
    )
    """

    // 'updateFilterFragment' is for places that often do not have (signed) 'opening_hours'. Thus, we only
    // ask for users to resurvey, and ignore places without tagged 'opening_hours'.

    private val updateFilterFragment = """
    (
        opening_hours older today -1 years
        and (
            leisure ~ park|garden|beach_resort|sports_centre|disc_golf_course|nature_reserve|playground|fitness_station
            or barrier
            or tourism = attraction
            or amenity ~ toilets|bicycle_rental|charging_station|place_of_worship|parking|research_institute|shower|grave_yard|kitchen|marketplace
            or railway = station
            or aeroway = terminal
            or man_made = observatory
            or club
            or building ~ civic|college|government|train_station|transportation|university
        )
    )
    """
    private val filter by lazy { """
        nodes, ways, relations with
          (
            $namedFilterFragment
            or $unnamedFilterFragment
            or $updateFilterFragment
          )
          and access !~ private|no
          and street_vendor != yes
          and opening_hours:signed != no
    """.toElementFilterExpression() }

    private val olderThan1Year = TagOlderThan("opening_hours", RelativeDate(-365f))

    override fun isApplicable(element: Element): Boolean {
        if (!filter.matches(element)) return false
        // no opening_hours yet -> new survey
        val ohStr = element.tags["opening_hours"] ?: return true
        /* don't show if it was recently checked (actually already checked by filter, but it is a
           performance improvement to avoid parsing the opening hours en masse if possible) */
        if (!olderThan1Year.matches(element)) return false
        // invalid opening_hours rules -> applicable because we want to ask for opening hours again
        // be strict
        val oh = ohStr.toOpeningHoursOrNull(lenient = false) ?: return true
        return oh.isSupported(allowTimePoints = false, allowAmbiguity = true)
    }
}
