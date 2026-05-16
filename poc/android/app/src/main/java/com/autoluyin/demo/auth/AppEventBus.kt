package com.autoluyin.demo.auth

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * v2.3 Module 2 — App-wide event bus，独立于 [AuthEventBus]。
 *
 * 用于 WebView JsBridge 触发的、需要 Activity 持有 launcher 的事件（如 SAF 文件夹选择器）。
 * JsBridge 任意线程 tryEmit；HomeActivity AppRoot Composable LaunchedEffect 监听。
 */
object AppEventBus {
    private val _openRecordingDirPicker = MutableSharedFlow<Unit>(extraBufferCapacity = 4)
    val openRecordingDirPicker: SharedFlow<Unit> = _openRecordingDirPicker.asSharedFlow()

    fun fireOpenRecordingDirPicker() {
        _openRecordingDirPicker.tryEmit(Unit)
    }
}
