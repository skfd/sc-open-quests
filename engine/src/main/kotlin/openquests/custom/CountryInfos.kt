package openquests.custom

import de.westnordost.streetcomplete.data.meta.CountryInfo
import de.westnordost.streetcomplete.data.meta.CountryInfos
import de.westnordost.streetcomplete.data.osm.mapdata.LatLon
import de.westnordost.streetcomplete.resources.Res
import de.westnordost.streetcomplete.util.countryboundaries.CountryBoundaries
import de.westnordost.streetcomplete.util.countryboundaries.CountryBoundariesImpl
import kotlinx.io.asSource
import kotlinx.io.buffered
import java.util.concurrent.ConcurrentHashMap

/**
 * SC's country metadata for a position, as the app hands it to the quest registry
 * (`{ countryInfos.get(countryBoundaries, it) }` in AndroidModule2): the region ids SC's
 * countryboundaries data gives for the position (smallest first, e.g. CA-ON, CA), each region's
 * yml in country_metadata/, then default.yml. CountryInfos, CountryBoundaries and the data files are
 * SC's own (vendored by sync-sc.ps1; only the CA, CA-ON and default yml are bundled, so a position
 * outside Ontario reads default.yml only, and no quest there is counted).
 *
 * CountryInfos caches in a plain HashMap; calls are serialized per id list, then cached here.
 */
object ScCountryInfos {
    private val countryInfos = CountryInfos(Res)

    val countryBoundaries: CountryBoundaries by lazy {
        val input = ScCountryInfos::class.java.getResourceAsStream("/sc/boundaries.ser")
            ?: error("missing resource sc/boundaries.ser")
        CountryBoundariesImpl(input.asSource().buffered().use {
            de.westnordost.countryboundaries.CountryBoundaries.deserializeFrom(it)
        })
    }

    private val byIds = ConcurrentHashMap<List<String>, CountryInfo>()

    fun get(ids: List<String>): CountryInfo =
        byIds[ids] ?: synchronized(this) { byIds.getOrPut(ids) { countryInfos.get(ids) } }

    /** SC's getCountryInfoByLocation */
    fun getCountryInfoByLocation(position: LatLon): CountryInfo = get(countryBoundaries.getIds(position))
}
