package com.autoluyin.demo.capability

import android.os.Build

/**
 * v2.1 — 客户端 ROM/Android 探测（纯 Build.* 字段采集）。
 *
 * 注意：本地不做 capability 判定 — 静态矩阵在后端
 * (services/device_capability.py)，避免双端漂移。
 */
data class DeviceInfo(
    val manufacturer: String,
    val model: String,
    val androidVersion: String,
    val brand: String,
)

object DeviceCapabilityProbe {
    fun collect(): DeviceInfo = DeviceInfo(
        manufacturer = (Build.MANUFACTURER ?: "").trim(),
        model = (Build.MODEL ?: "").trim(),
        androidVersion = (Build.VERSION.RELEASE ?: "").trim(),
        brand = (Build.BRAND ?: "").trim(),
    )
}
