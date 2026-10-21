// COPIED by engine/port_area_quests.py from StreetComplete app/src/commonMain/kotlin/de/westnordost/streetcomplete/quests/max_height/MaxHeightUtils.kt
// (sha256 of its LF text 23204371a4f5bdebaf8fa366b33abae29455b79aea595f4f575346645a3997b7, pinned in engine/PORTED-QUESTS.txt), unchanged below this header.
package de.westnordost.streetcomplete.quests.max_height

import de.westnordost.streetcomplete.data.elementfilter.ElementFilterExpression
import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.geometry.ElementPolylinesGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.MapDataWithGeometry
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import de.westnordost.streetcomplete.data.osm.mapdata.filter
import de.westnordost.streetcomplete.osm.ALL_PATHS
import de.westnordost.streetcomplete.osm.ALL_ROADS
import de.westnordost.streetcomplete.util.math.intersects

/** Returns ways that intersect with and are bridges above this way */
fun Way.getIntersectingBridges(mapData: MapDataWithGeometry): Sequence<Way> {
    val geometry = mapData.getWayGeometry(id) as? ElementPolylinesGeometry ?: return emptySequence()
    val ways = mapData.filter(bridgeFilter).filterIsInstance<Way>()

    val layer = tags["layer"]?.toIntOrNull() ?: 0

    return ways
        .filter { (it.tags["layer"]?.toIntOrNull() ?: 0) > layer }
        .filter { mapData.getWayGeometry(it.id)?.intersects(geometry) == true }
}

val tunnelFilter: ElementFilterExpression by lazy { """
    ways with
      highway
      and (
        covered = yes
        or tunnel ~ yes|building_passage|avalanche_protector
        or bridge = covered
      )
""".toElementFilterExpression() }

val bridgeFilter by lazy { """
    ways with
      (
        (
          highway ~ ${(ALL_ROADS + ALL_PATHS).joinToString("|")}
          or railway ~ rail|light_rail|subway|narrow_gauge|tram|disused|preserved|funicular|monorail
        )
        and bridge and bridge != no
      ) or (
        building = roof
        or man_made = pipeline and location = overhead
      )
      and layer
""".toElementFilterExpression() }
