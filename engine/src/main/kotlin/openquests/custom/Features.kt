package openquests.custom

import de.westnordost.osmfeatures.Feature
import de.westnordost.osmfeatures.FeatureDictionary
import de.westnordost.streetcomplete.data.osm.mapdata.Element
import de.westnordost.streetcomplete.util.ktx.getFeature
import kotlinx.io.files.SystemFileSystem
import java.nio.file.Files

/**
 * SC's feature dictionary, as the app hands it to the quest registry
 * (`{ featureDictionaryLazy.value.getFeature(it) }` in CommonModule): osmfeatures over SC's own
 * preset files, queried in the languages of the phone's locale list (since v64
 * `getLanguagesForFeatureDictionary()`, vendored; the stubbed Compose LocaleList holds the JVM's default
 * locale, then "en", then null). The engine pins that locale to en-CA (see Main.kt), and only the files
 * en-CA reads are bundled (src/main/resources/sc/osmfeatures/default, vendored by sync-sc.ps1).
 */
object ScFeatures {
    /** the locale the app is assumed to run in; the presets bundled are the ones it reads */
    const val LANGUAGE = "en-CA"
    private val FILES = listOf("presets.json", "en.json", "en-CA.json")

    private val dictionary: FeatureDictionary by lazy {
        // osmfeatures on the JVM reads from a directory; unpack the bundled presets into a temporary one
        val dir = Files.createTempDirectory("sc-osmfeatures")
        for (f in FILES) {
            val input = ScFeatures::class.java.getResourceAsStream("/sc/osmfeatures/default/$f")
                ?: error("missing resource sc/osmfeatures/default/$f")
            input.use { Files.copy(it, dir.resolve(f)) }
        }
        val d = FeatureDictionary.create(SystemFileSystem, dir.toString())
        for (f in FILES) Files.delete(dir.resolve(f))
        Files.delete(dir)
        d
    }

    /** SC's getFeature(element). osmfeatures fills its per-language indexes lazily in plain HashMaps,
     *  so calls are serialized; the quests ask only for elements that already passed their filter. */
    fun getFeature(element: Element): Feature? = synchronized(this) { dictionary.getFeature(element) }
}
