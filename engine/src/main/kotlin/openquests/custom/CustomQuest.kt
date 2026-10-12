package openquests.custom

import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType

/**
 * A custom StreetComplete quest (an `OsmElementQuestType` that is not an `OsmFilterQuestType`) whose
 * applicability is decided by the element's own tags, ported from SC's androidMain.
 *
 * SC keeps these quests next to their Android forms, so they cannot be vendored as they are. Each port
 * copies the quest's filter strings and `isApplicableTo()` verbatim and calls the vendored SC helpers
 * they use; [isApplicable] is what the quest's `getApplicableElements(mapData)` keeps, since that is
 * what the app runs on downloaded data (`OsmQuestController`). The upstream file of each port is pinned
 * in `engine/PORTED-QUESTS.txt`; `sync-sc.ps1` fails when one changed.
 *
 * Only quests whose `getApplicableElements()` looks at one element at a time belong here (some also
 * ask SC's feature dictionary, see [ScFeatures]). Quests that need the surrounding map data
 * (crossings, kerbs, housenumbers...) do not.
 */
interface CustomQuest {
    /** SC's quest type name, as in the registry dump */
    val name: String
    /** the element types `getApplicableElements()` can return */
    val elementTypes: Set<ElementType>
    /** whether the logic reads the clock (`older`, `today`, `TagOlderThan`); see agedOnly */
    val usesAge: Boolean
    fun isApplicable(element: Element): Boolean
}

/** Every ported custom quest, by name. Must list the same quests as PORTED-QUESTS.txt. */
val CUSTOM_QUESTS: Map<String, CustomQuest> = listOf(
    AddSidewalk,
    AddOpeningHours,
    AddPostboxCollectionTimes,
    AddRecyclingContainerMaterials,
    CheckShopType,
    AddClothingBinOperator,
    AddOnewayAerialway,
    AddRoadWidth,
    AddMaxPhysicalHeight,
    // these also ask SC's feature dictionary (ScFeatures)
    CheckShopExistence,
    CheckOpeningHoursSigned,
    AddPlaceName,
).associateBy { it.name }
