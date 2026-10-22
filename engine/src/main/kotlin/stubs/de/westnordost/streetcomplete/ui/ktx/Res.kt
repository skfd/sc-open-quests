package de.westnordost.streetcomplete.ui.ktx

import com.charleskorn.kaml.Yaml
import de.westnordost.streetcomplete.resources.Res
import kotlinx.serialization.decodeFromString

/** Stub of SC's ui/ktx/Res.kt (which reads composeResources through Compose). The engine bundles the
 *  files it needs under src/main/resources/sc/ (vendored by sync-sc.ps1), so
 *  "files/country_metadata/CA.yml" is the classpath resource "/sc/country_metadata/CA.yml". Null for
 *  a file that is not bundled, as SC returns null for a region without a metadata file. */
@Suppress("RedundantSuspendModifier", "UnusedReceiverParameter")
suspend fun Res.readBytesOrNull(path: String): ByteArray? =
    Res::class.java.getResourceAsStream("/sc/" + path.removePrefix("files/"))?.use { it.readBytes() }

/** SC: `readYaml` in a try/catch of MissingResourceException; the same decode, kaml on the bytes. */
@Suppress("RedundantSuspendModifier")
suspend inline fun <reified T> Res.readYamlOrNull(path: String, yaml: Yaml = Yaml.default): T? {
    val bytes = readBytesOrNull(path) ?: return null
    return yaml.decodeFromString<T>(bytes.decodeToString())
}
