plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.autoluyin.demo"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.autoluyin.demo"
        minSdk = 26          // Android 8.0 起可用；MIUI 主流机型已远超
        targetSdk = 33       // 暂保 33 以避免 Android 14 后台限制升级；正式版按需提到 35
        versionCode = 1
        versionName = "0.1.0"
        // 后端地址不再硬编码，APK 首次启动由用户输入或扫激活码注入；
        // 见 AppConfig.kt / MainActivity.showBackendUrlDialog。
        buildConfigField("String", "MIPUSH_APP_ID", "\"\"")
        buildConfigField("String", "MIPUSH_APP_KEY", "\"\"")
    }
    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    buildFeatures {
        viewBinding = true
        buildConfig = true
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

    // CardView for SuggestionCardView
    implementation("androidx.cardview:cardview:1.0.0")

    // JUnit 5 for unit tests
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.3")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
