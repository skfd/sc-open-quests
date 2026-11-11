package openquests

import java.io.File
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals

/** The points the country decision was probed at (DESIGN.md, "Countries in the place index"), pinned:
 *  if SC's boundaries.ser moves one of them, the place index moves with it and this says so. */
class RegionIdsTest {
    @Test fun `regionids gives SC's region ids at each point, in order`() {
        val dir = Files.createTempDirectory("regionids").toFile()
        val points = linkedMapOf(
            "toronto" to (-79.38 to 43.65),
            "simferopol" to (34.102 to 44.952),   // Crimea: both, no plain UA
            "laayoune" to (-13.203 to 27.153),    // west of the berm: Morocco
            "tifariti" to (-10.567 to 26.158),    // east of the berm: Western Sahara
            "ramallah" to (35.204 to 31.903),
            "senkaku" to (123.474 to 25.744),     // no country
        )
        val input = File(dir, "in.tsv").apply {
            writeText(points.entries.joinToString("") { (k, p) -> "$k\t${p.first}\t${p.second}\n" })
        }
        val out = File(dir, "out.tsv")
        regionIds(listOf("--in", input.path, "--out", out.path))
        val got = out.readLines().associate { it.substringBefore('\t') to it.substringAfter('\t') }
        assertEquals(points.keys.toList(), out.readLines().map { it.substringBefore('\t') })
        assertEquals("CA-ON,CA", got["toronto"])
        assertEquals("UA-43,RU", got["simferopol"])
        assertEquals("MA", got["laayoune"])
        assertEquals("EH", got["tifariti"])
        assertEquals("PS", got["ramallah"])
        assertEquals("", got["senkaku"])
    }
}
