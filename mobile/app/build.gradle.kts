plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.taskflow.mobile"
    compileSdk = 36
    buildToolsVersion = "36.1.0"

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "com.taskflow.mobile"
        minSdk = 24
        targetSdk = 36
        versionCode = 1
        versionName = "0.1"
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}
