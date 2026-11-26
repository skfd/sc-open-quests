package openquests

import java.io.File
import java.nio.file.Files
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** The lists made once for all cities against the loop per city they replace: the same lists in the same order. */
class CityListsTest {
    @Test fun `partsByCity gives each city the parts a filter per city gives, in the parts' order`() {
        val rnd = Random(3)
        val polygon = Polygon(doubleArrayOf(0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0))
        for (cityCount in listOf(0, 1, 7, 300)) {
            // cities without parts, cities with many, parts in no order of their city, a part of no city
            val parts = List(if (cityCount == 0) 0 else 2000) {
                Part(it, "p$it", if (it % 97 == 0) cityCount + 5 else (rnd.nextInt(cityCount) * rnd.nextInt(1, 3)) % cityCount, polygon)
            }
            val got = partsByCity(cityCount, parts)
            assertEquals(cityCount, got.size)
            for (c in 0 until cityCount) {
                assertContentEquals(parts.filter { it.city == c }.map { it.index }.toIntArray(), got[c], "city $c of $cityCount")
            }
        }
    }

    @Test fun `CityElements gives each city the elements a scan of every element's set gives, in the same order`() {
        val rnd = Random(9)
        for ((cityCount, elements) in listOf(1 to 50, 5 to 0, 5 to 3_000, 40 to 20_000, 300 to 60_000)) {
            val sets = CitySets(cityCount)
            // rectangles' sets: most elements in no city or one, some in two to four neighbours, a few in many
            val setIds = IntArray(elements) {
                when (rnd.nextInt(10)) {
                    0, 1, 2 -> 0
                    3, 4, 5, 6 -> sets.idOf(intArrayOf(rnd.nextInt(cityCount)))
                    7, 8 -> {
                        val first = rnd.nextInt(cityCount)
                        sets.idOf((first until minOf(cityCount, first + rnd.nextInt(1, 5))).toList().toIntArray())
                    }
                    else -> sets.idOf((0 until cityCount).filter { rnd.nextInt(3) == 0 }.toIntArray())
                }
            }
            // a city no element is in, where there is room for one
            val empty = if (cityCount >= 40) 17 else -1
            if (empty >= 0) for (i in setIds.indices) if (sets[setIds[i]].contains(empty)) setIds[i] = 0
            // the tagged nodes' case: an element stands in the lists as another number, ascending with it
            val values = IntArray(elements).also { v -> var at = 0; for (i in v.indices) { at += rnd.nextInt(1, 9); v[i] = at } }
            for (vs in listOf(null, values)) {
                val index = CityElements.of(sets, cityCount, setIds, vs)!!
                var pairs = 0L
                for (c in 0 until cityCount) {
                    val want = CityElements.scan(sets.membersOf(c), setIds, vs)
                    // the scan itself against the plainest reading
                    assertContentEquals(setIds.indices.filter { c in sets[setIds[it]] }.map { vs?.get(it) ?: it }.toIntArray(), want)
                    assertContentEquals(want, index.of(c), "city $c of $cityCount, ${if (vs == null) "indices" else "values"}")
                    assertEquals(want.size, index.count(c))
                    assertTrue(want.asList().zipWithNext().all { (a, b) -> a < b }, "ascending")
                    pairs += want.size
                }
                if (empty >= 0) assertEquals(0, index.count(empty))
                assertEquals(pairs, index.size.toLong())
                assertEquals(pairs, CityElements.pairs(sets, setIds))
                assertEquals(4L * (pairs + cityCount + 1) + 32, index.bytes)
            }
        }
    }

    /** the records of a state dump, sorted: their order in the file is the threads' */
    private fun records(f: File): List<String> =
        f.readBytes().asList().chunked(24).map { r -> r.joinToString("") { "%02x".format(it) } }.sorted()

    @Test fun `a run with the city index counts and dates what a run with the scan per city does`() {
        val dir = Files.createTempDirectory("city-lists").toFile()
        val helper = ManyCitiesTest()
        // 48 adjacent rectangle cities whose padded areas overlap their neighbours': most elements are in several
        // cities' lists. Every city has a bench last edited 2023-11-14, whose CheckExistence opens six years
        // on: counted 40 days before, each city has a date to find (AreaPass.dateCandidates)
        val rows = 6; val cols = 8
        val cities = helper.syntheticCities(File(dir, "cities.json"), rows, cols)
        val pbf = File(dir, "synthetic.osm.pbf").also { helper.writeSyntheticPbf(it, rows, cols, shop = true) }
        val today = parseToday("2029-10-05T00:00:00Z")
        fun run(mode: String): Pair<CountResult, List<String>> {
            val state = File(dir, "state-$mode.bin")
            val before = System.getProperty("openquests.areaIndex")
            System.setProperty("openquests.areaIndex", mode)
            try {
                val r = count(CountOptions(pbf = pbf, quests = File("data/quests/v64.1.json"), cities = cities, out = null,
                    baseDir = dir, today = today, dumpState = state))
                return r to records(state)
            } finally {
                if (before == null) System.clearProperty("openquests.areaIndex") else System.setProperty("openquests.areaIndex", before)
            }
        }
        val (scan, scanState) = run("false")
        val (index, indexState) = run("true")
        val (verify, verifyState) = run("verify")
        assertEquals(0, scan.engine.stats.cityListsVerified.get())
        assertEquals(0, index.engine.stats.cityListsVerified.get())
        // verify made both lists for every city and found them the same (it fails the run where they differ)
        assertEquals((rows * cols).toLong(), verify.engine.stats.cityListsVerified.get())
        // and, for every city (each has a date to find), the records in its tiles from its own lists and from the scan
        assertEquals((rows * cols).toLong(), verify.engine.stats.cityDatesVerified.get())
        val e = scan.engine
        var area = 0L
        for (other in listOf(index, verify)) {
            assertEquals(e.counts.perQuest.length(), other.engine.counts.perQuest.length())
            for (i in 0 until e.counts.perQuest.length()) assertEquals(e.counts.perQuest.get(i), other.engine.counts.perQuest.get(i), "counter $i")
        }
        for (c in e.cities) area += e.quests.indices.filter { e.quests[it].area != null }.sumOf { e.counts.open(c.index, it) }
        assertTrue(area >= rows * cols, "the area quests counted something in every city: $area")
        val qi = e.quests.indexOfFirst { it.name == "CheckExistence" }
        val dues = scanState.count { r -> r.substring(32, 36) == "%02x%02x".format(qi and 0xff, qi shr 8) && r.substring(38, 40) == "%02x".format(StateDump.DUE) }
        assertTrue(dues >= rows * cols, "a date for every city's bench: $dues")
        assertEquals(scanState, indexState)
        assertEquals(scanState, verifyState)
        println("city lists: $area area quests, $dues CheckExistence dates, ${scanState.size} records, the same with and without the index")
    }
}
