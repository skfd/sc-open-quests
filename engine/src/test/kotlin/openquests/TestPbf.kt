package openquests

import com.google.protobuf.ByteString
import crosby.binary.Fileformat
import crosby.binary.Osmformat
import java.io.DataOutputStream
import java.io.File
import kotlin.math.roundToLong

/** A small .osm.pbf for tests: nodes, then ways, each with version 1 and its own timestamp. */
class TestPbf(private val replicationTimestamp: Long = 1_792_786_851L /* 2026-10-23T20:20:51Z */) {
    class N(val id: Long, val lat: Double, val lon: Double, val tags: Map<String, String>, val ts: Long)
    class W(val id: Long, val refs: List<Long>, val tags: Map<String, String>, val ts: Long)

    val nodes = ArrayList<N>()
    val ways = ArrayList<W>()
    private var nid = 1L
    private var wid = 1L

    fun node(lat: Double, lon: Double, tags: Map<String, String> = emptyMap(), ts: Long = 1_700_000_000L): Long =
        N(nid++, lat, lon, tags, ts).also { nodes += it }.id

    fun way(refs: List<Long>, tags: Map<String, String>, ts: Long = 1_700_000_000L): Long =
        W(wid++, refs, tags, ts).also { ways += it }.id

    /** a closed square way of [size] degrees with its south-west corner at ([lat], [lon]) */
    fun square(lat: Double, lon: Double, size: Double, tags: Map<String, String>): Long {
        val c = listOf(node(lat, lon), node(lat, lon + size), node(lat + size, lon + size), node(lat + size, lon))
        return way(c + c[0], tags)
    }

    fun write(file: File) {
        fun stringTable(strings: List<String>) = Osmformat.StringTable.newBuilder()
            .apply { for (x in strings) addS(ByteString.copyFromUtf8(x)) }.build()

        val nodeStrings = listOf("") + nodes.flatMap { it.tags.flatMap { (k, v) -> listOf(k, v) } }.distinct()
        val dense = Osmformat.DenseNodes.newBuilder()
        val info = Osmformat.DenseInfo.newBuilder()
        var pid = 0L; var plat = 0L; var plon = 0L; var pts = 0L
        for (n in nodes) {
            val lat = (n.lat * 1e7).roundToLong(); val lon = (n.lon * 1e7).roundToLong()
            dense.addId(n.id - pid); dense.addLat(lat - plat); dense.addLon(lon - plon)
            pid = n.id; plat = lat; plon = lon
            for ((k, v) in n.tags) { dense.addKeysVals(nodeStrings.indexOf(k)); dense.addKeysVals(nodeStrings.indexOf(v)) }
            dense.addKeysVals(0)
            info.addVersion(1); info.addTimestamp(n.ts - pts); pts = n.ts
            info.addChangeset(0); info.addUid(0); info.addUserSid(0)
        }
        dense.setDenseinfo(info)
        val nodeBlock = Osmformat.PrimitiveBlock.newBuilder().setStringtable(stringTable(nodeStrings))
            .addPrimitivegroup(Osmformat.PrimitiveGroup.newBuilder().setDense(dense)).build()

        val wayStrings = listOf("") + ways.flatMap { it.tags.flatMap { (k, v) -> listOf(k, v) } }.distinct()
        val wayGroup = Osmformat.PrimitiveGroup.newBuilder()
        for (way in ways) {
            val b = Osmformat.Way.newBuilder().setId(way.id)
                .setInfo(Osmformat.Info.newBuilder().setVersion(1).setTimestamp(way.ts))
            for ((k, v) in way.tags) { b.addKeys(wayStrings.indexOf(k)); b.addVals(wayStrings.indexOf(v)) }
            var prev = 0L
            for (ref in way.refs) { b.addRefs(ref - prev); prev = ref }
            wayGroup.addWays(b)
        }
        val wayBlock = Osmformat.PrimitiveBlock.newBuilder().setStringtable(stringTable(wayStrings))
            .addPrimitivegroup(wayGroup).build()

        val header = Osmformat.HeaderBlock.newBuilder()
            .addRequiredFeatures("OsmSchema-V0.6").addRequiredFeatures("DenseNodes")
            .addOptionalFeatures("Sort.Type_then_ID")
            .setOsmosisReplicationTimestamp(replicationTimestamp)
            .build()
        DataOutputStream(file.outputStream().buffered()).use { out ->
            fun blob(type: String, bytes: ByteArray) {
                val blob = Fileformat.Blob.newBuilder().setRaw(ByteString.copyFrom(bytes)).setRawSize(bytes.size).build().toByteArray()
                val blobHeader = Fileformat.BlobHeader.newBuilder().setType(type).setDatasize(blob.size).build().toByteArray()
                out.writeInt(blobHeader.size); out.write(blobHeader); out.write(blob)
            }
            blob("OSMHeader", header.toByteArray())
            blob("OSMData", nodeBlock.toByteArray())
            if (ways.isNotEmpty()) blob("OSMData", wayBlock.toByteArray())
        }
    }
}

/** A cities file of rectangles, boundaries written next to it. [countryCodes] null: gated by position. */
class TestCity(val id: String, val s: Double, val w: Double, val n: Double, val e: Double,
               val countryCodes: List<String>?, val timeZone: String)

fun writeTestCities(file: File, cities: List<TestCity>): File {
    val b = File(file.parentFile, "b").also { it.mkdirs() }
    val entries = cities.mapIndexed { i, c ->
        val rel = 5000L + i
        val ring = listOf(c.s to c.w, c.s to c.e, c.n to c.e, c.n to c.w, c.s to c.w)
        val geometry = ring.joinToString(",") { """{"lat": ${it.first}, "lon": ${it.second}}""" }
        File(b, "$rel.json").writeText(
            """{"type": "relation", "id": $rel, "members": [{"type": "way", "ref": 1, "role": "outer", "geometry": [$geometry]}]}""")
        val codes = c.countryCodes?.joinToString(",", "[", "]") { "\"$it\"" } ?: "null"
        """{"id": "${c.id}", "name": "${c.id}", "relation": $rel, "countryCodes": $codes, "timeZone": "${c.timeZone}", """ +
            """"population": 1, "landAreaKm2": 1.0, "boundary": "b/$rel.json"}"""
    }
    file.writeText(entries.joinToString(",\n", "{\"cities\": [\n", "\n]}\n"))
    return file
}
