package de.westnordost.streetcomplete.resources

import org.jetbrains.compose.resources.DrawableResource

/** Stub of the Res object that Compose Multiplatform generates for SC's composeResources. Only here so
 *  that the vendored data/meta/CountryInfos.kt and osm/Feature.kt compile unchanged; CountryInfos reads
 *  files through [de.westnordost.streetcomplete.ui.ktx.readYamlOrNull] (also stubbed), and
 *  Feature.iconDrawableResource (UI only, never called) finds no icons. */
object Res

val Res.allDrawableResources: Map<String, DrawableResource> get() = emptyMap()
