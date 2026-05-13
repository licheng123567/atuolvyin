package com.autoluyin.demo.auth

import android.util.Log
import okhttp3.Interceptor
import okhttp3.Response
import org.json.JSONObject

/**
 * v2.0 Task 8 — OkHttp 后置拦截器：检测 401 + 鉴权码 → 触发 [AuthEventBus.fireForceLogout]。
 *
 * 链顺序约定（见 [com.autoluyin.demo.ApiClient]）：
 *  1. AuthInterceptor    （已有，前置加 Bearer token）
 *  2. AuthErrorInterceptor（本类，后置识别 401 错误码）
 *
 * 关键约束：
 *  - **绝不在此处 startActivity**：Interceptor 在子线程 + 没 Activity Context，会 crash。
 *    通过 EventBus 广播，由前台 Activity 的 LaunchedEffect 接到后跳转。
 *  - 用 [Response.peekBody] 避免消费 body，让 Retrofit converter 仍能正常读取错误响应。
 *  - 仅 [TRIGGER_CODES] 白名单触发；其它 401（例如业务自定义鉴权错误）不强制踢出。
 */
class AuthErrorInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val response = chain.proceed(chain.request())
        if (response.code == 401) {
            val body = runCatching { response.peekBody(PEEK_BYTES).string() }.getOrDefault("")
            val (code, message) = parseErrorBody(body)
            if (code in TRIGGER_CODES) {
                Log.w(TAG, "auth failure code=$code msg=$message url=${response.request.url}")
                AuthEventBus.fireForceLogout(code, message)
            } else {
                Log.d(TAG, "401 ignored (code=$code) url=${response.request.url}")
            }
        }
        return response
    }

    /**
     * 容错解析多种错误体形态：
     *   - FastAPI 标准：{"detail": {"code": "...", "message": "..."}}
     *   - FastAPI 简单：{"detail": "..."}
     *   - 自定义顶层：{"code": "...", "message": "..."}
     */
    private fun parseErrorBody(raw: String): Pair<String, String?> {
        if (raw.isBlank()) return DEFAULT_CODE to null
        return runCatching {
            val obj = JSONObject(raw)
            val detail = obj.opt("detail")
            when (detail) {
                is JSONObject -> {
                    val c = detail.optString("code").takeIf { it.isNotBlank() } ?: DEFAULT_CODE
                    val m = detail.optString("message").takeIf { it.isNotBlank() }
                    c to m
                }
                is String -> DEFAULT_CODE to detail.takeIf { it.isNotBlank() }
                else -> {
                    val c = obj.optString("code").takeIf { it.isNotBlank() } ?: DEFAULT_CODE
                    val m = obj.optString("message").takeIf { it.isNotBlank() }
                    c to m
                }
            }
        }.getOrDefault(DEFAULT_CODE to null)
    }

    companion object {
        private const val TAG = "AuthErrorIntcpt"
        private const val PEEK_BYTES = 2048L
        private const val DEFAULT_CODE = "ERR_UNAUTHORIZED"

        /** 触发强制退出的错误码白名单。 */
        private val TRIGGER_CODES = setOf(
            "ERR_SESSION_EVICTED",
            "ERR_INVALID_TOKEN",
            "ERR_TOKEN_EXPIRED",
        )
    }
}
