package openquests

import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.ui.ktx.countryMetadataCodes
import de.westnordost.streetcomplete.ui.ktx.readBundled
import openquests.custom.ScCountryInfos
import org.junit.jupiter.api.Assumptions.assumeTrue
import java.io.File
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** The bundle of SC's country_metadata (sync-sc.ps1): complete, and a gap in it is an error. */
class CountryMetadataTest {
    private val bundled = File("engine/src/main/resources/sc/country_metadata")

    private fun ymlNames(dir: File) = dir.listFiles { f -> f.name.endsWith(".yml") }.orEmpty().map { it.name.removeSuffix(".yml") }.toSet()

    @Test fun `the index lists exactly the bundled files`() {
        assertTrue(countryMetadataCodes.size >= 500, "${countryMetadataCodes.size} codes")
        assertTrue("default" in countryMetadataCodes && "CA-ON" in countryMetadataCodes && "JP" in countryMetadataCodes)
        assertEquals(countryMetadataCodes, ymlNames(bundled))
        for (code in countryMetadataCodes) {
            assertTrue(javaClass.getResource("/sc/country_metadata/$code.yml") != null, "$code.yml not on the classpath")
        }
    }

    @Test fun `every country_metadata file of the SC checkout is bundled, byte for byte`() {
        val boundaries = File(System.getProperty("openquests.scBoundaries") ?: "")
        val sc = File(boundaries.parentFile ?: File(""), "country_metadata")
        assumeTrue(sc.isDirectory, "SC country_metadata not found at $sc")
        assertEquals(ymlNames(sc), countryMetadataCodes)
        for (code in countryMetadataCodes) {
            assertContentEquals(File(sc, "$code.yml").readBytes(), File(bundled, "$code.yml").readBytes(), code)
        }
    }

    @Test fun `SC-VERSION txt records the sha256 of every bundled file`() {
        val recorded = File("engine/SC-VERSION.txt").readLines()
            .mapNotNull { Regex("""^\s+([0-9a-f]{64})\s+country_metadata/(\S+)\.yml$""").find(it) }
            .associate { it.groupValues[2] to it.groupValues[1] }
        assertEquals(countryMetadataCodes, recorded.keys)
        val sha = MessageDigest.getInstance("SHA-256")
        for ((code, want) in recorded) {
            val got = sha.digest(File(bundled, "$code.yml").readBytes()).joinToString("") { "%02x".format(it) }
            assertEquals(want, got, code)
        }
    }

    @Test fun `every bundled file decodes as SC decodes it`() {
        for (code in countryMetadataCodes - "default") ScCountryInfos.get(listOf(code))
    }

    @Test fun `a file SC ships but the bundle lacks is an error, a region without one is not`() {
        val codes = setOf("default", "JP")
        assertFailsWith<IllegalStateException> { readBundled("files/country_metadata/JP.yml", { codes }) { null } }
        assertNull(readBundled("files/country_metadata/JP-13.yml", { codes }) { null })
        assertNull(readBundled("files/osmfeatures/default/fr.json", { codes }) { null })
        // the real bundle: SC has no file for Tokyo-to (JP-13), so CountryInfos skips the id
        assertNull(readBundled("files/country_metadata/JP-13.yml", { countryMetadataCodes }) { javaClass.getResourceAsStream(it) })
    }

    @Test fun `positions outside Canada and Germany read their own country's metadata`() {
        val tokyo = ScCountryInfos.getCountryInfoByLocation(LatLon(35.6812, 139.7671))
        assertEquals("JP", tokyo.countryCode)
        assertTrue(tokyo.isLeftHandTraffic) // JP.yml; default.yml says false
        assertEquals(listOf("ja"), tokyo.officialLanguages)

        val sydneyIds = ScCountryInfos.countryBoundaries.getIds(LatLon(-33.8688, 151.2093))
        assertEquals(listOf("AU-NSW", "AU"), sydneyIds)
        assertTrue(ScCountryInfos.get(sydneyIds).isLeftHandTraffic) // AU.yml

        val houstonIds = ScCountryInfos.countryBoundaries.getIds(LatLon(29.7604, -95.3698))
        assertEquals("US", ScCountryInfos.get(houstonIds).countryCode)
        assertEquals(listOf("US-TX", "US"), houstonIds)
    }
}
