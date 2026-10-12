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
}

kotlin {
    jvmToolchain(21)
}

application {
    mainClass.set("openquests.SpikeKt")
    applicationDefaultJvmArgs = listOf(
        "-Xmx12g", // peak heap was ~7.2 GB for Ontario; a 32 GB heap only made GC lazier (18 GB RSS, slower)
        // SC's date filters use the system time zone; pin it so a run does not depend on the host
        "-Duser.timezone=America/Toronto",
    )
}
