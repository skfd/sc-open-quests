package openquests.custom

import de.westnordost.osmfeatures.Feature
import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType

/** Port of SC quests/place_name/AddPlaceName.kt. getApplicableElements = mapData.filter { isApplicableTo(it) } */
object AddPlaceName : CustomQuest {
    override val name = "AddPlaceName"
    override val elementTypes = setOf(ElementType.NODE, ElementType.WAY)
    override val usesAge = false

    private val getFeature: (Element) -> Feature? = ScFeatures::getFeature

    private val filter by lazy { ("""
        nodes, ways with
        (
          shop and shop !~ no|vacant
          or office and office !~ no|vacant
          or craft
          or amenity = recycling and recycling_type = centre
          or amenity = shelter and shelter_type = basic_hut
          or tourism = information and information ~ office|visitor_centre
          or natural = cave_entrance and fee = yes
          or """ +

        // The common list is shared by the opening hours quest and the wheelchair quest.
        // It is also mostly shared by the name quest, that has some wildcards (for say craft and office)
        // So when adding other tags to the common list keep in mind that they need to be appropriate for all those quests.
        // Independent tags can be added in the "name only" tab.

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
                "public_bath", "traffic_park",

                // name & wheelchair
                "theatre",                                        // culture
                "conference_centre", "arts_centre",               // events
                "police",                                         // civic
                "ferry_terminal",                                 // transport
                "place_of_worship",                               // religious
                "hospital",                                       // health care
                "brothel", "gambling", "love_hotel", "stripclub", // bad stuff

                // name only
                "studio",                                                                // culture
                "events_venue", "exhibition_centre", "music_venue", "funeral_hall",      // events
                "prison", "fire_station", "bus_station", "refugee_site",                 // civic
                "social_facility", "nursing_home", "childcare", "retirement_home", "social_centre", // social
                "monastery",                                                             // religious
                "kindergarten", "school", "college", "university", "research_institute", // education
                "dojo",                                                                  // sport
            ),
            "tourism" to arrayOf(
                // common
                "zoo", "aquarium", "theme_park", "gallery", "museum",

                // name & wheelchair
                "attraction",
                "hotel", "guest_house", "motel", "hostel", "alpine_hut", "apartment", "resort", "camp_site", "caravan_site", "chalet", // accommodations

                // name only
                "wilderness_hut"

                // and tourism = information, see above
            ),
            "leisure" to arrayOf(
                // common
                "fitness_centre", "golf_course", "water_park", "miniature_golf", "bowling_alley",
                "amusement_arcade", "adult_gaming_centre", "tanning_salon", "sauna",
                "indoor_play",

                // name & wheelchair
                "sports_centre", "stadium",

                // name & opening hours
                "trampoline_park",

                // name only
                "dance", "nature_reserve", "marina", "horse_riding",
                "bathing_place", "escape_game", "beach_resort", "summer_camp", "marina"
            ),
            "landuse" to arrayOf(
                "cemetery", "allotments"
            ),
            "military" to arrayOf(
                "airfield", "barracks", "training_area", "base",
            ),
            "healthcare" to arrayOf(
                // common
                "pharmacy", "doctor", "clinic", "dentist", "centre", "physiotherapist",
                "laboratory", "alternative", "psychotherapist", "optometrist", "podiatrist",
                "nurse", "counselling", "speech_therapist", "blood_donation", "sample_collection",
                "occupational_therapist", "dialysis", "vaccination_centre", "audiologist",
                "blood_bank", "nutrition_counselling",

                // name & wheelchair
                "rehabilitation", "hospice", "midwife", "birthing_centre"
            ),
            "historic" to arrayOf(
                // name only
                "castle", "church", "farm", "fort", "manor", "monument", "mosque", "temple",
                "ship",
            ),
            "waterway" to arrayOf(
                // name & opening hours
                "fuel",
            ),
        ).map { it.key + " ~ " + it.value.joinToString("|") }.joinToString("\n  or ") + "\n" + """
        )
        and (
            (
                !name
                and !brand
                and noname != yes
            )
            or ~fixme|FIXME ~ name|name\?|Name|Name\?
        )
        and name:signed != no
    """).toElementFilterExpression() }

    override fun isApplicable(element: Element): Boolean =
        filter.matches(element) && getFeature(element) != null
}
