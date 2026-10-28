package openquests

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.double
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import java.io.File

class City(
    val index: Int,
    val id: String,
    val name: String,
    val relation: Long,
    val countryCodes: List<String>,
    val timeZone: String,
    val population: Long?,
    val landAreaKm2: Double?,
    val polygon: Polygon,
)

fun loadCities(file: File, baseDir: File): List<City> {
    val root = Json.parseToJsonElement(file.readText()).jsonObject
    val cities = root["cities"]!!.jsonArray.mapIndexed { i, e ->
        val c = e as JsonObject
        val relation = c["relation"]!!.jsonPrimitive.long
        val boundary = File(baseDir, c.str("boundary")!!)
        City(
            index = i,
            id = c.str("id")!!,
            name = c.str("name")!!,
            relation = relation,
            countryCodes = c["countryCodes"]!!.jsonArray.map { it.jsonPrimitive.content },
            timeZone = c.str("timeZone")!!,
            population = c["population"]?.takeIf { it !is JsonNull }?.jsonPrimitive?.long,
            landAreaKm2 = c["landAreaKm2"]?.takeIf { it !is JsonNull }?.jsonPrimitive?.double,
            polygon = Polygon.fromOverpassJson(boundary, relation),
        )
    }
    val ids = cities.map { it.id }
    require(ids.toSet().size == ids.size) { "duplicate city ids in ${file.path}" }
    return cities
}

/** A neighbourhood of a city (config/parts/<city>.json): counted from the city's quests whose
 *  position is inside [polygon], nothing of its own. [index] is its place among all parts of the run. */
class Part(val index: Int, val id: String, val city: Int, val polygon: Polygon)

/** The parts of [cities] from `<dir>/<cityId>.json` where that file exists (DATA-FORMAT.md, "Places
 *  and parts"); geometry paths are relative to [baseDir]. In city order, each city's in registry order. */
fun loadParts(dir: File, cities: List<City>, baseDir: File): List<Part> {
    val parts = ArrayList<Part>()
    for (city in cities) {
        val file = File(dir, "${city.id}.json")
        if (!file.isFile) continue
        val root = Json.parseToJsonElement(file.readText()).jsonObject
        require(root.str("city") == city.id) { "${file.path} is the registry of ${root.str("city")}, not ${city.id}" }
        val seen = HashSet<String>()
        for (e in root["parts"]!!.jsonArray) {
            val p = e.jsonObject
            val id = p.str("id")!!
            require(seen.add(id)) { "${file.path}: part $id twice" }
            parts += Part(parts.size, id, city.index, Polygon.fromGeoJson(File(baseDir, p.str("geometry")!!)))
        }
    }
    return parts
}

/** Finds the cities whose polygon contains a point: bounding boxes first (through a [BoxGrid]), then
 *  the polygons. */
class CityIndex(val cities: List<City>) : PolygonIndex(cities.map { it.polygon }) {
    /** Indices of the cities containing the point, ascending; [NONE] if there are none. */
    fun citiesAt(lat: Double, lon: Double): IntArray = at(lat, lon)

    companion object {
        val NONE = IntArray(0)
    }
}

/** Finds the polygons that contain a point: bounding boxes first (through a [BoxGrid]), then the
 *  polygons. */
open class PolygonIndex(private val polygons: List<Polygon>) {
    private val minLat = DoubleArray(polygons.size) { polygons[it].minLat }
    private val maxLat = DoubleArray(polygons.size) { polygons[it].maxLat }
    private val minLon = DoubleArray(polygons.size) { polygons[it].minLon }
    private val maxLon = DoubleArray(polygons.size) { polygons[it].maxLon }
    // floor() is monotone, so a point inside a box has its cell inside the box's cells
    private val grid = BoxGrid(
        IntArray(polygons.size) { deg7(minLat[it]) }, IntArray(polygons.size) { deg7(minLon[it]) },
        IntArray(polygons.size) { deg7(maxLat[it]) }, IntArray(polygons.size) { deg7(maxLon[it]) })

    /** Whether the box could hold a point of some city. A polygon centroid lies in its convex hull
     *  and a polyline midpoint on the line, so an element whose bbox misses every city's bbox
     *  cannot have its centre in a city. */
    fun bboxMayHit(south: Double, west: Double, north: Double, east: Double): Boolean {
        fun hits(i: Int) = north >= minLat[i] && south <= maxLat[i] && east >= minLon[i] && west <= maxLon[i]
        val cells = grid.cellsIn(deg7(south), deg7(west), deg7(north), deg7(east))
        if (cells == null) { for (i in polygons.indices) if (hits(i)) return true; return false }
        for (cell in cells) for (i in grid.candidatesInCell(cell) ?: continue) if (hits(i)) return true
        return false
    }

    /** Indices of the polygons containing the point, ascending; an empty array if there are none. */
    fun at(lat: Double, lon: Double): IntArray {
        val candidates = grid.candidates(deg7(lat), deg7(lon)) ?: return CityIndex.NONE
        var result = CityIndex.NONE
        for (i in candidates) {
            if (lat < minLat[i] || lat > maxLat[i] || lon < minLon[i] || lon > maxLon[i]) continue
            if (polygons[i].contains(lat, lon)) result = result + i
        }
        return result
    }
}

private fun deg7(d: Double): Int = kotlin.math.floor(d * 1e7).toInt()

/**
 * A uniform grid over boxes given in 1e-7 degrees (inclusive bounds), for finding the boxes that may
 * hold a point without testing every box: each cell lists, ascending, the boxes that overlap it. The
 * grid spans the boxes' union, in at most [MAX_CELLS_PER_AXIS] cells per axis and cells of at least
 * [MIN_CELL] (0.005 degrees, about 500 m): Ontario's 53 cities give cells of about 1.5 x 4 km, the whole
 * planet cells of about 40 x 80 km. A point outside the grid has no candidates.
 */
class BoxGrid(south: IntArray, west: IntArray, north: IntArray, east: IntArray) {
    private val lat0: Long; private val lon0: Long
    private val cellLat: Long; private val cellLon: Long
    private val rows: Int; private val cols: Int
    private val cells: Array<IntArray?>

    init {
        val n = south.size
        if (n == 0) {
            lat0 = 0; lon0 = 0; cellLat = 1; cellLon = 1; rows = 0; cols = 0; cells = emptyArray()
        } else {
            lat0 = south.min().toLong(); lon0 = west.min().toLong()
            val latSpan = north.max() - lat0 + 1; val lonSpan = east.max() - lon0 + 1
            cellLat = maxOf(MIN_CELL, (latSpan + MAX_CELLS_PER_AXIS - 1) / MAX_CELLS_PER_AXIS)
            cellLon = maxOf(MIN_CELL, (lonSpan + MAX_CELLS_PER_AXIS - 1) / MAX_CELLS_PER_AXIS)
            rows = ((latSpan + cellLat - 1) / cellLat).toInt(); cols = ((lonSpan + cellLon - 1) / cellLon).toInt()
            val counts = IntArray(rows * cols)
            fun each(i: Int, f: (Int) -> Unit) {
                for (r in row(south[i])..row(north[i])) for (c in col(west[i])..col(east[i])) f(r * cols + c)
            }
            for (i in 0 until n) each(i) { counts[it]++ }
            val filled = IntArray(rows * cols)
            cells = Array(rows * cols) { if (counts[it] == 0) null else IntArray(counts[it]) }
            for (i in 0 until n) each(i) { cells[it]!![filled[it]++] = i } // i ascends, so each cell's list does
        }
    }

    private fun row(lat7: Int) = ((lat7 - lat0) / cellLat).toInt()
    private fun col(lon7: Int) = ((lon7 - lon0) / cellLon).toInt()

    /** Cell index of the point, or -1 outside the grid. */
    fun cellOf(lat7: Int, lon7: Int): Int {
        if (lat7 < lat0 || lon7 < lon0) return -1
        val r = row(lat7); val c = col(lon7)
        return if (r >= rows || c >= cols) -1 else r * cols + c
    }

    /** The boxes overlapping the point's cell, ascending (a superset of those holding the point). */
    fun candidates(lat7: Int, lon7: Int): IntArray? {
        val cell = cellOf(lat7, lon7)
        return if (cell < 0) null else cells[cell]
    }

    fun candidatesInCell(cell: Int): IntArray? = cells[cell]

    /** The cells a box overlaps, or null if that is more than [maxCells] (test every box instead). */
    fun cellsIn(south: Int, west: Int, north: Int, east: Int, maxCells: Int = 64): IntArray? {
        if (rows == 0 || north < lat0 || east < lon0) return IntArray(0)
        val r0 = if (south < lat0) 0 else row(south); val r1 = minOf(rows - 1, row(north))
        val c0 = if (west < lon0) 0 else col(west); val c1 = minOf(cols - 1, col(east))
        if (r0 > r1 || c0 > c1) return IntArray(0)
        if ((r1 - r0 + 1).toLong() * (c1 - c0 + 1) > maxCells) return null
        return IntArray((r1 - r0 + 1) * (c1 - c0 + 1)).also { a ->
            var k = 0
            for (r in r0..r1) for (c in c0..c1) a[k++] = r * cols + c
        }
    }

    companion object {
        const val MAX_CELLS_PER_AXIS = 512L
        const val MIN_CELL = 50_000L
    }
}

/**
 * City membership as one Int: each distinct set of city indices gets an id, 0 the empty set and
 * c + 1 the set {c}. Thread-safe; the common cases (no city, one city, the same set again) take no
 * lock and no allocation.
 */
class CitySets(private val cityCount: Int) {
    private val lock = Any()
    // the sets by id; an element never changes once written, the array is replaced when it grows
    @Volatile private var sets: Array<IntArray?> = arrayOfNulls(maxOf(16, 2 * (cityCount + 1)))
    // written after the set it counts, so a reader that sees the count sees the set
    @Volatile private var count = 0
    private val ids = HashMap<List<Int>, Int>()  // guarded by lock
    private val unions = java.util.concurrent.ConcurrentHashMap<Long, Int>()

    init {
        add(IntArray(0))
        for (c in 0 until cityCount) add(intArrayOf(c))
    }

    val size: Int get() = count

    /** The cities of set [id], ascending. */
    operator fun get(id: Int): IntArray {
        if (id < count) return sets[id]!!
        synchronized(lock) { return sets[id]!! }
    }

    /** The id of [sortedCities] (ascending, distinct). */
    fun idOf(sortedCities: IntArray): Int {
        if (sortedCities.isEmpty()) return 0
        if (sortedCities.size == 1 && sortedCities[0] < cityCount) return sortedCities[0] + 1
        synchronized(lock) { return ids[sortedCities.toList()] ?: add(sortedCities.copyOf()) }
    }

    private fun add(sorted: IntArray): Int = synchronized(lock) {
        val id = count
        if (id == sets.size) sets = sets.copyOf(2 * id)
        sets[id] = sorted
        ids[sorted.toList()] = id
        count = id + 1
        id
    }

    fun union(a: Int, b: Int): Int {
        if (a == b || b == 0) return a
        if (a == 0) return b
        val key = (minOf(a, b).toLong() shl 32) or maxOf(a, b).toLong()
        unions[key]?.let { return it }
        val x = get(a); val y = get(b)
        val merged = IntArray(x.size + y.size)
        var i = 0; var j = 0; var n = 0
        while (i < x.size || j < y.size) {
            val v = when {
                j == y.size || (i < x.size && x[i] < y[j]) -> x[i++]
                i == x.size || y[j] < x[i] -> y[j++]
                else -> { j++; x[i++] }
            }
            merged[n++] = v
        }
        return idOf(merged.copyOf(n)).also { unions[key] = it }
    }

    /** For each set id, whether it holds [city]; index it with an element's id. */
    fun membersOf(city: Int): BooleanArray = BooleanArray(size) { get(it).binarySearch(city) >= 0 }
}
