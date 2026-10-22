package androidx.compose.ui.text.intl

/** Stub of Compose's Locale, with the members SC's data/meta/CountryInfo.kt reads
 *  (userPreferredLocale) and util/locale/FeatureDictionaryUtil.kt (toLanguageTag). Only here so those
 *  files compile unchanged; the engine's locale is the JVM default, pinned to en-CA in Main.kt. */
class Locale(val languageTag: String) {
    val language: String get() = languageTag.substringBefore('-')
    fun toLanguageTag(): String = languageTag

    companion object {
        val current: Locale get() = Locale(java.util.Locale.getDefault().toLanguageTag())
    }
}

/** Stub of Compose's LocaleList: the phone's locale list is the JVM's default locale alone, so
 *  getLanguagesForFeatureDictionary() gives ["en-CA", "en", null] under the engine's pinned locale. */
class LocaleList(val localeList: List<Locale>) {
    companion object {
        val current: LocaleList get() = LocaleList(listOf(Locale.current))
    }
}
