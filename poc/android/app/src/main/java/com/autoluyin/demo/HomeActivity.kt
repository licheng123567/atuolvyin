package com.autoluyin.demo

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.activity.compose.BackHandler
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.view.WindowCompat
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.autoluyin.demo.auth.AppEventBus
import com.autoluyin.demo.auth.AuthEventBus
import com.autoluyin.demo.screens.auth.ForceLogoutActivity
import com.autoluyin.demo.ui.theme.AppTheme
import com.autoluyin.demo.webview.AppWebView
import com.autoluyin.demo.webview.WebNavigationBus

/**
 * v2.0 Task 2 — Compose Hybrid Shell。
 *
 * 流程：MainActivity 完成 preflight（权限/URL/login/self-check）后跳转此 Activity。
 * 4 个底部 tab 各自加载后端托管的 `/app/{tab}` React 页面。
 *
 * 注意：MainActivity 仍是 launcher；它 finish() 之后用户进入 HomeActivity。
 * Task 2 仅骨架，对应 React 页面 Task 3/4 才落地（暂时是 404 — 预期）。
 */
class HomeActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ApiClient.appContext = applicationContext
        // 标准 Android 状态栏（不仿 iOS notch）
        WindowCompat.setDecorFitsSystemWindows(window, true)
        setContent {
            AppTheme {
                AppRoot()
            }
        }
    }
}

/**
 * v0.5.2 — 计算 SAF OpenDocumentTree 的初始入口 URI。
 *
 * 优先级：
 *  1. 已扫到的候选目录（说明该 ROM 真有该路径）
 *  2. AppConfig.runtime.candidateDirs 首条（兜底起点，避免用户跳到 /sdcard 翻）
 *  3. 系统默认（返回 null → SAF 自己决定）
 *
 * URI 格式：content://com.android.externalstorage.documents/document/primary%3A<path>
 * Android 8.0+ 才认 EXTRA_INITIAL_URI（API 26）。低版本直接传 null。
 */
private fun computeInitialPickerUri(ctx: Context): android.net.Uri? {
    if (android.os.Build.VERSION.SDK_INT < android.os.Build.VERSION_CODES.O) return null
    val scan = RecordingScanner.listDirsExistingDetailed(ctx)
    val pathCandidate = scan.existingDirs.firstOrNull()
        ?: AppConfig.runtime.candidateDirs.firstOrNull()
        ?: return null
    return runCatching {
        android.provider.DocumentsContract.buildDocumentUri(
            "com.android.externalstorage.documents",
            "primary:$pathCandidate",
        )
    }.getOrNull()
}

private data class TabSpec(
    val route: String,
    val label: String,
    val icon: ImageVector,
)

private val Tabs = listOf(
    TabSpec("home", "首页", Icons.Filled.Home),
    TabSpec("cases", "案件", Icons.Filled.Folder),
    TabSpec("call-history", "记录", Icons.Filled.Phone),
    TabSpec("profile", "我的", Icons.Filled.Person),
)

@Composable
private fun AppRoot() {
    val navController = rememberNavController()
    val ctx = LocalContext.current

    // v2.4 — 监听 WebNavigationBus：native 端（CallWatcherService / JsBridge.endCall）
    // 触发后渲染全屏 WebView overlay（无 4-tab），承载 in-call / call-end / force-logout。
    var overlayPath by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) {
        WebNavigationBus.navigate.collect { path -> overlayPath = path }
    }
    LaunchedEffect(Unit) {
        WebNavigationBus.exit.collect { overlayPath = null }
    }

    if (overlayPath != null) {
        val path = overlayPath!!
        // 系统返回键：in-call 不允许返回（避免误退通话）；其它路径回到 4-tab 主屏
        BackHandler(enabled = true) {
            if (!path.startsWith("/app/in-call")) {
                overlayPath = null
            }
        }
        WebViewOverlay(path = path)
        return
    }

    // v2.0 Task 8 — 全局监听强制退出事件。
    // SharedFlow replay = 1，所以即便事件早于 collect 触发，本 LaunchedEffect 仍会拿到。
    LaunchedEffect(Unit) {
        AuthEventBus.forceLogout.collect { reason ->
            ctx.startActivity(ForceLogoutActivity.createIntent(ctx, reason))
        }
    }

    // v2.3 Module 2 + v0.5.2 — WebView (Profile 页) 调 Bridge.openRecordingDirPicker 时
    // 通过 AppEventBus 通知本 Activity 启动 SAF 文件夹选择器。
    // 必须在 ComponentActivity / NavBackStackEntry 上下文内 register，所以放在 Composable 里。
    // v0.5.2：传 EXTRA_INITIAL_URI 让选择器直接跳到当前 ROM 的常见录音目录，省得用户翻 /sdcard 找。
    val pickDirLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocumentTree(),
    ) { uri ->
        if (uri != null) {
            runCatching {
                ctx.contentResolver.takePersistableUriPermission(
                    uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION,
                )
            }
            AppConfig.saveUserRecordingDirUri(ctx, uri.toString())
            Toast.makeText(ctx, "已设置录音文件夹", Toast.LENGTH_SHORT).show()
        }
    }
    LaunchedEffect(Unit) {
        AppEventBus.openRecordingDirPicker.collect {
            // 计算 initial URI：优先用 ROM 候选首条（已存在 or 列表首位），跳过则用系统默认
            val initialUri = computeInitialPickerUri(ctx)
            pickDirLauncher.launch(initialUri)
        }
    }

    Scaffold(
        bottomBar = { BottomNavigation4Tabs(navController) },
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = "home",
            modifier = Modifier.padding(padding),
        ) {
            Tabs.forEach { tab ->
                composable(tab.route) { WebViewTabScreen(tab.route, ctx) }
            }
        }
    }
}

@Composable
private fun BottomNavigation4Tabs(navController: NavHostController) {
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route
    NavigationBar {
        Tabs.forEach { tab ->
            val selected = currentRoute == tab.route ||
                backStackEntry?.destination?.hierarchy?.any { it.route == tab.route } == true
            NavigationBarItem(
                selected = selected,
                onClick = {
                    if (currentRoute != tab.route) {
                        navController.navigate(tab.route) {
                            popUpTo(navController.graph.findStartDestination().id) {
                                saveState = true
                            }
                            launchSingleTop = true
                            restoreState = true
                        }
                    }
                },
                icon = { Icon(tab.icon, contentDescription = tab.label) },
                label = { Text(tab.label) },
                colors = NavigationBarItemDefaults.colors(
                    selectedIconColor = MaterialTheme.colorScheme.primary,
                    selectedTextColor = MaterialTheme.colorScheme.primary,
                    unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    indicatorColor = MaterialTheme.colorScheme.primaryContainer,
                ),
            )
        }
    }
}

@Composable
private fun WebViewTabScreen(tab: String, ctx: Context) {
    val backend = AppConfig.backendUrl(ctx)
    if (backend.isNullOrBlank()) {
        // 理论不可达 — MainActivity preflight 已保证 URL 已配置
        Text(
            text = "未配置后端地址，请返回首页重新配置。",
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp),
            style = MaterialTheme.typography.bodyLarge,
        )
        return
    }
    // v2.2 — WebView 加载 React mobile 页面。
    // Chromium 53（Android 6 stock WebView）不支持 <script type="module">，
    // 所以走 dev mode（5173 ESM）会白屏。改为指向 4173 prod 静态服务器
    // （Vite build IIFE bundle + stripModuleAttrs 处理过的 HTML）。
    //   http://host:18000  → http://host:4173
    //   https://api.example.com → 同源（生产部署 backend 自托管 dist）
    val webBase = run {
        val trimmed = backend.trimEnd('/')
        if (trimmed.contains(":18000")) {
            trimmed.replace(":18000", ":4173")
        } else {
            trimmed
        }
    }
    val url = "$webBase/app/$tab"
    AppWebView(url = url, modifier = Modifier.fillMaxSize())
}

/**
 * v2.4 — 全屏 WebView overlay：渲染 React fullscreen 路由（in-call / call-end / force-logout）。
 * 无 4-tab，独占整个屏幕。被 [WebNavigationBus] 触发；React 通过 [JsBridge.exitOverlay] 关闭。
 */
@Composable
private fun WebViewOverlay(path: String) {
    val ctx = LocalContext.current
    val backend = AppConfig.backendUrl(ctx)
    if (backend.isNullOrBlank()) return
    val webBase = run {
        val trimmed = backend.trimEnd('/')
        if (trimmed.contains(":18000")) trimmed.replace(":18000", ":4173") else trimmed
    }
    val cleanPath = if (path.startsWith("/")) path else "/$path"
    AppWebView(url = "$webBase$cleanPath", modifier = Modifier.fillMaxSize())
}
