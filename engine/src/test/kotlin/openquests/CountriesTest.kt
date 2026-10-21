package openquests

import de.westnordost.countryboundaries.CountryBoundaries
import kotlinx.io.buffered
import kotlinx.io.files.Path
import kotlinx.io.files.SystemFileSystem
import org.junit.jupiter.api.Assumptions.assumeTrue
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** SC: CountryBoundariesImpl.isInAny. An Ontario position has the countryboundaries ids
 *  "CA-ON" and "CA"; a quest's code matches only an equal id. */
class CountriesTest {
    private val ontario = listOf("CA", "CA-ON")

    @Test fun allCountries() = assertTrue(Countries.All.isEnabledIn(ontario))

    @Test fun noCountriesExceptCanada() =
        assertTrue(Countries.NoneExcept(listOf("US", "CA", "AU")).isEnabledIn(ontario))

    @Test fun noCountriesExceptOntarioOnly() =
        assertTrue(Countries.NoneExcept(listOf("CA-BC", "CA-QC", "CA-ON", "US-WA")).isEnabledIn(ontario))

    @Test fun noCountriesExceptOtherProvince() =
        assertFalse(Countries.NoneExcept(listOf("CA-BC", "CA-QC")).isEnabledIn(ontario))

    @Test fun noCountriesExceptElsewhere() =
        assertFalse(Countries.NoneExcept(listOf("IT", "JP", "AR", "US-OR")).isEnabledIn(ontario))

    @Test fun allCountriesExceptCanada() =
        assertFalse(Countries.AllExcept(listOf("US", "CA")).isEnabledIn(ontario))

    @Test fun allCountriesExceptOntario() =
        assertFalse(Countries.AllExcept(listOf("CA-ON")).isEnabledIn(ontario))

    @Test fun allCountriesExceptElsewhere() =
        assertTrue(Countries.AllExcept(listOf("JP")).isEnabledIn(ontario))

    @Test fun `SC's countryboundaries data gives CA-ON and CA, or DE, for every city`() {
        val file = File(System.getProperty("openquests.scBoundaries") ?: "")
        assumeTrue(file.isFile, "SC boundaries.ser not found at $file")
        val boundaries = SystemFileSystem.source(Path(file.path)).buffered().use { CountryBoundaries.deserializeFrom(it) }
        var checked = 0
        for (city in loadCities(File("config/cities.json"), File("."))) {
            // the bbox centre, when it is inside the city
            val p = city.polygon
            val lat = (p.minLat + p.maxLat) / 2; val lon = (p.minLon + p.maxLon) / 2
            if (!p.contains(lat, lon)) continue
            val ids = boundaries.getIds(longitude = lon, latitude = lat)
            // Ontario, or Germany (SC's data has no German subdivisions, so DE alone)
            assertTrue(ids.toSet() in listOf(setOf("CA-ON", "CA"), setOf("DE")), "${city.id} at $lat,$lon: $ids")
            assertEquals(city.countryCodes.toSet(), ids.toSet(), "${city.id}: countryCodes in config")
            checked++
        }
        println("countryboundaries ids checked for $checked cities")
        assertTrue(checked >= 30)
    }

    @Test fun `registry dump gives the expected gating for Toronto`() {
        val registry = Registry.load(File("data/quests/v64.0.json"))
        val cities = loadCities(File("config/cities.json"), File("."))
        val toronto = cities.single { it.id == "toronto" }
        val statuses = registry.quests.groupingBy { questStatus(it, toronto) }.eachCount()
        val gatedOut = registry.countedQuests.filter { !it.countries.isEnabledIn(toronto.countryCodes) }.map { it.name }
        println("Toronto: $statuses; filter quests not in region: $gatedOut")
        assertEquals(registry.quests.size, statuses.values.sum())
        assertEquals(registry.quests.count { !it.isCounted }, statuses["unsupported"])
        // every city with Toronto's codes has the same quests gated out (German cities differ)
        for (c in cities.filter { it.countryCodes.toSet() == toronto.countryCodes.toSet() }) assertEquals(gatedOut, registry.countedQuests.filter { questStatus(it, c) == "not-in-region" }.map { it.name })
    }
}
