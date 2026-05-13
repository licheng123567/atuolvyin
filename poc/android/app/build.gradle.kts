plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    // v2.0 Task 1 — Compose Compiler Plugin（Kotlin 2.0+ 取代旧的 kotlinCompilerExtensionVersion）
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.autoluyin.demo"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.autoluyin.demo"
        minSdk = 23          // v1.9.9 — 适配 MIUI 10/Android 6 测试机（PRD：通话录音目标平台）
        targetSdk = 29       // v1.9.9 — MIUI 10 兼容打包 (Android 10 API)。正式版回 33+
        versionCode = 2
        versionName = "0.2.0"
        // 后端地址不再硬编码，APK 首次启动由用户输入或扫激活码注入；
        // 见 AppConfig.kt / MainActivity.showBackendUrlDialog。
        buildConfigField("String", "MIPUSH_APP_ID", "\"\"")
        buildConfigField("String", "MIPUSH_APP_KEY", "\"\"")
    }
    // v1.9.9 — MIUI 10 / Android 8 era 部分机型只识别 v1 (JAR) 签名，
    // 默认 AGP 8.x debug 仅 v2，会导致「解析软件包出现了问题」。开启双签。
    signingConfigs {
        getByName("debug") {
            storeFile = file("${System.getProperty("user.home")}/.android/debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
            enableV1Signing = true
            enableV2Signing = true
        }
    }
    buildTypes {
        getByName("debug") {
            signingConfig = signingConfigs.getByName("debug")
        }
        release {
            isMinifyEnabled = false
        }
    }
    buildFeatures {
        viewBinding = true
        buildConfig = true
        compose = true // v2.0 Task 1 — 引入 Jetpack Compose + Material 3
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    testOptions {
        unitTests.all {
            it.useJUnitPlatform()
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    // v2.2 Module A — SAF 手选录音目录 (DocumentFile.fromTreeUri)
    implementation("androidx.documentfile:documentfile:1.0.1")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.work:work-runtime-ktx:2.9.1")

    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-moshi:2.11.0")
    implementation("com.squareup.moshi:moshi-kotlin:1.15.1")

    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")

    // v2.0 Task 1 — Jetpack Compose BOM + Material 3
    // 2024.06 BOM 对 minSdk 23 友好，Material3 1.2.x 系列
    implementation(platform("androidx.compose:compose-bom:2024.06.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended") // v2.0 Task 2 — 4 tab 图标
    implementation("androidx.activity:activity-compose:1.9.0")
    // v2.0 Task 6 — RealtimeCallViewModel 用 viewModels() + AndroidViewModel
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    // v2.0 Task 6 — ComponentActivity.supportFragmentManager（PostCallTagDialog 仍是 DialogFragment）
    implementation("androidx.fragment:fragment-ktx:1.8.2")
    debugImplementation("androidx.compose.ui:ui-tooling")

    // v2.0 Task 2 — Navigation for Compose（4 tab 切换）
    implementation("androidx.navigation:navigation-compose:2.7.7")

    // CardView for SuggestionCardView
    implementation("androidx.cardview:cardview:1.0.0")

    // CameraX + ML Kit for QR scan (Sprint 12.4)
    implementation("androidx.camera:camera-camera2:1.3.4")
    implementation("androidx.camera:camera-lifecycle:1.3.4")
    implementation("androidx.camera:camera-view:1.3.4")
    implementation("com.google.mlkit:barcode-scanning:17.3.0")

    // JUnit 5 for unit tests
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.3")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")

    // JUnit 4 for Robolectric
    testImplementation("junit:junit:4.13.2")

    // Robolectric for Android unit tests
    testImplementation("org.robolectric:robolectric:4.12.1")

    // JSON library for unit tests
    testImplementation("org.json:json:20231013")

    // MockK for unit tests
    testImplementation("io.mockk:mockk:1.13.10")
}
