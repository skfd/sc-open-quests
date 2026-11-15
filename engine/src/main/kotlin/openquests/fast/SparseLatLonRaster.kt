package openquests.fast

import de.westnordost.streetcomplete.data.osm.mapdata.BoundingBox
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.util.math.normalizeLongitude
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min

/**
 * SC's `LatLonRaster` (util/math/LatLonRaster.kt) with the same squares and the same answers, holding only
 * the squares that have a point. SC's keeps a slot per square of the box: for a world cell of 8 by 7
 * degrees at 0.0005 that is an array of 240M references, 1 GB, of which a few hundred thousand are used,
 * three times per city (AddHousenumber twice, AddIsAmenityIndoor), and the collector has to walk each one
 * (DESIGN.md, "Batch engine speed-up"). The squares start at the box's corner as SC's do, [insert] drops a
 * point outside them as SC's does, and [getAll] gives the points of the squares a box touches row by row,
 * west to east, each square's in the order they were inserted: SC's order.
 */
class SparseLatLonRaster(bounds: BoundingBox, private val cellSize: Double) {
    private val rasterWidth: Int
    private val rasterHeight: Int
    private val bbox: BoundingBox
    var size = 0
        private set

    // open addressing: keys[s] is a square's index + 1 (0: free), lists[s] its points
    private var keys = LongArray(1 shl 12)
    private var lists = arrayOfNulls<ArrayList<LatLon>>(1 shl 12)
    private var used = 0
    /** the used squares' indices ascending, made when a wide [getAll] first asks after an insert */
    private var sorted: LongArray? = null

    init {
        val lonDiff = normalizeLongitude(bounds.max.longitude - bounds.min.longitude)
        val latDiff = bounds.max.latitude - bounds.min.latitude
        rasterWidth = ceil(lonDiff / cellSize).toInt()
        rasterHeight = ceil(latDiff / cellSize).toInt()
        val maxLon = normalizeLongitude(bounds.min.longitude + rasterWidth * cellSize)
        val maxLat = bounds.min.latitude + rasterHeight * cellSize
        bbox = BoundingBox(bounds.min, LatLon(maxLat, maxLon))
    }

    private fun slotOf(key: Long): Int {
        val mask = keys.size - 1
        var s = ((key * -7046029254386353131L) ushr 32).toInt() and mask
        while (keys[s] != 0L && keys[s] != key + 1) s = (s + 1) and mask
        return s
    }

    private fun grow() {
        val oldKeys = keys; val oldLists = lists
        keys = LongArray(oldKeys.size * 2)
        lists = arrayOfNulls(oldKeys.size * 2)
        for (i in oldKeys.indices) if (oldKeys[i] != 0L) {
            val s = slotOf(oldKeys[i] - 1)
            keys[s] = oldKeys[i]; lists[s] = oldLists[i]
        }
    }

    fun insert(p: LatLon) {
        val x = longitudeToCellX(p.longitude)
        val y = latitudeToCellY(p.latitude)
        if (!isInsideBounds(x, y)) return
        val key = y.toLong() * rasterWidth + x
        var s = slotOf(key)
        if (keys[s] == 0L) {
            if ((used + 1) * 2 > keys.size) { grow(); s = slotOf(key) }
            keys[s] = key + 1
            lists[s] = ArrayList(2)
            used++
            sorted = null
        }
        lists[s]!!.add(p)
        size++
    }

    fun getAll(bounds: BoundingBox): Iterable<LatLon> {
        val startX = max(0, min(longitudeToCellX(bounds.min.longitude), rasterWidth - 1))
        val startY = max(0, min(latitudeToCellY(bounds.min.latitude), rasterHeight - 1))
        val endX = max(0, min(longitudeToCellX(bounds.max.longitude), rasterWidth - 1))
        val endY = max(0, min(latitudeToCellY(bounds.max.latitude), rasterHeight - 1))
        if (used == 0 || endX < startX || endY < startY) return emptyList()
        val out = ArrayList<LatLon>()
        if ((endX - startX + 1L) * (endY - startY + 1L) <= WIDE) {
            for (y in startY..endY) for (x in startX..endX) {
                val s = slotOf(y.toLong() * rasterWidth + x)
                if (keys[s] != 0L) out.addAll(lists[s]!!)
            }
        } else {
            // a wide box (an area with an address the size of a district): the used squares in order,
            // not every square of the box
            val all = sorted ?: LongArray(used).also { a ->
                var n = 0
                for (k in keys) if (k != 0L) a[n++] = k - 1
                a.sort()
                sorted = a
            }
            for (y in startY..endY) {
                val from = y.toLong() * rasterWidth + startX
                val to = y.toLong() * rasterWidth + endX
                var lo = 0; var hi = all.size
                while (lo < hi) { val mid = (lo + hi) ushr 1; if (all[mid] < from) lo = mid + 1 else hi = mid }
                while (lo < all.size && all[lo] <= to) { out.addAll(lists[slotOf(all[lo])]!!); lo++ }
            }
        }
        return out
    }

    private fun isInsideBounds(x: Int, y: Int): Boolean =
        x in 0 until rasterWidth && y in 0 until rasterHeight

    private fun longitudeToCellX(longitude: Double) =
        floor(normalizeLongitude(longitude - bbox.min.longitude) / cellSize).toInt()

    private fun latitudeToCellY(latitude: Double) =
        floor((latitude - bbox.min.latitude) / cellSize).toInt()

    private companion object { const val WIDE = 64L }
}
