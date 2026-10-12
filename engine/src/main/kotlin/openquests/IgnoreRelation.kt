package openquests

/**
 * Port of `ApplicationConstants.ignoreRelation()` from SC's commonMain `ApplicationConstants.kt`, copied
 * verbatim (pinned in engine/PORTED-QUESTS.txt as helper:ignoreRelation; the file cannot be vendored,
 * it also refers to BuildConfig and SplitWayAction).
 *
 * The app drops these relations while parsing a download (`MapDataApiParser`, via
 * `MapDataDownloader.getMap(bounds, ApplicationConstants::ignoreRelation)`), so no quest ever sees them:
 * neither as a quest's element nor as a member in a quest's surroundings. Both engine passes skip them.
 */
fun ignoreRelation(tags: Map<String, String>): Boolean {
    val type = tags["type"] ?: return false
    return when (type) {
        // ignore non ferry relations since these are sometimes/often very very large
        "route" -> tags["route"] != "ferry"
        "route_master", "superroute", "network", "disused:route" -> true

        // very large, not useful for SC
        "boundary" -> true
        // can easily span very large areas, not useful for SC
        "water", "waterway", "watershed", "collection" -> true
        // questionable relation type: members could easily span multiple continents
        "person" -> true
        // no wiki entry, sounds like it could span large areas
        "power", "pipeline", "railway" -> true
        else -> false
    }
}
