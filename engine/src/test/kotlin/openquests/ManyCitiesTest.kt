package openquests

import com.google.protobuf.ByteString
import crosby.binary.Fileformat
import crosby.binary.Osmformat
import java.io.DataOutputStream
import java.io.File
import java.nio.file.Files
import kotlin.math.roundToLong
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** More cities than the 64 the area pass once kept in a bit mask, and the grids that find them. */
class ManyCitiesTest {
    // ---------------------------------------------------------------------------------------------
    // the grids against brute force

    @Test fun `BoxGrid and CitySets give what testing every box gives`() {
        val rnd = Random(7)
        // 300 boxes, small and large, clustered and overlapping, around Ontario and across the date line's neighbour
        val n = 300
        val s = IntArray(n); val w = IntArray(n); val nn = IntArray(n); val e = IntArray(n)
        for (i in 0 until n) {
            val lat = if (i % 3 == 0) 43.6 + rnd.nextDouble(0.3) else rnd.nextDouble(-60.0, 70.0)
            val lon = if (i % 3 == 0) -79.6 + rnd.nextDouble(0.5) else rnd.nextDouble(-179.0, 179.0)
            val h = if (i % 10 == 0) rnd.nextDouble(1.0) else rnd.nextDouble(0.08)
            val wd = if (i % 10 == 0) rnd.nextDouble(1.0) else rnd.nextDouble(0.08)
            s[i] = (lat * 1e7).toInt(); nn[i] = ((lat + h) * 1e7).toInt()
            w[i] = (lon * 1e7).toInt(); e[i] = ((lon + wd) * 1e7).toInt()
        }
        val grid = BoxGrid(s, w, nn, e)
        val sets = CitySets(n)
        repeat(200_000) { k ->
            // half the points near a box, so that most have candidates
            val b = rnd.nextInt(n)
            val lat7 = if (k % 2 == 0) rnd.nextInt(s[b] - 1000, nn[b] + 1000) else rnd.nextInt(-900_000_000, 900_000_000)
            val lon7 = if (k % 2 == 0) rnd.nextInt(w[b] - 1000, e[b] + 1000) else rnd.nextInt(-1_800_000_000, 1_800_000_000)
            val want = (0 until n).filter { lat7 in s[it]..nn[it] && lon7 in w[it]..e[it] }.toIntArray()
            val got = grid.candidates(lat7, lon7)?.filter { lat7 in s[it]..nn[it] && lon7 in w[it]..e[it] }?.toIntArray() ?: IntArray(0)
            assertContentEquals(want, got, "$lat7,$lon7")
            assertContentEquals(want, sets[sets.idOf(want)])
        }
        // unions of sets are the sets of the union
        repeat(5_000) {
            val a = (0 until n).filter { rnd.nextInt(40) == 0 }.toIntArray()
            val b = (0 until n).filter { rnd.nextInt(40) == 0 }.toIntArray()
            val u = sets.union(sets.idOf(a), sets.idOf(b))
            assertContentEquals((a.toSet() + b.toSet()).sorted().toIntArray(), sets[u])
            val member = sets.membersOf(a.firstOrNull() ?: 0)
            if (a.isNotEmpty()) assertTrue(member[u])
        }
        assertEquals(0, sets.idOf(IntArray(0)))
        assertEquals(6, sets.idOf(intArrayOf(5)))
    }

    @Test fun `CityIndex finds what testing every city finds, for the real cities and for many small ones`() {
        val real = loadCities(File("config/cities.json"), File("."))
        val small = syntheticCities(File(Files.createTempDirectory("many-cities").toFile(), "c"), 12, 10).let {
            loadCities(it, it.parentFile)
        }
        val rnd = Random(11)
        for (cities in listOf(real, small)) {
            val index = CityIndex(cities)
            fun brute(lat: Double, lon: Double) = cities.indices.filter { cities[it].polygon.contains(lat, lon) }.toIntArray()
            repeat(20_000) {
                val c = cities[rnd.nextInt(cities.size)].polygon
                val lat = rnd.nextDouble(c.minLat - 0.05, c.maxLat + 0.05)
                val lon = rnd.nextDouble(c.minLon - 0.05, c.maxLon + 0.05)
                assertContentEquals(brute(lat, lon), index.citiesAt(lat, lon), "$lat,$lon")
                val h = rnd.nextDouble(0.0, if (rnd.nextInt(20) == 0) 5.0 else 0.05)
                val wd = rnd.nextDouble(0.0, if (rnd.nextInt(20) == 0) 5.0 else 0.05)
                val want = cities.any { val p = it.polygon
                    lat + h >= p.minLat && lat <= p.maxLat && lon + wd >= p.minLon && lon <= p.maxLon }
                assertEquals(want, index.bboxMayHit(lat, lon, lat + h, lon + wd), "box $lat,$lon +$h,+$wd")
            }
        }
    }

    // ---------------------------------------------------------------------------------------------
    // a whole run with 80 cities

    @Test fun `a run with 80 cities counts each city as runs with 40 do`() {
        val dir = Files.createTempDirectory("many-cities").toFile()
        val rows = 8; val cols = 10
        val all = syntheticCities(File(dir, "all.json"), rows, cols)
        val pbf = File(dir, "synthetic.osm.pbf").also { writeSyntheticPbf(it, rows, cols) }
        val quests = File("data/quests/v64.0.json")
        fun run(cities: File) = count(CountOptions(pbf = pbf, quests = quests, cities = cities, out = null, baseDir = dir))
        val whole = run(all)
        assertEquals(rows * cols, whole.engine.cities.size)

        val ids = whole.engine.cities.map { it.id }
        val halves = ids.chunked(ids.size / 2).mapIndexed { k, part ->
            val f = File(dir, "half$k.json")
            f.writeText(citiesJson(part.map { id -> id.removePrefix("c").split("-").let { it[0].toInt() to it[1].toInt() } }))
            run(f)
        }

        val e = whole.engine
        val slots = e.counts.perQuest.length() / (e.counts.cityCount * e.counts.questCount)
        var areaCounted = 0L
        for (city in e.cities) {
            val half = halves.single { r -> r.engine.cities.any { it.id == city.id } }.engine
            val hc = half.cities.single { it.id == city.id }.index
            for (qi in e.quests.indices) {
                val hq = half.quests.indexOfFirst { it.name == e.quests[qi].name }
                for (slot in 0 until slots) assertEquals(half.counts.get(hc, hq, slot), e.counts.get(city.index, qi, slot),
                    "${city.id} ${e.quests[qi].name} slot $slot")
            }
            val housenumbers = e.counts.open(city.index, e.quests.indexOfFirst { it.name == "AddHousenumber" })
            assertEquals(1, housenumbers, "${city.id}: AddHousenumber (an area quest) for its one house")
            areaCounted += e.quests.indices.filter { e.quests[it].area != null }.sumOf { e.counts.open(city.index, it) }
        }
        println("80 cities: ${e.quests.indices.sumOf { qi -> e.cities.sumOf { e.counts.open(it.index, qi) } }} quests, $areaCounted from area quests")
    }

    private val lat0 = 43.70
    private val lon0 = -79.40
    private val step = 0.01

    private fun citiesJson(cells: List<Pair<Int, Int>>): String = cells.joinToString(",\n", "{\"cities\": [\n", "\n]}\n") { (r, c) ->
        """{"id": "c$r-$c", "name": "C $r $c", "relation": ${relationId(r, c)}, "countryCodes": ["CA", "CA-ON"], """ +
            """"timeZone": "America/Toronto", "population": 1000, "landAreaKm2": 1.0, "boundary": "b/${relationId(r, c)}.json"}"""
    }

    private fun relationId(r: Int, c: Int) = 1000L + r * 100 + c

    /** rows x cols adjacent squares of [step] degrees from (lat0, lon0), boundaries written next to [file] */
    private fun syntheticCities(file: File, rows: Int, cols: Int): File {
        val b = File(file.parentFile, "b").also { it.mkdirs() }
        val cells = (0 until rows).flatMap { r -> (0 until cols).map { c -> r to c } }
        for ((r, c) in cells) {
            val s = lat0 + r * step; val w = lon0 + c * step; val n = s + step; val e = w + step
            val ring = listOf(s to w, s to e, n to e, n to w, s to w)
            val geometry = ring.joinToString(",") { """{"lat": ${it.first}, "lon": ${it.second}}""" }
            File(b, "${relationId(r, c)}.json").writeText(
                """{"type": "relation", "id": ${relationId(r, c)}, "members": [{"type": "way", "ref": 1, "role": "outer", "geometry": [$geometry]}]}""")
        }
        file.writeText(citiesJson(cells))
        return file
    }

    /**
     * Per city: a house without an address (AddHousenumber), a residential road crossed by a footway
     * at a shared node, and a bench; every other column a road that runs on into the next city, so
     * that a way lies in two cities' areas. Every city's area overlaps its neighbours' (1 km padding).
     */
    private fun writeSyntheticPbf(file: File, rows: Int, cols: Int) {
        class N(val id: Long, val lat: Double, val lon: Double, val tags: Map<String, String> = emptyMap())
        class W(val id: Long, val refs: List<Long>, val tags: Map<String, String>)
        val nodes = ArrayList<N>(); val ways = ArrayList<W>()
        var nid = 1L; var wid = 1L
        fun node(lat: Double, lon: Double, tags: Map<String, String> = emptyMap()) = N(nid++, lat, lon, tags).also { nodes += it }.id
        for (r in 0 until rows) for (c in 0 until cols) {
            val s = lat0 + r * step; val w = lon0 + c * step
            val house = listOf(node(s + .003, w + .003), node(s + .003, w + .0034), node(s + .0034, w + .0034), node(s + .0034, w + .003))
            ways += W(wid++, house + house[0], mapOf("building" to "house"))
            val crossing = node(s + .006, w + .005)
            ways += W(wid++, listOf(node(s + .006, w + .002), crossing, node(s + .006, w + .008)), mapOf("highway" to "residential"))
            ways += W(wid++, listOf(node(s + .005, w + .005), crossing, node(s + .007, w + .005)), mapOf("highway" to "footway"))
            node(s + .008, w + .008, mapOf("amenity" to "bench"))
            if (c % 2 == 0 && c + 1 < cols) {
                ways += W(wid++, listOf(node(s + .009, w + .002), node(s + .009, w + .014)), mapOf("highway" to "service"))
            }
        }
        val ts = 1_700_000_000L // 2023-11-14, in seconds (date_granularity 1000 ms)

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
            info.addVersion(1); info.addTimestamp(ts - pts); pts = ts
            info.addChangeset(0); info.addUid(0); info.addUserSid(0)
        }
        dense.setDenseinfo(info)
        val nodeBlock = Osmformat.PrimitiveBlock.newBuilder().setStringtable(stringTable(nodeStrings))
            .addPrimitivegroup(Osmformat.PrimitiveGroup.newBuilder().setDense(dense)).build()

        val wayStrings = listOf("") + ways.flatMap { it.tags.flatMap { (k, v) -> listOf(k, v) } }.distinct()
        val wayGroup = Osmformat.PrimitiveGroup.newBuilder()
        for (way in ways) {
            val b = Osmformat.Way.newBuilder().setId(way.id)
                .setInfo(Osmformat.Info.newBuilder().setVersion(1).setTimestamp(ts))
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
            .setOsmosisReplicationTimestamp(1_792_786_851L) // 2026-10-23T20:20:51Z
            .build()
        DataOutputStream(file.outputStream().buffered()).use { out ->
            fun blob(type: String, bytes: ByteArray) {
                val blob = Fileformat.Blob.newBuilder().setRaw(ByteString.copyFrom(bytes)).setRawSize(bytes.size).build().toByteArray()
                val blobHeader = Fileformat.BlobHeader.newBuilder().setType(type).setDatasize(blob.size).build().toByteArray()
                out.writeInt(blobHeader.size); out.write(blobHeader); out.write(blob)
            }
            blob("OSMHeader", header.toByteArray())
            blob("OSMData", nodeBlock.toByteArray())
            blob("OSMData", wayBlock.toByteArray())
        }
    }
}
