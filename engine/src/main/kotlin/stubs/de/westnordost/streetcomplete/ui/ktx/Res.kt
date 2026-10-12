package de.westnordost.streetcomplete.ui.ktx

import de.westnordost.streetcomplete.resources.Res

/** Stub of SC's ui/ktx/Res.kt readBytesOrNull (which reads composeResources through Compose). The
 *  engine bundles the files it needs under src/main/resources/sc/ (vendored by sync-sc.ps1), so
 *  "files/country_metadata/CA.yml" is the classpath resource "/sc/country_metadata/CA.yml". Null
 *  for a file that is not bundled, as SC returns null for a region without a metadata file. */
@Suppress("RedundantSuspendModifier", "UnusedReceiverParameter")
suspend fun Res.readBytesOrNull(path: String): ByteArray? =
    Res::class.java.getResourceAsStream("/sc/" + path.removePrefix("files/"))?.use { it.readBytes() }
