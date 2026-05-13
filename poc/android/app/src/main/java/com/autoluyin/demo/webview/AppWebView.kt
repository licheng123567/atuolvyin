package com.autoluyin.demo.webview

import android.content.Intent
import android.view.View
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import com.autoluyin.demo.AppConfig

/**
 * v2.0 Task 2 — 通用 WebView 容器。
 *
 * 4 个底部 Tab（home / cases / call-history / profile）都通过此 Composable 加载
 * 后端托管的 React 页面 `/app/{tab}`。
 *
 * - JavaScript / DOM Storage / DB 全开（前端 React 路由依赖）
 * - LAYER_TYPE_HARDWARE：Android 6 (MIUI 10) 滑动性能关键
 * - 同域内导航走 WebView；跨域跳系统浏览器（防止外部链接污染 SPA stack）
 * - JWT 通过 `window.__JWT__` 注入；JsBridge 暴露为 `window.AndroidBridge`
 *
 * 注意：4 个 tab 在 Compose NavHost 切换时默认会销毁未选中页面。Task 2 不做
 * 深度优化（用户可感知的"切回时重新加载"成本接受），后续 Task 6 再加 saveable。
 */
@Composable
fun AppWebView(url: String, modifier: Modifier = Modifier) {
    val ctx = LocalContext.current
    val webView = remember {
        WebView(ctx).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            @Suppress("DEPRECATION")
            settings.databaseEnabled = true
            settings.useWideViewPort = true
            settings.loadWithOverviewMode = false
            settings.cacheMode = WebSettings.LOAD_DEFAULT
            // 启用硬件加速（Android 6 性能关键）
            setLayerType(View.LAYER_TYPE_HARDWARE, null)
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(
                    view: WebView,
                    req: WebResourceRequest,
                ): Boolean {
                    val target = req.url.toString()
                    val backend = AppConfig.backendUrl(ctx).orEmpty()
                    return if (backend.isNotEmpty() && target.startsWith(backend)) {
                        false // 同域内导航交给 WebView 自己
                    } else {
                        ctx.startActivity(Intent(Intent.ACTION_VIEW, req.url))
                        true
                    }
                }
            }
            webChromeClient = WebChromeClient()
            // 注入 JsBridge —— 前端通过 window.AndroidBridge.* 调用
            addJavascriptInterface(JsBridge(ctx), "AndroidBridge")
        }
    }

    // JWT 注入：每次 url 变化都重新注入（避免登出后 stale）
    LaunchedEffect(url) {
        val jwt = AppConfig.jwtToken(ctx).orEmpty()
        webView.loadUrl(url)
        webView.evaluateJavascript("window.__JWT__ = '$jwt';", null)
    }

    AndroidView(
        factory = { webView },
        modifier = modifier,
    )
}
