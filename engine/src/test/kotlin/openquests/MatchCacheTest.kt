package openquests

import de.westnordost.streetcomplete.data.elementfilter.toElementFilterExpression
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.data.osm.mapdata.ElementType
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.data.osm.mapdata.Node
import de.westnordost.streetcomplete.data.osm.mapdata.Relation
import de.westnordost.streetcomplete.data.osm.mapdata.Way
import java.io.File
import kotlin.random.Random
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.time.Clock
import kotlin.time.Duration.Companion.days
import kotlin.time.Instant

class MatchCacheTest {
    @AfterTest fun restore() = EngineClock.install(Clock.System.now())

    private val asOf = Instant.parse("2026-11-07T21:21:36Z")
    private val clocks = listOf(asOf, EngineClock.LONG_AGO, asOf + (40 * 366).days, asOf - 400.days, asOf + 900.days)
    private val settings = listOf<Float?>(null, Resurvey.HALF, Resurvey.DOUBLE)

    private fun questsByType(quests: List<QuestDef>) = Array(3) { t ->
        quests.indices.filter { quests[it].matcher?.includesElementType(ElementType.entries[t]) == true }.toIntArray()
    }

    private fun element(type: Int, id: Long, tags: Map<String, String>, timestamp: Long): Element {
        val map = TagMap(tags.size).apply { for ((k, v) in tags) add(k, v) }
        return when (type) {
            NODE -> Node(id, LatLon(0.0, 0.0), map, 1, timestamp)
            WAY -> Way(id, listOf(1L, 2L), map, 1, timestamp)
            else -> Relation(id, emptyList(), map, 1, timestamp)
        }
    }

    /** every variant a count can ask: the clock here, long ago and far ahead, at each resurvey setting */
    private fun answers(q: QuestDef, e: Element): Set<Boolean> = buildSet {
        for (clock in clocks) for (s in settings) add(EngineClock.at(clock) { Resurvey.at(s) { q.matcher!!.matches(e) } })
    }

    /** what the cache settles for [e] must be what the quest answers, whatever the clock and the setting */
    private fun check(cache: MatchCache, quests: List<QuestDef>, byType: Array<IntArray>, type: Int, e: Element, tally: IntArray) {
        val out = cache.outcome(type, e)!!
        for (qi in byType[type]) {
            val q = quests[qi]
            val i = out.sure.indexOf(qi)
            when {
                i >= 0 -> {
                    assertEquals(setOf(true), answers(q, e), "${q.name} settled as open on ${e.tags}")
                    assertEquals(if (q.usesAge) M_NOW or M_05 or M_2 else M_NOW, out.sureMask[i], q.name)
                    assertEquals(out.sureMask[i], matchVariants(q.usesAge) { q.matcher!!.matches(e) }, q.name)
                    tally[0]++
                }
                qi in out.ask -> tally[1]++
                else -> {
                    assertEquals(setOf(false), answers(q, e), "${q.name} settled as never open on ${e.tags}")
                    tally[2]++
                }
            }
        }
    }

    @Test fun `what a signature settles is what every quest answers`() {
        EngineClock.install(asOf)
        val registry = Registry.load(File("data/quests/v64.1.json"))
        val quests = registry.countedQuests
        val byType = questsByType(quests)
        val cache = MatchCache(quests, byType)

        // the filters' own words: each `key = value`, `key ~ a|b`, `key < 3` gives the key its values
        val values = HashMap<String, MutableSet<String>>()
        val perQuest = quests.map { q ->
            val keys = LinkedHashSet<String>()
            val text = q.elementFilter.orEmpty()
            for (m in Regex("""~?([\w:]+)\s*(?:!?[=~]|[<>]=?)\s*([\w|:.-]+)""").findAll(text)) {
                keys += m.groupValues[1].split('|')
                for (k in m.groupValues[1].split('|')) values.getOrPut(k) { HashSet() } += m.groupValues[2].split('|')
            }
            for (m in Regex("""!?~?([\w:|]+)""").findAll(text)) keys += m.groupValues[1].split('|').filter { it.isNotEmpty() }
            keys.toList()
        }
        val allKeys = (perQuest.flatten() + values.keys).distinct()
        val anyValue = listOf("yes", "no", "2", "3.5", "0.5", "30 mph", "2019-06-01", "2031-01-01", "x", "asphalt", "Main St", "designated")
        val rnd = Random(7)
        val stamps = listOf(0L, asOf.toEpochMilliseconds(), (asOf - 500.days).toEpochMilliseconds(),
            (asOf - 3000.days).toEpochMilliseconds(), (asOf - 30.days).toEpochMilliseconds())
        val tally = IntArray(3)
        var id = 0L
        repeat(60_000) {
            val q = rnd.nextInt(quests.size)
            val pool = perQuest[q].ifEmpty { allKeys }
            val tags = HashMap<String, String>()
            repeat(1 + rnd.nextInt(7)) {
                val k = if (rnd.nextInt(6) == 0) allKeys[rnd.nextInt(allKeys.size)] else pool[rnd.nextInt(pool.size)]
                val own = values[k]?.toList()
                tags[k] = if (own != null && rnd.nextInt(4) != 0) own[rnd.nextInt(own.size)] else anyValue[rnd.nextInt(anyValue.size)]
            }
            // a tag no filter names must change nothing
            if (rnd.nextBoolean()) tags["addr:housenumber"] = rnd.nextInt(300).toString()
            if (rnd.nextInt(5) == 0) tags["check_date:" + pool[rnd.nextInt(pool.size)]] = if (rnd.nextBoolean()) "2019-06-01" else "2026-10-01"
            val type = rnd.nextInt(3)
            check(cache, quests, byType, type, element(type, ++id, tags, stamps[rnd.nextInt(stamps.size)]), tally)
        }
        // the test has teeth only if all three answers came up often
        assertTrue(tally[0] > 5_000, "settled as open: ${tally[0]}")
        assertTrue(tally[1] > 5_000, "asked: ${tally[1]}")
        assertTrue(tally[2] > 1_000_000, "settled as never open: ${tally[2]}")
    }

    @Test fun `a value's class is what the filters can tell apart`() {
        EngineClock.install(asOf)
        val a = QuestDef(0, "A", 0, "filter", "ways with highway ~ residential|service and !name and width < 3", null, null,
            false, false, false, Countries.All, null, null, listOf("ways"))
        val b = QuestDef(1, "B", 1, "filter", "ways with ~addr:.* ~ 1.* and surface older today -4 years", null, null,
            false, true, false, Countries.All, null, null, listOf("ways"))
        val quests = listOf(a, b)
        val byType = questsByType(quests)
        val cache = MatchCache(quests, byType)
        fun way(vararg tags: Pair<String, String>, timestamp: Long = 0L) = element(WAY, 1, mapOf(*tags), timestamp)
        fun settled(e: Element) = cache.outcome(WAY, e)!!.let { it.sure.toList() to it.ask.toList() }

        assertEquals(listOf(0) to emptyList<Int>(), settled(way("highway" to "service", "width" to "2")))
        assertEquals(listOf(0) to emptyList<Int>(), settled(way("highway" to "residential", "width" to "2.5", "lit" to "yes")))
        assertEquals(emptyList<Int>() to emptyList<Int>(), settled(way("highway" to "residential", "width" to "4")))
        assertEquals(emptyList<Int>() to emptyList<Int>(), settled(way("highway" to "residential", "width" to "2", "name" to "A")))
        assertEquals(emptyList<Int>() to emptyList<Int>(), settled(way("highway" to "primary", "width" to "2")))
        // a key regex with a value regex: the quest with the open leaf is asked only where the tags allow it
        // (`surface older` means the tag surface, older than that: without the tag it is never open)
        assertEquals(emptyList<Int>() to emptyList<Int>(), settled(way("addr:housenumber" to "12")))
        assertEquals(emptyList<Int>() to listOf(1), settled(way("addr:housenumber" to "12", "surface" to "sand")))
        assertEquals(emptyList<Int>() to emptyList<Int>(), settled(way("addr:housenumber" to "22", "surface" to "sand")))
        assertEquals(emptyList<Int>() to listOf(1), settled(way("addr:housenumber" to "22", "addr:unit" to "1a", "surface" to "mud")))
        assertEquals(listOf(0) to listOf(1),
            settled(way("highway" to "service", "width" to "1", "addr:flats" to "1-4", "surface" to "mud")))
    }
}
