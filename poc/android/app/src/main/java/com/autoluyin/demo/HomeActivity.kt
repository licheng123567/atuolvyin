package com.autoluyin.demo

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
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
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
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
import com.autoluyin.demo.auth.AuthEventBus
import com.autoluyin.demo.screens.auth.ForceLogoutActivity
import com.autoluyin.demo.ui.theme.AppTheme
import com.autoluyin.demo.webview.AppWebView

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

    // v2.0 Task 8 — 全局监听强制退出事件。
    // SharedFlow replay = 1，所以即便事件早于 collect 触发，本 LaunchedEffect 仍会拿到。
    LaunchedEffect(Unit) {
        AuthEventBus.forceLogout.collect { reason ->
            ctx.startActivity(ForceLogoutActivity.createIntent(ctx, reason))
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
    val url = "${backend.trimEnd('/')}/app/$tab"
    AppWebView(url = url, modifier = Modifier.fillMaxSize())
}
