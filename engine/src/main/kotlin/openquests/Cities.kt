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

/** Finds the cities whose polygon contains a point: bounding boxes first, then the polygons. */
class CityIndex(val cities: List<City>) {
    private val minLat = DoubleArray(cities.size) { cities[it].polygon.minLat }
    private val maxLat = DoubleArray(cities.size) { cities[it].polygon.maxLat }
    private val minLon = DoubleArray(cities.size) { cities[it].polygon.minLon }
    private val maxLon = DoubleArray(cities.size) { cities[it].polygon.maxLon }

    /** Whether the box could hold a point of some city. A polygon centroid lies in its convex hull
     *  and a polyline midpoint on the line, so an element whose bbox misses every city's bbox
     *  cannot have its centre in a city. */
    fun bboxMayHit(south: Double, west: Double, north: Double, east: Double): Boolean {
        for (i in cities.indices) {
            if (north >= minLat[i] && south <= maxLat[i] && east >= minLon[i] && west <= maxLon[i]) return true
        }
        return false
    }

    /** Indices of the cities containing the point, ascending; [NONE] if there are none. */
    fun citiesAt(lat: Double, lon: Double): IntArray {
        var result = NONE
        for (i in cities.indices) {
            if (lat < minLat[i] || lat > maxLat[i] || lon < minLon[i] || lon > maxLon[i]) continue
            if (cities[i].polygon.contains(lat, lon)) result = result + i
        }
        return result
    }

    companion object {
        val NONE = IntArray(0)
    }
}
