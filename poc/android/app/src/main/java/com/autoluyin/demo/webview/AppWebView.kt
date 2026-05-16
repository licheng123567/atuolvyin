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
            // v2.2 — debug build 开 chrome://inspect 远程调试，方便真机抓白屏
            WebView.setWebContentsDebuggingEnabled(true)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            @Suppress("DEPRECATION")
            settings.databaseEnabled = true
            settings.useWideViewPort = true
            settings.loadWithOverviewMode = false
            // v2.2 — dev 期强制不走 cache，确保 Vite 端 hot reload 后总是拉最新 bundle。
            // 生产 build 应改回 LOAD_DEFAULT。
            settings.cacheMode = WebSettings.LOAD_NO_CACHE
            // 启用硬件加速（Android 6 性能关键）
            setLayerType(View.LAYER_TYPE_HARDWARE, null)
            webViewClient = object : WebViewClient() {
                // v2.2 — onPageStarted 注入 __JWT__：保证 React 主 JS 执行前 token 已可读
                override fun onPageStarted(view: WebView, url: String?, favicon: android.graphics.Bitmap?) {
                    val jwt = AppConfig.jwtToken(ctx).orEmpty()
                    val backend = AppConfig.backendUrl(ctx).orEmpty()
                    view.evaluateJavascript(
                        "window.__JWT__='${jwt}'; window.__BACKEND__='${backend}';",
                        null,
                    )
                }

                override fun shouldOverrideUrlLoading(
                    view: WebView,
                    req: WebResourceRequest,
                ): Boolean {
                    // v2.2 — same-host 判定（不再死盯 backend URL，因为 frontend 走 :5173 不同端口）
                    val target = req.url.toString()
                    val backend = AppConfig.backendUrl(ctx).orEmpty()
                    val backendHost = runCatching { android.net.Uri.parse(backend).host }.getOrNull()
                    val targetHost = req.url.host
                    return if (backendHost != null && targetHost == backendHost) {
                        false // 同 host 内导航（含 :5173 / :18000 / 其他端口）交给 WebView
                    } else {
                        ctx.startActivity(Intent(Intent.ACTION_VIEW, req.url))
                        true
                    }
                }

                override fun onReceivedError(
                    view: WebView,
                    req: WebResourceRequest,
                    err: android.webkit.WebResourceError,
                ) {
                    android.util.Log.e(
                        "AutoluyinWV",
                        "WebView err url=${req.url} code=${err.errorCode} desc=${err.description}",
                    )
                }
            }
            webChromeClient = object : WebChromeClient() {
                override fun onConsoleMessage(msg: android.webkit.ConsoleMessage): Boolean {
                    android.util.Log.i(
                        "AutoluyinWV",
                        "console[${msg.messageLevel()}] ${msg.message()} (${msg.sourceId()}:${msg.lineNumber()})",
                    )
                    return true
                }
            }
            // 注入 JsBridge —— 前端通过 window.AndroidBridge.* 调用
            addJavascriptInterface(JsBridge(ctx), "AndroidBridge")
        }
    }

    LaunchedEffect(url) {
        webView.loadUrl(url)
    }

    AndroidView(
        factory = { webView },
        modifier = modifier,
    )
}
