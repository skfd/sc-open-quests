// COPIED by engine/port_area_quests.py from StreetComplete app/src/androidMain/kotlin/de/westnordost/streetcomplete/quests/ferry/FerryUtils.kt
// (sha256 of its LF text e2532e05bf95cf63bc0679fe26f077a2238b0e0fa256a4c33c53a17ddfcf8f2f, pinned in engine/PORTED-QUESTS.txt), unchanged below this header.
package de.westnordost.streetcomplete.quests.ferry

import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.data.osm.mapdata.Relation

/** Return all ids of ways that are part of any ferry route relation */
fun wayIdsInFerryRoutes(relations: Collection<Relation>): Set<Long> {
    val result = HashSet<Long>()
    for (relation in relations) {
        if (relation.tags["route"] != "ferry") continue
        for (member in relation.members) {
            if (member.type != ElementType.WAY) continue
            result.add(member.ref)
        }
    }
    return result
}
