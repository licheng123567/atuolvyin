plugins {
    id("com.android.application") version "8.5.2" apply false
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
    // v2.0 Task 1 — Kotlin 2.0+ 用 Compose Compiler Plugin 取代 kotlinCompilerExtensionVersion
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.21" apply false
}
