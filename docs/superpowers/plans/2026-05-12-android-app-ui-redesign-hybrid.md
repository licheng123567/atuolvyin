# Sprint v2.0 — Android App UI Hybrid Rewrite (1:1 app-agent.html)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement task-by-task. Each task block tracks with `- [ ]` checkboxes.

**Goal:** 按 `ui/app-agent.html` 设计稿 1:1 重写 Android App UI（9 屏），采用 **WebView + Compose 混合架构**：静态屏（首页/列表/详情/记录/个人）由 React 移动版 + `design-system.css` 渲染于 WebView，与设计稿同一份 CSS 保证像素级吻合；实时通话屏（拨打请求/通话中/通话结束）用 Jetpack Compose 原生重写以稳定承载 WebSocket / 风控状态机 / 来电锁屏唤醒。

**目标平台**：Android 6.0+（MIUI 10 系），minSdk=23，targetSdk=29，符合 PRD § 8.4 兼容性矩阵。

**Architecture:**
- 单 Activity 模式：`MainActivity` 持有原生 Compose `Scaffold` + Bottom Tab Bar
- 4 个 Tab：`Home / Cases / CallHistory / Profile` — 内嵌 `WebViewFragment` 加载对应 React 路由
- 5 个非 Tab 场景：
  - 全屏 Compose：`DialRequestActivity` / `RealtimeCallActivity` (重写) / `CallEndMarkActivity`
  - 全屏 WebView：`CaseDetailActivity`（从案件列表 push，仍走 WebView）
  - 全局拦截器：`ForceLogoutDialog`（被 ApiClient 401/异地登录响应触发）
- 数据流：WebView 走 `useCustom`（fetch） → 后端；Compose 走 Retrofit/WS → 后端；二者 token 通过 `JsBridge.getJwt()` 共享

**Tech Stack:**
- 原生：Kotlin + Jetpack Compose + Material 3 + ViewModel + Hilt
- WebView 内：React + Refine.dev + `design-system.css` token，路由 `/app/*`
- 通信：`@JavascriptInterface JsBridge`（auth/nav/dial/scan/push 事件）
- 测试：Compose UI test + Robolectric + 真机截图对比 app-agent.html

---

## ⚠️ Notes (read before any task)

**1. 不要直接套 `ui/app-agent.html` 跑 WebView**
该文件是静态设计稿（无 fetch、硬编码数据）。我们要把它的视觉**移植到 React** (`frontend/src/pages/app/`)，复用 `ui/assets/design-system.css` 的 token，然后 WebView 加载 React 路由。这样既像素级吻合设计稿又能拿后端数据。

**2. RealtimeCallActivity 重写不要破坏现有 AudioStreamClient / WS 流**
现有 `AudioStreamClient.kt`（v1.9.9 已修 baseUrl 派生）+ `useCallSocket` + 风控 L1/L2/L3 全保留；只重写 UI 层。

**3. iPhone 风格 frame 不要照搬**
设计稿用 `iPhone 14` 边框只是为了演示。Android App 用全屏布局；底部 tab bar、顶部 status bar 用 Android 标准（不仿 iOS notch）。

**4. tab 切换不要 reload WebView**
4 个 tab 的 WebView 在 `MainActivity` 持久驻留（用 `WebView.saveState()` / `restoreState()` 或多个 WebView 实例 with `visibility=GONE`），切回来要保持滚动位置和登录态。

**5. Compose 与 WebView 共享 token**
JWT 存 SharedPreferences（已有 `AppConfig.saveJwtToken`）。Compose 走 OkHttp `AuthInterceptor`（已有）；WebView 启动时通过 `evaluateJavascript("window.__JWT__ = ...")` 注入，React 端 `axiosClient` 优先读 `window.__JWT__`，回退到 cookie。

---

## File Map

| File | Action | 责任 |
|---|---|---|
| **基础架构** | | |
| `poc/android/app/build.gradle.kts` | Modify | 加 Compose + Material 3 + Hilt + Coil 依赖；保持 minSdk=23 |
| `poc/android/app/src/main/java/com/autoluyin/demo/ui/theme/AppTheme.kt` | Create | 翻译 `design-system.css` token 为 Compose `MaterialTheme`（色板 + Typography + Shape） |
| `poc/android/app/src/main/java/com/autoluyin/demo/MainActivity.kt` | Rewrite | 单 Activity + Compose Scaffold + BottomNavigation 4 tabs |
| `poc/android/app/src/main/java/com/autoluyin/demo/webview/AppWebView.kt` | Create | 封装 `WebView` Composable，注入 JsBridge + 共享 cookie / JWT |
| `poc/android/app/src/main/java/com/autoluyin/demo/webview/JsBridge.kt` | Create | `@JavascriptInterface`：getJwt / dial / scan / push 订阅 / 强制退出回调 |
| **WebView 部分（5 屏）** | | |
| `frontend/src/pages/app/home/index.tsx` | Create | Screen 1 工作台首页（greeting + summary card + 待办列表） |
| `frontend/src/pages/app/cases/index.tsx` | Create | Screen 5 案件列表 |
| `frontend/src/pages/app/cases/[id].tsx` | Create | Screen 6 案件详情 |
| `frontend/src/pages/app/call-history/index.tsx` | Create | Screen 7 通话记录（实际可复用 PC 版逻辑，UI 改 mobile） |
| `frontend/src/pages/app/profile/index.tsx` | Create | Screen 8 个人信息 + 设置入口 |
| `frontend/src/pages/app/_layout.tsx` | Create | 移动布局壳：去掉 PC 侧边栏，加底部留白避让 Tab Bar |
| `frontend/src/router/appRoutes.tsx` | Create | 注册 `/app/*` 路由 + 移动鉴权拦截 |
| `frontend/src/lib/jsBridge.ts` | Create | `window.AndroidBridge` 类型声明 + 兜底实现（浏览器调试用） |
| `ui/assets/design-system-mobile.css` | Create | 在 `design-system.css` 基础上加 mobile-only token（如 tap target ≥ 44px） |
| **Compose 原生（3 屏）** | | |
| `poc/android/app/src/main/java/com/autoluyin/demo/screens/dial/DialRequestScreen.kt` | Create | Screen 2 全屏拨号请求（蓝渐变 + 80px 头像 + 倒计时环 + 大按钮） |
| `poc/android/app/src/main/java/com/autoluyin/demo/screens/dial/DialRequestActivity.kt` | Create | 入口 Activity，PushReceiver 触发 |
| `poc/android/app/src/main/java/com/autoluyin/demo/screens/realtime/RealtimeCallScreen.kt` | Create | Screen 3 通话中 Compose UI |
| `poc/android/app/src/main/java/com/autoluyin/demo/realtime/RealtimeCallActivity.kt` | Refactor | 从 XML/View 重写到 Compose，保留 AudioStreamClient 接入 |
| `poc/android/app/src/main/java/com/autoluyin/demo/screens/postcall/CallEndMarkScreen.kt` | Create | Screen 4 通话结束标记（AI 分析卡 + 快速标签单选 + 承诺日期） |
| `poc/android/app/src/main/java/com/autoluyin/demo/screens/postcall/CallEndMarkActivity.kt` | Create | 接 PhoneStateReceiver IDLE 触发 |
| **全局** | | |
| `poc/android/app/src/main/java/com/autoluyin/demo/screens/dialogs/ForceLogoutDialog.kt` | Create | Screen 9 强制退出 Composable Dialog |
| `poc/android/app/src/main/java/com/autoluyin/demo/Api.kt` | Modify | AuthInterceptor 收到 401/3009 → broadcast LocalBroadcast → MainActivity 弹 ForceLogout |
| **测试 + Playbook** | | |
| `poc/android/app/src/androidTest/java/.../DialRequestScreenTest.kt` | Create | Compose UI test：倒计时 / 按钮 / 头像 |
| `poc/android/app/src/androidTest/java/.../JsBridgeTest.kt` | Create | Bridge 单测：getJwt / dial / scan |
| `frontend/tests/playwright/app-home.spec.ts` | Create | mobile viewport 截图回归（与 `ui/app-agent.html` Screen 1 对比） |
| `docs/QA_PLAYBOOKS/v2.0-android-redesign.md` | Create | 9 屏验收 checklist + 像素对比方法 |

---

## Task 1: Compose 主题 token + 依赖升级

**Files:**
- Modify: `poc/android/app/build.gradle.kts`
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/ui/theme/AppTheme.kt`
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/ui/theme/Color.kt`
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/ui/theme/Type.kt`
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/ui/theme/Shape.kt`

**Steps:**
- [ ] 加依赖：`androidx.compose:compose-bom:2024.08.00` / `material3:1.3.0` / `activity-compose:1.9.1` / `navigation-compose:2.7.7` / `hilt-android:2.51` + `kapt`
- [ ] 开 `buildFeatures.compose = true` + `composeOptions.kotlinCompilerExtensionVersion`
- [ ] 从 `ui/assets/design-system.css` 抽 token：
  - 主色 `#1A56DB`、欠费红 `#E02424`、文字层级 `#111827/#374151/#6b7280`、卡片背景 `#FFFFFF`、页面背景 `#F3F4F6`
  - 字号 11/12/13/14/15/16/20/24/28
  - 圆角 10/12/16/20/40
  - 间距 4/8/12/14/16/20
- [ ] `Color.kt`：定义 `Primary`, `DebtRed`, `TextPrimary` 等
- [ ] `Type.kt`：Body/Title/Display 用 `PingFang/HarmonyOS Sans/system` family + size 阶梯
- [ ] `Shape.kt`：`small=8.dp`, `medium=12.dp`, `large=16.dp`, `extraLarge=20.dp`
- [ ] `AppTheme.kt`：暴露 `AppTheme { content() }` Composable
- [ ] 单测：Robolectric 验证 token 与 CSS 一致（snapshot）

**Verification:**
- `./gradlew :app:compileDebugKotlin` 通过
- Compose preview 能渲染基础 `Surface(color = MaterialTheme.colorScheme.primary)`

---

## Task 2: MainActivity 单 Activity + Bottom Tab + WebView 骨架

**Files:**
- Rewrite: `poc/android/app/src/main/java/com/autoluyin/demo/MainActivity.kt`
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/webview/AppWebView.kt`
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/webview/JsBridge.kt`
- Modify: `poc/android/app/src/main/AndroidManifest.xml`（声明 Compose 主题，去掉旧 ActionBar）

**Steps:**
- [ ] `MainActivity` 改用 `setContent { AppTheme { AppRoot() } }`
- [ ] `AppRoot()` 是 `Scaffold { bottomBar = { BottomNavigation { 4 tabs } } }`
- [ ] 4 个 Tab 用 `NavHost`：`home / cases / call-history / profile`
- [ ] 每个 tab 路由对应一个 `WebViewScreen(url = "${backendBase}/app/${tab}")`
- [ ] `AppWebView`：WebView Composable with `webViewClient`, `domStorage=true`, `javaScriptEnabled=true`，addJavascriptInterface 注入 `JsBridge` as `"AndroidBridge"`
- [ ] WebView 启动时 `evaluateJavascript("window.__JWT__='${jwt}'")` 注入 token
- [ ] `JsBridge` 6 个方法（先 stub，后续 task 填）：
  - `getJwt(): String`
  - `getBackendUrl(): String`
  - `dialCase(caseIdJson: String): Unit` — fallback 调 `MainActivity.startDial`
  - `scanQr(): Unit` — 启动 `QrScanActivity`
  - `openCaseDetail(caseId: Long)` — push 案件详情 WebView
  - `notifyAuthError()` — 触发 `ForceLogoutDialog`
- [ ] 处理硬件返回键：WebView 能 goBack 优先 goBack，否则交给 Compose Navigation
- [ ] 测试：UI test 验证 4 tab 切换 + WebView 持久化滚动位置

**Verification:**
- App 启动后看到底部 4 tab
- 点击每个 tab，WebView 加载对应路由（暂时显示 404，下个 task 建路由）
- `adb shell input keyevent KEYCODE_BACK` 不退出 App，正确处理 WebView 历史

---

## Task 3: React mobile pages — Screen 1 工作台首页 + Screen 8 个人信息

**Files:**
- Create: `frontend/src/pages/app/_layout.tsx`
- Create: `frontend/src/pages/app/home/index.tsx`
- Create: `frontend/src/pages/app/profile/index.tsx`
- Create: `frontend/src/router/appRoutes.tsx`
- Modify: `frontend/src/App.tsx`（注册 `/app/*` 路由）
- Create: `frontend/src/lib/jsBridge.ts`
- Create: `ui/assets/design-system-mobile.css`

**Steps:**
- [ ] `appRoutes.tsx`：4 个 tab 路由 + `/app/cases/:id`（详情）
- [ ] `_layout.tsx`：全屏（无侧边栏），bottom padding 64px 避让 Tab Bar
- [ ] `home/index.tsx`：
  - 顶部 greeting（"上午好，{userName}" + 日期）
  - 蓝色渐变 summary card（今日已拨/接通/承诺 3 列）
  - "待办拨号" section（请求卡片 list）—— 来源：`GET /api/v1/agent/me/dial-requests`
  - "本月通话分钟" 小卡 —— `GET /api/v1/agent/me/performance`
- [ ] `profile/index.tsx`：
  - 头像 + 姓名 + 角色 badge
  - "本月绩效" 行（跳本月数据页）
  - "服务器地址" 行（显示 backendUrl，点击触发 Bridge.openSettings）
  - "退出登录" 按钮 → 清 token + Bridge.notifyAuthError
- [ ] `lib/jsBridge.ts`：
  - 检测 `window.AndroidBridge` 存在 → 真机；否则 stub（浏览器调试）
  - 暴露 `dial(caseId)` / `scan()` / `openSettings()` / 接收 push 事件
- [ ] `design-system-mobile.css`：
  - tap target 最小 44×44
  - 字号阶梯比 PC 略大（12→14, 14→16 等）
  - 移动手势 momentum scroll
- [ ] 像素对比：playwright mobile viewport 390×844 截图 vs `ui/app-agent.html` Screen 1，diff ≤ 2%

**Verification:**
- `npx tsc -b --noEmit` 通过
- 浏览器 390×844 viewport 访问 `/app/home` 与 `ui/app-agent.html` Screen 1 视觉吻合
- WebView 加载后点击「待办拨号 → 立即拨打」触发 `AndroidBridge.dialCase(...)`

---

## Task 4: React mobile pages — Screen 5/6/7 案件列表 + 详情 + 通话记录

**Files:**
- Create: `frontend/src/pages/app/cases/index.tsx`
- Create: `frontend/src/pages/app/cases/[id].tsx`
- Create: `frontend/src/pages/app/call-history/index.tsx`

**Steps:**
- [ ] `cases/index.tsx`：
  - 顶部搜索 + 筛选（待联系/跟进中/承诺/已缴费）
  - 每项卡片：业主姓名 / 房号 / 欠费金额（红色大字）/ 月数 / 距上次联系
  - 滑动到底分页 + 下拉刷新
  - 点击项 → `AndroidBridge.openCaseDetail(caseId)` 启动 push WebView
- [ ] `cases/[id].tsx`：
  - 业主信息卡（姓名/电话脱敏/楼栋房号）
  - 欠费明细（按月 list）
  - 活动时间线（通话摘要 + 跟进记录）—— 复用 `frontend/src/components/case/ActivityTimeline.tsx` 改 mobile 版
  - 底部固定操作栏："立即拨号"（大按钮）+ "标记跟进"
- [ ] `call-history/index.tsx`：
  - 复用 PC 版逻辑（v1.9.9 已加的"今日实时"banner 适配 mobile）
  - 列表项：通话时间 / 业主 / 时长 / 结果 badge / AI 评分
  - 点击 → 详情 push（暂跳 PC 版 `/calls/:id` 也用 WebView，二期可做专用 mobile 详情）
- [ ] 移动版组件库：抽公共 `<MobileCard>`, `<MobileListItem>`, `<MobileButton>` 到 `frontend/src/components/mobile/`

**Verification:**
- 3 个屏 playwright 截图对比 app-agent.html 对应 Screen，diff ≤ 2%
- 列表项点击触发 JsBridge 调用日志可见
- 下拉刷新 + 分页正常

---

## Task 5: Compose 原生 — Screen 2 拨打请求全屏

**Files:**
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/screens/dial/DialRequestScreen.kt`
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/screens/dial/DialRequestActivity.kt`
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/screens/dial/DialRequestViewModel.kt`
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/push/DialRequestHandler.kt`（push 触发改 startActivity）

**Steps:**
- [ ] `DialRequestActivity`：
  - `WindowCompat.setDecorFitsSystemWindows(false)` 全屏
  - `showWhenLocked + turnScreenOn`（锁屏唤起）
  - 从 Intent 拿 `case_id` / `call_id` / `expires_at`
- [ ] `DialRequestScreen` 视觉：
  - 顶栏：left "拨打请求" + right 倒计时（mm:ss）
  - 80×80 圆形头像（initials）+ name (24px bold) + 房号
  - 欠费卡（白底，欠费金额 20px 红色 + 月数）
  - SVG 倒计时环（120×120，颜色随剩余时间变化：>50% 蓝 / 20-50% 橙 / <20% 红）
  - 底部双按钮："立即拨打"（大蓝色）+ "稍后处理"
- [ ] `DialRequestViewModel`：
  - 倒计时 Flow（30s 默认，从 expires_at - now 计算）
  - "立即拨打" → 调 `ApiClient.dialStart(case_id)` → 拿 call_id → `Intent.ACTION_CALL` 拉起系统拨号
  - "稍后处理" → finish + 上报后端 `defer`
- [ ] 测试：Compose UI test 验证倒计时减 + 按钮 enabled state

**Verification:**
- 真机锁屏状态下推送一条 `dial-request` → DialRequestActivity 自动起 + 屏幕亮
- 倒计时到 0 自动 finish 并上报 expired
- "立即拨打" 触发系统拨号 + 跳到 RealtimeCallActivity

---

## Task 6: Compose 原生 — Screen 3 通话中（重写 RealtimeCallActivity）

**Files:**
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/screens/realtime/RealtimeCallScreen.kt`
- Refactor: `poc/android/app/src/main/java/com/autoluyin/demo/realtime/RealtimeCallActivity.kt`（XML → Compose）
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/realtime/AudioStreamClient.kt`（保留，只改 callback 适配 Compose state）
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/screens/realtime/RealtimeCallViewModel.kt`

**Steps:**
- [ ] `RealtimeCallViewModel`：
  - StateFlow 暴露：transcript / suggestion / risk / connectionState
  - 启动时调 `AudioStreamClient.start()`，回调改写 StateFlow.emit
  - 提供 `adoptSuggestion(id)` / `ignoreSuggestion(id)` / `hangup()` actions
- [ ] `RealtimeCallScreen` 视觉：
  - 顶栏：业主名 + 通话时长 + 网络状态 badge（🟢 实时 / 🟡 弱网 / 🔵 本地）
  - 风控条（L1 橙 / L2 红 / L3 红 + 强制挂断 modal）
  - 中部实时转写流（自动滚到底）+ 音量波形动画
  - AI 建议浮卡（z-index 高，滑入式，"采纳"/"忽略"按钮）
  - 底部控制栏：扬声器 / 静音 / 挂断（红色大按钮）
- [ ] 重要：保留所有现有 callback 路径（hangup 上报 / supervisor takeover / 风控 L3 强制挂断），仅 UI 层重写
- [ ] 测试：
  - Compose UI test 验证 transcript append → 自动滚动
  - 风控 L3 事件 → 强制挂断 modal 显示 + 5s 倒计时自动挂

**Verification:**
- 真机通话 5 分钟，转写流稳定（不卡顿）
- 中途断网 → connectionState 切到 🟡，恢复后回 🟢
- 风控关键词触发 → L1 banner 显示 + 震动

---

## Task 7: Compose 原生 — Screen 4 通话结束标记

**Files:**
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/screens/postcall/CallEndMarkScreen.kt`
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/screens/postcall/CallEndMarkActivity.kt`
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/PhoneStateReceiver.kt`（IDLE → startActivity(CallEndMark) 替代旧 Dialog）

**Steps:**
- [ ] `CallEndMarkActivity`：从 Intent 拿 `call_id`
- [ ] `CallEndMarkScreen` 视觉：
  - 顶部"通话已结束"标题 + 通话时长 + AI 总结卡片（背景灰）
  - "本次结果"单选 chip 组：承诺缴费 / 已缴费 / 拒绝 / 无法联系 / 其他（AI 预填）
  - 选"承诺缴费" → 展开承诺日期 DatePicker
  - 备注 textarea
  - 底部"保存"按钮（满宽蓝色）
- [ ] 提交 → `PATCH /api/v1/calls/{call_id}/tag` → finish
- [ ] 4 秒内未操作 → 自动 Bg 化（保留任务通知，用户后续可继续编辑）

**Verification:**
- 通话挂断后 1s 内 CallEndMarkActivity 自动起
- AI 预填值与 `GET /api/v1/calls/{call_id}/tag-suggest` 一致
- 保存成功后通话记录列表立刻显示新行

---

## Task 8: 全局 — Screen 9 强制退出 + ApiClient 401 拦截

**Files:**
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/screens/dialogs/ForceLogoutDialog.kt`
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/Api.kt`（AuthInterceptor 加 401 / 3009 处理）
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/MainActivity.kt`（LocalBroadcastReceiver 监听 + 弹 dialog）

**Steps:**
- [ ] `AuthInterceptor.intercept`：拿到 response 后判断 `code == 3009`（异地登录） → LocalBroadcast `action="force_logout"`
- [ ] `MainActivity` 注册 BroadcastReceiver → 弹 `ForceLogoutDialog`
- [ ] `ForceLogoutDialog`：modal Compose Dialog，显示原因 + "重新登录" 按钮 → 清 token + 跳回登录页
- [ ] 关键：JsBridge 也要能从 WebView 主动触发（fetch 拿到 401 也走同一逻辑）

**Verification:**
- 用同一账号在另一台机器登录 → 当前手机 5s 内弹 ForceLogoutDialog
- 点"重新登录" → SharedPreferences token 清空 + 回到登录页

---

## Task 9: Playwright 像素对比 + Playbook

**Files:**
- Create: `frontend/tests/playwright/app-screens.spec.ts`
- Create: `docs/QA_PLAYBOOKS/v2.0-android-redesign.md`

**Steps:**
- [ ] Playwright 测试：mobile viewport 390×844，截图 9 屏分别 vs `ui/app-agent.html` 同 Screen 的截图，diff 计算（用 `pixelmatch`）
- [ ] 阈值：每屏 diff ≤ 2%（允许文字渲染微差）
- [ ] Playbook 9 章 — 每屏一个验收 section，含：
  - 设计稿截图 + 真实截图并排
  - 关键交互测试步骤（拨号 / 接通 / 挂断 / 标记 / 切 tab）
  - 已知差异（如 Android 状态栏 vs iOS notch）
  - 通过/不通过标准

**Verification:**
- `npx playwright test app-screens.spec.ts` 9 屏全过
- Playbook commit + PR description 引用

---

## 关键文件改动汇总

| 类型 | 路径数 | 行数估算 |
|---|---|---|
| Compose 主题 + Activity 重写 | 6 | ~800 |
| WebView + JsBridge | 3 | ~400 |
| Compose 原生屏 (S2/S3/S4/S9) | 8 | ~1500 |
| React mobile pages | 8 | ~1200 |
| design-system-mobile.css | 1 | ~80 |
| 测试 + Playbook | 4 | ~600 |
| **合计** | **~30 文件** | **~4500 行** |

## 验收

1. **9 屏全部 1:1 吻合 `ui/app-agent.html`**：Playwright diff ≤ 2%
2. **Android 6 (MIUI 10) 真机跑通**：4 tab 切换 / 拨号 / 录音上传 / 通话结束标记 完整 happy path
3. **性能**：冷启动 ≤ 3s，tab 切换 ≤ 200ms（WebView 预热保活）
4. **回归**：现有 v1.9.9 功能全保（扫码 / 自检 / 录音扫描 / WS 流 / 风控 L1-L3）

## 不变量

- minSdk=23 不动（PRD § 8.4 兼容性要求）
- AudioStreamClient + RecordingScanner + PhoneStateReceiver 核心逻辑不动，只换 UI 调用方
- 后端 API 完全不动（只是新增 `frontend/src/pages/app/` 路由调用现有 endpoint）
- v1.9.9 已修的 P0（WS URL 派生 / v1+v2 签名 / API 26 守护）全保留

## 风险

| 风险 | 缓解 |
|---|---|
| WebView 在 Android 6 上性能弱 | 启用 hardware acceleration + 复用 WebView 实例不重建 |
| Compose Material 3 在 minSdk 23 上某些 API 不可用 | 已验证 Compose BOM 2024.08 支持 minSdk 21；定期测 |
| 静态屏 / 原生屏 切换闪屏 | 用共享元素动画 + 同色背景渐变；二级页面不要纯白闪 |
| 像素对比 diff 阈值太严卡测试 | 字体渲染差异允许 ±5px 容错；只比较结构和色块 |
| 双端 design token 飘移 | 单一 source of truth：`ui/assets/design-system.css` → Kotlin Color.kt 自动生成脚本（二期） |

## 工时

| Task | 估时 |
|---|---|
| 1. Compose 主题 token + 依赖 | 0.5d |
| 2. MainActivity + Tab + WebView 骨架 | 1d |
| 3. React mobile S1 + S8 | 1d |
| 4. React mobile S5 + S6 + S7 | 1.5d |
| 5. Compose S2 拨打请求 | 1d |
| 6. Compose S3 通话中（重写 RealtimeCallActivity） | 2d |
| 7. Compose S4 通话结束 | 0.5d |
| 8. ForceLogout + 401 拦截 | 0.5d |
| 9. Playwright 像素对比 + Playbook | 1d |
| **合计** | **~9 工作日（2 周）** |

## 后续（不在本轮）

- iPad / 平板适配（同一份 React 加 tablet breakpoint）
- 暗色主题（design-system.css 已有 dark token，启用即可）
- 离线 case 缓存（Room + WorkManager 后台同步）
- Compose Multiplatform 复用 iOS（如果未来出 iOS App）
