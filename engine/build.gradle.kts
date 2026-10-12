plugins {
    // keep in step with the pinned StreetComplete tag (v63.4 uses Kotlin 2.4.0)
    kotlin("jvm") version "2.4.0"
    // only so that the vendored @Serializable annotations compile unchanged
    kotlin("plugin.serialization") version "2.4.0"
    application
}

repositories {
    mavenCentral()
}

dependencies {
    // same version as StreetComplete v63.4
    implementation("org.jetbrains.kotlinx:kotlinx-datetime:0.8.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.9.0")
    // OSM PBF format bindings (crosby.binary); pulls protobuf-java
    implementation("org.openstreetmap.pbf:osmpbf:1.8.0")
    // feature presets (Feature, GeometryType), same version as StreetComplete v63.4
    implementation("de.westnordost:osmfeatures:8.0.0")
    // opening hours parser, same version as StreetComplete v63.4 (AddOpeningHours, AddPostboxCollectionTimes)
    implementation("de.westnordost:osm-opening-hours:0.4.0")
    // country metadata and boundaries (getCountryInfoByLocation), same versions as StreetComplete v63.4
    implementation("com.charleskorn.kaml:kaml:0.104.0")
    implementation("de.westnordost:countryboundaries:3.0.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.11.0") // runBlocking in CountryInfos.kt

    testImplementation(kotlin("test"))
    testImplementation("org.junit.jupiter:junit-jupiter:5.12.2")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

kotlin {
    jvmToolchain(21)
}

// SC's date filters use the system time zone; pin it so a run does not depend on the host.
// The engine refuses to run if a city's timeZone differs from it.
// SC's getFeature() asks osmfeatures in the default locale, as the app does in the phone's; pin it to
// en-CA, the locale whose preset files are bundled (openquests.custom.ScFeatures).
val engineJvmArgs = listOf("-Duser.timezone=America/Toronto", "-Duser.language=en", "-Duser.country=CA")

application {
    mainClass.set("openquests.MainKt")
    applicationName = "sc-open-quests-engine"
    applicationDefaultJvmArgs = listOf(
        "-Xmx24g", // see README "Memory" for the measured peak on Ontario (the area pass needs more)
    ) + engineJvmArgs
}

tasks.test {
    useJUnitPlatform()
    jvmArgs(engineJvmArgs)
    // the Ontario regression test runs the whole engine in-process
    maxHeapSize = "24g"
    // repo root, so that config/ and data/ paths resolve as they do for the CLI
    workingDir = rootProject.projectDir.parentFile
    // -Ppbf=<path> points the Ontario regression test elsewhere; it is skipped if the file is missing
    systemProperty(
        "openquests.pbf",
        providers.gradleProperty("pbf").getOrElse("C:/Users/kk/Code/.osm-data/ontario/ontario-2026-07-16.osm.pbf"),
    )
    // the shared extract store (~/Code/osm-extracts); SnapshotReproductionTest recounts from it
    systemProperty(
        "openquests.osmData",
        providers.gradleProperty("osmData").getOrElse("C:/Users/kk/Code/.osm-data"),
    )
    // SC's country boundaries data (in an SC checkout); the test using it is skipped without it
    systemProperty(
        "openquests.scBoundaries",
        providers.gradleProperty("scBoundaries").getOrElse(
            "C:/Users/kk/AppData/Local/Temp/sc-v63.4/app/src/commonMain/composeResources/files/boundaries.ser"),
    )
    testLogging {
        events("passed", "skipped", "failed")
        showStandardStreams = true
        exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL
    }
}
