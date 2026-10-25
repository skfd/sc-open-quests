package de.westnordost.streetcomplete.ui.ktx

import com.charleskorn.kaml.Yaml
import de.westnordost.streetcomplete.resources.Res
import kotlinx.serialization.decodeFromString
import java.io.InputStream

/** Stub of SC's ui/ktx/Res.kt (which reads composeResources through Compose). The engine bundles the
 *  files it needs under src/main/resources/sc/ (vendored by sync-sc.ps1), so
 *  "files/country_metadata/CA.yml" is the classpath resource "/sc/country_metadata/CA.yml". Null for
 *  a region SC has no metadata file for, as SC returns null then (CountryInfos skips the id). A
 *  country_metadata file that SC ships but the bundle lacks is an error, not null: CountryInfos would
 *  silently fall back to default.yml. */
@Suppress("RedundantSuspendModifier", "UnusedReceiverParameter")
suspend fun Res.readBytesOrNull(path: String): ByteArray? =
    readBundled(path, { countryMetadataCodes }) { Res::class.java.getResourceAsStream(it) }

/** SC: `readYaml` in a try/catch of MissingResourceException; the same decode, kaml on the bytes. */
@Suppress("RedundantSuspendModifier")
suspend inline fun <reified T> Res.readYamlOrNull(path: String, yaml: Yaml = Yaml.default): T? {
    val bytes = readBytesOrNull(path) ?: return null
    return yaml.decodeFromString<T>(bytes.decodeToString())
}

private const val COUNTRY_METADATA = "files/country_metadata/"

/** The region codes SC ships a country_metadata yml for (sc/country_metadata.index, which sync-sc.ps1
 *  writes from SC's directory listing): "CA", "CA-ON", "default", ... */
val countryMetadataCodes: Set<String> by lazy {
    val stream = Res::class.java.getResourceAsStream("/sc/country_metadata.index")
        ?: error("missing resource sc/country_metadata.index; rerun engine/sync-sc.ps1")
    stream.bufferedReader().use { r -> r.readLines().filter { it.isNotBlank() }.toSet() }
}

/** [path] ("files/...") read from the classpath through [open]; null if not bundled, unless it is a
 *  country_metadata file whose code is in [codes]. */
internal fun readBundled(path: String, codes: () -> Set<String>, open: (String) -> InputStream?): ByteArray? {
    val bytes = open("/sc/" + path.removePrefix("files/"))?.use { it.readBytes() }
    if (bytes == null && path.startsWith(COUNTRY_METADATA) && path.endsWith(".yml")) {
        val code = path.removePrefix(COUNTRY_METADATA).removeSuffix(".yml")
        check(code !in codes()) {
            "SC ships country_metadata/$code.yml but the engine's bundle lacks it; rerun engine/sync-sc.ps1"
        }
    }
    return bytes
}
