package com.autoluyin.demo.webview

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * v2.4 — Native → React WebView 路由总线
 *
 * 触发场景：
 *   1. CallWatcherService.startDialAndHeartbeat 成功 → /app/in-call/{server_call_id}
 *   2. CallWatcherService.matchAndUpload 完成 → /app/call-end/{server_call_id}
 *   3. JsBridge.endCall 触发 → /app/call-end/{server_call_id}
 *
 * 消费者：HomeActivity AppRoot 收到 navigate 后渲染全屏 WebView 覆盖 4-tab；
 *        收到 exit 后销毁覆盖回到正常 4-tab 模式。
 *
 * 与 [com.autoluyin.demo.auth.AppEventBus] 不同 —— AppEventBus 是 native 内部事件
 * (SAF picker)，本 bus 专管 WebView 路由。
 */
object WebNavigationBus {
    private val _navigate = MutableSharedFlow<String>(extraBufferCapacity = 8, replay = 1)
    val navigate: SharedFlow<String> = _navigate.asSharedFlow()

    private val _exit = MutableSharedFlow<Unit>(extraBufferCapacity = 4)
    val exit: SharedFlow<Unit> = _exit.asSharedFlow()

    /** path 必须以 /app/... 开头（不带 base URL，由 HomeActivity 拼）。 */
    fun navigateTo(reactPath: String) {
        _navigate.tryEmit(reactPath)
    }

    fun exitOverlay() {
        _exit.tryEmit(Unit)
    }
}
