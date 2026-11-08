package openquests.fast

import de.westnordost.streetcomplete.data.osm.mapdata.BoundingBox
import de.westnordost.streetcomplete.data.osm.mapdata.MapDataWithGeometry
import openquests.ArrayMapData
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

    /** Pins of the SC helper files it copies too, by their PORTED-QUESTS.txt name (`helper:...`). */
    val helperSha256: Map<String, String> get() = emptyMap()

    /** Searches this twin shares with others on the same map data. AreaPass runs them first, next to the
     *  quests that need none, so no thread waits on one. */
    val shared: List<PerMapData<*>> get() = emptyList()
}

/** Fast twins by quest name; AreaPass uses them instead of the port of the same name. */
val FAST_TWINS: Map<String, FastTwin> = listOf<FastTwin>(
    FastAddMaxHeight,
    FastAddHousenumber,
    FastAddIsAmenityIndoor,
    FastAddAddressStreet,
    FastAddKerbHeight,
    FastAddTactilePavingKerb,
    FastAddLevel,
    FastAddLevelThing,
).associateBy { it.name }

/** A search that reads no clock, done once per map data however many quests and runs ask for it: the
 *  first to ask computes it, the others wait for that result. Kept for [ArrayMapData] only, which cannot
 *  change and is equal only to itself (SC's MutableMapDataWithGeometry can, and compares by content), weakly,
 *  so a city's map data is not kept past its pass. */
class PerMapData<T>(val name: String, private val compute: (MapDataWithGeometry) -> T) {
    private val results = java.util.Collections.synchronizedMap(java.util.WeakHashMap<ArrayMapData, Lazy<T>>())

    fun of(mapData: MapDataWithGeometry): T =
        if (mapData !is ArrayMapData) compute(mapData)
        else results.computeIfAbsent(mapData) { lazy { compute(mapData) } }.value
}

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
