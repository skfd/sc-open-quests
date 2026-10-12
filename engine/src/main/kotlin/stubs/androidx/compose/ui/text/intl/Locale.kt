package androidx.compose.ui.text.intl

/** Stub of Compose's Locale, with the members SC's data/meta/CountryInfo.kt reads
 *  (userPreferredLocale). Only here so that file compiles unchanged; the engine never calls it. */
class Locale(val languageTag: String) {
    val language: String get() = languageTag.substringBefore('-')

    companion object {
        val current: Locale get() = Locale(java.util.Locale.getDefault().toLanguageTag())
    }
}
