package com.autoluyin.demo.auth

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * v2.0 Task 8 — 全局鉴权事件总线（process-wide 单例）。
 *
 * 触发方：
 *  - [com.autoluyin.demo.auth.AuthErrorInterceptor]：OkHttp 子线程拿到 401 → fireForceLogout
 *  - [com.autoluyin.demo.webview.JsBridge.notifyAuthError]：前端 fetch 401 → fireForceLogout
 *
 * 监听方：
 *  - [com.autoluyin.demo.HomeActivity] AppRoot Composable LaunchedEffect
 *  - 其它前台 Activity 可按需 collect（DialRequestActivity / RealtimeCallActivity / CallEndMarkActivity 暂不
 *    强制接入：HomeActivity 总在 task back stack 里，跳 ForceLogoutActivity 时会带 CLEAR_TASK 卸掉所有栈帧）
 *
 * 设计要点：
 *  - 单例对象 + SharedFlow，跨 Activity / Service / 子线程都能广播
 *  - replay = 1：后注册的 collector 也能拿到最近一次事件，避免 Interceptor 早于 Activity 启动而漏触发
 *  - extraBufferCapacity = 4：防止快速连续 401 把 tryEmit 撑爆
 *  - [reset] 由 [com.autoluyin.demo.screens.auth.ForceLogoutActivity] onCreate 调用，清 replay 缓存防止
 *    旋转屏 / Activity 重建时重复触发跳转
 */
object AuthEventBus {
    private val _forceLogout = MutableSharedFlow<ForceLogoutReason>(
        replay = 1,
        extraBufferCapacity = 4,
    )
    val forceLogout: SharedFlow<ForceLogoutReason> = _forceLogout.asSharedFlow()

    /** 触发强制退出。reason 来自后端 detail.message 或前端默认文案。 */
    fun fireForceLogout(code: String, message: String?) {
        _forceLogout.tryEmit(ForceLogoutReason(code, message))
    }

    /** 清 replay 缓存。仅 ForceLogoutActivity onCreate 调用，避免重复跳转。 */
    @OptIn(ExperimentalCoroutinesApi::class)
    fun reset() {
        _forceLogout.resetReplayCache()
    }
}

/**
 * 强制退出事件 payload。
 *
 * @property code 错误码：ERR_SESSION_EVICTED / ERR_INVALID_TOKEN / ERR_TOKEN_EXPIRED
 * @property message 后端 detail.message 或 null（null 时 ForceLogoutScreen 用默认文案）
 */
data class ForceLogoutReason(
    val code: String,
    val message: String?,
)
