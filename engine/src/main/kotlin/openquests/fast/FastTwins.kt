package openquests.fast

import de.westnordost.streetcomplete.data.osm.mapdata.BoundingBox
import openquests.custom.AreaQuest
import kotlin.math.floor

/**
 * A faster copy of a ported area quest, for the per-city unit: the same result as SC's code on any map
 * data, with one change that only skips work SC's code would discard. [sourceSha256] is the pin of
 * the SC file it copies (engine/PORTED-QUESTS.txt); a test fails when SC's file moves on, and
 * `-Dopenquests.verifyFast=true` runs the original next to it and fails on any difference.
 */
interface FastTwin : AreaQuest {
    val sourceSha256: String
}

/** Fast twins by quest name; AreaPass uses them instead of the port of the same name. */
val FAST_TWINS: Map<String, FastTwin> = listOf<FastTwin>(
    FastAddMaxHeight,
    FastAddHousenumber,
    FastAddIsAmenityIndoor,
).associateBy { it.name }

/** Grid over bounding boxes: [query] returns every value whose box intersects the given one
 *  (inclusive edges, as SC's BoundingBox.intersect), and maybe others. */
class BoundsGrid<T>(private val cellDegrees: Double = 0.005) {
    private val cells = HashMap<Long, MutableList<T>>()

    private fun cell(d: Double) = floor(d / cellDegrees).toInt()
    private fun key(x: Int, y: Int) = (x.toLong() shl 32) or (y.toLong() and 0xffffffffL)

    fun insert(b: BoundingBox, value: T) {
        for (x in cell(b.min.longitude)..cell(b.max.longitude)) for (y in cell(b.min.latitude)..cell(b.max.latitude)) {
            cells.getOrPut(key(x, y)) { ArrayList(2) }.add(value)
        }
    }

    fun query(b: BoundingBox): Set<T> {
        val out = LinkedHashSet<T>()
        for (x in cell(b.min.longitude)..cell(b.max.longitude)) for (y in cell(b.min.latitude)..cell(b.max.latitude)) {
            cells[key(x, y)]?.let { out.addAll(it) }
        }
        return out
    }
}
