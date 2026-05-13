# Sprint v2.1 — 设备录音能力感知（"用户/管理员都知情"闭环）

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement task-by-task. 每个 task 块用 `- [ ]` 跟踪。

**Goal:** 解决 v2.0 留下的"新机型用户默默失败"问题。让坐席自己 + 物业管理员都能在使用前/使用中明确知道设备的实时录音能力，避免通话挂断后"AI 分析永不出现"的盲区。

**核心问题（v2.0 后才被识别）：**
- 当前 `RecordingScanner` 在 Android 10+ 系统级封禁通话录音的机型上**默默失败**
- App 自检只查 `recording_dir_ok` 文件夹存在性，不验证"录音文件实际产生"
- 没有 UI 告诉用户当前手机能否用实时分析模式
- PC 管理员看不到坐席设备健康度，合同纠纷时拿不出数据

**架构方案（"探测 + 表态 + 留痕"三段式）：**

```
启动 → 客户端 ROM 探测（Build.* + 系统录音器开关识别）
     → 自检 self-check 上报后端，返回 recording_capability
     → 后端写 device_capability_log 留痕
     → App 主页顶部 banner 显示当前 capability
     → 拨号前再次校验，incompatible 弹拦截
     → PC /admin/agent-devices 看坐席设备列表 + 实时通话墙加 capability badge
```

**Tech Stack:**
- Backend：FastAPI + Pydantic + Alembic + SQLAlchemy 2.0
- App：Kotlin（Compose 已就绪）
- PC：React + Refine.dev + shadcn/ui + Tailwind
- 测试：pytest + Playwright

---

## ⚠️ Notes (read before any task)

**1. 不要做强制拒绝**（C 方案才做）
本 sprint B 方案：incompatible 设备 **可以继续用 App**，但拨号前弹"您的设备无法保存录音，是否继续？"给用户选；管理员侧能看到该坐席状态。强制拒绝（基于白名单）是 v2.2+ 的 C 方案范围。

**2. ROM 探测的边界**
客户端探测能拿到 `Build.MANUFACTURER / Build.MODEL / Build.VERSION.RELEASE / Build.MANUFACTURER`，但**无法直接探测"系统通话录音器是否开启"**——这是 OEM 私有设置，不开放 API。我们的策略：
- 静态映射（PRD § 8.4 矩阵）：根据 ROM × Android 版本判定 `realtime / post_upload / incompatible` 三档
- 运行时验证：通话挂断后 `RecordingScanner` 找不到文件 → 上报 `actual_recording_failed = true` → 后端把该设备标记为"实测不可用"
- 用户自报：onboarding 步骤 3 让用户勾选"我已在系统设置开启通话自动录音"

**3. 不要破坏 v2.0 的实时通话流**
RealtimeCallActivity / AudioStreamClient / 风控 / Compose 重写完全不动。本 sprint 只在**外围**加 banner / dialog / 后端字段。

**4. PRD § 8.4 已有兼容矩阵**
不要重复写矩阵；后端常量直接 import 自 docs/PRD.md 概念，做成 Python `CAPABILITY_MATRIX` 字典。

**5. 不要把"capability"当 "can_call"**
- `can_call` = 当前是否允许拨号（v1.6 已有）— 不变
- `recording_capability` = 录音模式能力（v2.1 新增）— 三档 enum

---

## File Map

| File | Action | 责任 |
|---|---|---|
| **Module A — 后端模型 + API** | | |
| `poc/backend/app/models/device_capability_log.py` | Create | 留痕表 |
| `poc/backend/alembic/versions/24014_v210_device_capability.py` | Create | 迁移 |
| `poc/backend/app/services/device_capability.py` | Create | ROM × Android 静态矩阵 + 计算函数 |
| `poc/backend/app/schemas/device.py` | Modify | SelfCheckIn/Out 加 capability 字段 |
| `poc/backend/app/api/devices.py` | Modify | self-check 调 capability 服务 + 写日志 |
| `poc/backend/app/api/admin_agent_devices.py` | Create | 新 endpoint `/admin/agent-devices` |
| `poc/backend/app/main.py` | Modify | 挂载新 router |
| `poc/backend/app/api/agent_me.py` | Modify | active-call 响应加 capability flag |
| **Module B — Android 探测 + UX** | | |
| `poc/android/app/src/main/java/com/autoluyin/demo/capability/DeviceCapabilityProbe.kt` | Create | Build.* 收集 + 静态判定 |
| `poc/android/app/src/main/java/com/autoluyin/demo/Api.kt` | Modify | SelfCheckReq/Resp 加 capability 字段 |
| `poc/android/app/src/main/java/com/autoluyin/demo/MainActivity.kt` | Modify | onboarding 4 步 + capability 持久化 |
| `poc/android/app/src/main/java/com/autoluyin/demo/onboarding/OnboardingActivity.kt` | Create | 4 步骤 Compose Activity（权限 / URL / 录音设置 / 自检） |
| `poc/android/app/src/main/java/com/autoluyin/demo/onboarding/OnboardingScreen.kt` | Create | Composable Wizard |
| `poc/android/app/src/main/java/com/autoluyin/demo/AppConfig.kt` | Modify | 加 saveCapability/getCapability + onboarding done flag |
| **Module C — Android UI 集成** | | |
| `frontend/src/pages/app/home/index.tsx` | Modify | 顶部加 capability banner |
| `frontend/src/pages/app/profile/index.tsx` | Modify | 个人信息显示当前 capability |
| `frontend/src/pages/app/cases/[id].tsx` | Modify | 拨号前 incompatible 弹 confirm |
| `frontend/src/lib/jsBridge.ts` | Modify | 加 `getCapability()` bridge 方法 |
| `poc/android/app/src/main/java/com/autoluyin/demo/webview/JsBridge.kt` | Modify | 加 getCapability stub 实装 |
| **Module D — PC 管理员页面** | | |
| `frontend/src/pages/admin/agent-devices/index.tsx` | Create | 坐席设备列表 |
| `frontend/src/App.tsx` | Modify | 注册 /admin/agent-devices 路由 |
| `frontend/src/config/nav.ts` | Modify | 侧边栏加入口 |
| `frontend/src/pages/supervisor/wall/index.tsx`（如有） / 实时通话墙文件 | Modify | 坐席卡片加 capability badge |
| **Module E — 测试 + Playbook** | | |
| `poc/backend/tests/api/test_device_capability.py` | Create | 后端测试 |
| `poc/backend/tests/services/test_device_capability_matrix.py` | Create | 静态矩阵测试 |
| `frontend/e2e/v210-device-capability.spec.ts` | Create | 前端 e2e |
| `docs/PRD.md` | Modify | § 8.4 加 capability 状态机说明 |
| `docs/QA_PLAYBOOKS/v2.1-device-capability.md` | Create | 验收 Playbook |

---

## Task 1: 后端数据模型 + 静态能力矩阵服务

**Files:**
- Create: `poc/backend/app/models/device_capability_log.py`
- Create: `poc/backend/alembic/versions/24014_v210_device_capability.py`
- Create: `poc/backend/app/services/device_capability.py`
- Create: `poc/backend/tests/services/test_device_capability_matrix.py`

**Steps:**
- [ ] 新表 `device_capability_log`：
  - id / tenant_id / user_id / device_id / detected_at
  - manufacturer (string 32) / model (string 64) / android_version (string 16) / rom_label (string 32)
  - capability enum: `realtime / post_upload / incompatible`
  - actual_recording_works: bool? (运行时验证结果，nullable — 第一次自检时未知)
  - source: `static_matrix / runtime_verified` (本次记录数据来源)
  - notes: string?
- [ ] 索引：`(tenant_id, user_id, detected_at desc)` + `(device_id)`
- [ ] `services/device_capability.py`：
  - 常量 `CAPABILITY_MATRIX: dict[tuple[str, str], CapabilityLevel]`，键 `(rom_family, android_major)` 例如 `("miui", "9")` → `realtime`
  - 函数 `derive_rom_family(manufacturer, model) -> str`（"xiaomi" → "miui"，"huawei" → "emui"，"oppo"/"realme" → "coloros"，"vivo"/"iqoo" → "originos"，其他 → "aosp"）
  - 函数 `derive_capability(manufacturer, model, android_version) -> CapabilityLevel`
  - 矩阵规则同 PRD § 8.4.2（实施 5×7 矩阵）
- [ ] 单元测试覆盖：典型机型 8 组（小米/华为/OPPO/vivo/Pixel × Android 6/9/12/14）

**Verification:**
- `pytest tests/services/test_device_capability_matrix.py` 全过
- `alembic upgrade head` 成功创建表
- 矩阵覆盖率：5 个 ROM × 7 个 Android 版本 = 35 组合，每组都有明确返回值（不返回 None）

---

## Task 2: 扩展 self-check endpoint + 写留痕日志

**Files:**
- Modify: `poc/backend/app/schemas/device.py`
- Modify: `poc/backend/app/api/devices.py`
- Create: `poc/backend/tests/api/test_device_capability.py`

**Steps:**
- [ ] `SelfCheckIn` 加字段（全可选，向后兼容旧 App）：
  - `manufacturer: str | None`
  - `model: str | None`
  - `android_version: str | None`
  - `recording_toggle_self_reported: bool | None` (用户在 onboarding 勾的"我已开启系统通话录音")
  - `last_recording_scan_failed: bool | None` (上次通话挂断后 RecordingScanner 是否找不到文件)
- [ ] `SelfCheckResp` 加字段：
  - `recording_capability: Literal["realtime", "post_upload", "incompatible"]`
  - `detected_rom: str`（如 "MIUI 10.2"）
  - `guidance_text: str`（按 capability 给的中文指引文案）
- [ ] `devices.self_check()` 实现：
  - 调 `derive_capability(...)`
  - 如果 `last_recording_scan_failed=True` → 直接降级为 `incompatible`（运行时验证胜过静态矩阵）
  - 写一行 `device_capability_log`
  - 返回 capability + guidance
- [ ] `guidance_text` 三段（按 capability）：
  - realtime: "实时通话分析已就绪 — {detected_rom}"
  - post_upload: "事后上传模式 — 您的设备 {detected_rom} 暂不支持实时分析。通话挂断 1-2 分钟后可在「通话记录」查看 AI 摘要"
  - incompatible: "您的设备 {detected_rom} 系统级不支持通话录音。建议使用 MIUI 10/11 或 EMUI 9/10 的机型。当前可继续拨号，但 AI 分析功能不可用"
- [ ] 测试 5 个 case：xiaomi/9 → realtime；xiaomi/14 → post_upload；pixel/14 → incompatible；空字段（旧 App 兼容）→ realtime + guidance "未识别设备型号"；last_scan_failed=True 覆盖矩阵 → incompatible

**Verification:**
- pytest 5 个 case 全过
- 用 curl 实测 `/api/v1/devices/self-check` 返回新字段
- 旧 App（没传 manufacturer 等）不报错，向后兼容

---

## Task 3: PC 管理员设备列表 endpoint

**Files:**
- Create: `poc/backend/app/api/admin_agent_devices.py`
- Modify: `poc/backend/app/main.py`（mount router）
- 测试合并到 Task 2 的 test 文件

**Steps:**
- [ ] `GET /api/v1/admin/agent-devices?page=&page_size=&capability=&q=` 返回 `PaginatedResponse[AgentDeviceItem]`
- [ ] `AgentDeviceItem`:
  - user_id / user_name / role
  - device_id / manufacturer / model / android_version / rom_label
  - latest_capability / latest_self_check_at / actual_recording_works
  - status_label (运行时计算："实时可用" / "事后上传" / "录音不可用" / "未自检")
- [ ] 查询：`select latest of device_capability_log per (user, device)`，join user
- [ ] 权限：admin / supervisor / project_manager 角色才能看（用现有 `require_admin_or_supervisor` 装饰器）
- [ ] 过滤参数：capability filter，q 搜 user_name / device_id
- [ ] 测试 3 个 case：admin 看全部；supervisor 只看本组；外部催收员 403

**Verification:**
- 3 个测试 pass
- curl 调通返回 paginated 结构

---

## Task 4: Android 客户端 ROM 探测 + 自检上报

**Files:**
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/capability/DeviceCapabilityProbe.kt`
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/Api.kt`
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/AppConfig.kt`
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/MainActivity.kt`
  - 现有 `doSelfCheck()` 方法改造：把 Build.* 数据、用户自报录音开关、上次扫描失败标志一起塞 SelfCheckReq

**Steps:**
- [ ] `DeviceCapabilityProbe.kt`：
  - `fun collectDeviceInfo(ctx): DeviceInfo` 返回 manufacturer / model / androidVersion / brand
  - 不做客户端判定（让后端基于矩阵判定，前端只采集）
- [ ] `Api.kt`：扩展 `SelfCheckReq` + `SelfCheckResp` 数据类（与后端 schema 对齐）
- [ ] `AppConfig.kt`：
  - `saveCapability(ctx, capability: String, guidance: String, rom: String)` → SharedPreferences
  - `getCapability(ctx): CapabilityState?`（含 capability + guidance + rom + checked_at）
  - `markRecordingScanFailed(ctx, failed: Boolean)` → 持久化"上次扫描失败"标志
- [ ] `MainActivity.doSelfCheck()`:
  - 调 `DeviceCapabilityProbe.collectDeviceInfo` 拼 SelfCheckReq
  - 自检完成后 `AppConfig.saveCapability(...)` 持久化
- [ ] `CallWatcherService.matchAndUpload`：找不到文件时调 `AppConfig.markRecordingScanFailed(ctx, true)` 触发下次自检降级
- [ ] 找到文件成功上传时调 `markRecordingScanFailed(ctx, false)` 清除

**Verification:**
- `./gradlew :app:compileDebugKotlin` 成功
- 真机自检后 `adb logcat | grep capability` 看到上报字段
- 后端日志看到新自检请求带 manufacturer/model

---

## Task 5: Onboarding 4 步骤 Compose 引导 + 持久化

**Files:**
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/onboarding/OnboardingActivity.kt`
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/onboarding/OnboardingScreen.kt`
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/onboarding/OnboardingViewModel.kt`
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/MainActivity.kt`（开机决策跳转）
- Modify: `poc/android/app/src/main/AndroidManifest.xml`（注册）

**Steps:**
- [ ] `AppConfig` 加 `isOnboardingDone(ctx): Bool` / `markOnboardingDone(ctx)`
- [ ] MainActivity onCreate：如果 `!isOnboardingDone && jwtToken == null` → 跳 OnboardingActivity；否则走原有 preflight
- [ ] OnboardingScreen 4 步：
  1. **欢迎 + 权限**（lucide Shield icon）：列出 6 个权限说明 + "授予权限" 按钮 → 跳 ActivityCompat.requestPermissions
  2. **后端地址**（lucide Server icon）：输入 backend URL（hint "例如 http://192.168.31.242:18000"）+ "保存" 按钮
  3. **录音设置确认**（lucide Mic icon，**关键步骤**）：
     - 显示用户设备 ROM/Android 版本 + 静态判定的 capability
     - 三档不同文案：
       - realtime: 显示绿色 "您的设备支持实时通话分析" + "请到 设置 → 通话设置 → 通话自动录音 中开启" + "打开系统设置" 按钮（startActivity Settings.ACTION_SETTINGS）+ "我已确认开启" checkbox
       - post_upload: 显示橙色 "您的设备使用事后上传模式" + 同样的设置指引 + checkbox
       - incompatible: 显示红色 "您的设备 ROM 不支持通话录音" + "继续使用（仅拨号，无 AI 分析）" + 强制 checkbox 二次确认
     - 必勾 checkbox 才能"下一步"
  4. **自检**（lucide CheckCircle icon）：自动调 self-check，显示结果（绿/橙/红 banner），点 "完成" → markOnboardingDone + 跳 HomeActivity
- [ ] `OnboardingViewModel`：管理 4 步状态、当前步骤、各步完成与否
- [ ] 设计：每步全屏 Compose，底部 "下一步" 按钮 + 顶部 4 段进度条（lucide ChevronLeft 返回上一步）

**Verification:**
- `./gradlew :app:compileDebugKotlin` 成功
- 真机 clear data 后启动 → 自动进 Onboarding → 4 步走完进 HomeActivity
- 二次启动直接进 HomeActivity（onboarding done 标记生效）

---

## Task 6: WebView 端 capability banner + 拨号前拦截

**Files:**
- Modify: `frontend/src/pages/app/home/index.tsx`（顶部 banner）
- Modify: `frontend/src/pages/app/profile/index.tsx`（个人信息显示）
- Modify: `frontend/src/pages/app/cases/[id].tsx`（拨号前 confirm）
- Modify: `frontend/src/lib/jsBridge.ts`（加 getCapability）
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/webview/JsBridge.kt`（实装 getCapability）
- Modify: `frontend/src/styles/design-system-mobile.css` + `ui/assets/design-system-mobile.css`（banner CSS）

**Steps:**
- [ ] JsBridge 加 `@JavascriptInterface fun getCapability(): String` 返回 JSON `{capability, guidance, rom}` from AppConfig
- [ ] `lib/jsBridge.ts`：`Bridge.getCapability(): { capability, guidance, rom } | null` — 浏览器 fallback 返回 stub `{capability:"realtime", guidance:"开发模式", rom:"DEV"}`
- [ ] home/index.tsx 顶部加 `<CapabilityBanner />`：
  - realtime: 绿色细条 "🟢 实时通话分析已就绪 - {rom}"，可关闭
  - post_upload: 橙色 "🟡 事后上传模式 - {rom}（详情）" — 点详情进 profile 页
  - incompatible: 红色 "🔴 录音不可用 - {rom}（联系管理员）" — 不可关闭
- [ ] profile/index.tsx 加新 section "录音能力"：显示 capability + rom + guidance 全文 + "重新自检" 按钮（调 AndroidBridge.runSelfCheck — 需要 Task 7 加 bridge 方法）
- [ ] cases/[id].tsx 拨号按钮 onClick 前判断：if `Bridge.getCapability().capability === "incompatible"` → 弹 confirm dialog "您的设备无法保存录音，本次通话将无 AI 分析。是否继续？" → 用户点继续才走原拨号
- [ ] CSS 加 `.cap-banner.cap-banner-{green,orange,red}` 样式（轻量横条 padding 8px 16px）

**Verification:**
- `npx tsc -b --noEmit` 通过
- `npx vite build` 通过
- 浏览器 viewport 模拟 capability=incompatible 看到红色 banner
- Android 真机集成测试：onboarding 后 home banner 颜色与 capability 对应

---

## Task 7: PC 管理员设备列表页 + 实时通话墙 badge

**Files:**
- Create: `frontend/src/pages/admin/agent-devices/index.tsx`
- Modify: `frontend/src/App.tsx`（注册路由）
- Modify: `frontend/src/config/nav.ts`（侧边栏加入口）
- Modify: 现有实时通话墙文件（先 grep 找）— 卡片加 capability badge

**Steps:**
- [ ] `frontend/src/pages/admin/agent-devices/index.tsx`：
  - 复用 admin/users/index.tsx 的 layout 模板
  - 表格列：坐席姓名 / 角色 / 设备型号 / Android / ROM / 录音模式 (badge) / 上次自检 / 操作
  - capability badge：绿/橙/红
  - 顶部筛选：capability 三档 + 角色
  - 操作列："查看历史"（弹 modal 显示该设备最近 10 次 capability_log）
  - 数据：useList resource="admin/agent-devices"
- [ ] `App.tsx` 加 `<Route path="/admin/agent-devices" element={<AgentDeviceListPage />} />`
- [ ] `nav.ts` admin 区段加菜单项 "设备能力" with lucide Smartphone icon
- [ ] grep 找现有"实时通话墙"页面（`/supervisor/wall` 或 `/admin/realtime-wall`），坐席卡片加右上小标签：📡 实时 / 📦 事后 / ❌ 不可用
  - 数据来自 active-call 响应（Task 2 已加 capability flag）

**Verification:**
- 浏览器访问 `/admin/agent-devices` 看到 paginated 表格
- 用 supervisor 账号访问只看到本组坐席
- 实时通话墙坐席卡片右上有 capability badge

---

## Task 8: 测试 + PRD 更新 + Playbook

**Files:**
- Create: `frontend/e2e/v210-device-capability.spec.ts`
- Modify: `docs/PRD.md` § 8.4（加 capability 状态机 + onboarding 流程图）
- Create: `docs/QA_PLAYBOOKS/v2.1-device-capability.md`

**Steps:**
- [ ] e2e 测试：
  - 模拟 capability=realtime / post_upload / incompatible 三种状态访问 /app/home，断言 banner 颜色
  - 模拟 incompatible 状态点 /app/cases/1 拨号按钮，断言弹 confirm dialog
  - admin 账号访问 /admin/agent-devices，断言表格渲染
- [ ] PRD § 8.4 加新小节 8.4.8 "客户端能力探测与降级流程"：
  - 状态机图（自检 → capability → banner → onboarding step 3）
  - capability 三档定义 + 转换条件（如 last_scan_failed=True 强制降级）
  - 与 TenantSettings.recording_mode 的关系（租户级偏好 vs 设备级实际能力，设备能力为准）
- [ ] `v2.1-device-capability.md` Playbook：
  - 后端 self-check 测试（curl 5 个 case）
  - Android onboarding 4 步手测（含 adb 命令清缓存重走流程）
  - PC `/admin/agent-devices` 验收（filter + 分页）
  - 实时通话墙 badge 验收
  - 已知差异 + 验收终判

**Verification:**
- e2e 全过
- PRD lint 通过（如有）
- Playbook 200+ 行覆盖 8 个验收点

---

## 关键文件改动汇总

| 类型 | 路径数 | 行数估算 |
|---|---|---|
| 后端模型 + 迁移 + 服务 | 4 | ~400 |
| 后端 API endpoint | 3 | ~250 |
| Android Compose onboarding | 4 | ~600 |
| Android probe + ApiClient | 3 | ~200 |
| WebView banner / profile / dial guard | 6 | ~300 |
| PC 管理员设备列表 + 通话墙 badge | 4 | ~400 |
| 测试 + Playbook + PRD | 4 | ~600 |
| **合计** | **~28 文件** | **~2750 行** |

## 验收

1. **后端测试全过**：`pytest tests/api/test_device_capability.py tests/services/test_device_capability_matrix.py`
2. **Android 真机走完 onboarding 4 步** → home banner 颜色与设备 capability 对应（MIUI 10 → 绿 / Pixel 14 → 红）
3. **PC `/admin/agent-devices`** 列出 4+ 坐席的设备状态，capability filter 工作
4. **实时通话墙** 坐席卡片右上有 capability badge
5. **incompatible 设备** 拨号前弹 confirm，用户点继续仍能拨号（不强制拒绝）
6. **降级机制**：通话挂断后 RecordingScanner 找不到文件 → 下次自检 capability=incompatible

## 不变量

- v2.0 的 9 屏 UI 不动（home 顶部加 banner / profile 加一个 section / cases/[id] 加 confirm — 都是增量）
- AudioStreamClient / 风控 / Compose 通话流不动
- TenantSettings.recording_mode 不动（租户偏好；设备能力是另一个维度，不冲突）
- 旧 App 兼容（self-check 字段全可选；不传 manufacturer 等回退到 realtime + guidance "未识别"）

## 风险

| 风险 | 缓解 |
|---|---|
| 静态矩阵与实际机型不匹配 | runtime_verified 优先级高于 static_matrix；积累 device_capability_log 后定期 review 矩阵 |
| 用户无脑勾 onboarding step 3 checkbox | 通话挂断后 RecordingScanner 失败会自动降级为 incompatible；用户下次自检看到红色就知道 |
| 老 App 不传新字段导致后端 NPE | 字段全 nullable + 默认值；测试 case 覆盖 |
| Pixel 用户被劝退 | incompatible 不强制拒绝；可继续用纯拨号功能；管理员可联系换机 |
| ROM 探测对小厂设备误判 | 默认 fallback `aosp` family，按 Android 版本判定（10+ 一律 post_upload，14+ incompatible） |

## 工时

| Task | 估时 |
|---|---|
| 1. 后端模型 + 矩阵服务 | 0.5d |
| 2. self-check 扩展 + 留痕 | 0.5d |
| 3. PC 管理员 endpoint | 0.5d |
| 4. Android probe + 上报 | 0.5d |
| 5. Onboarding 4 步 Compose | 1.5d |
| 6. WebView banner + 拨号拦截 | 1d |
| 7. PC 管理员页 + 通话墙 badge | 0.5d |
| 8. 测试 + PRD + Playbook | 0.5d |
| **合计** | **~5.5 工作日（约 1 周）** |

## 后续（不在本轮）

- **Sprint v2.2 — 设备白名单强制策略**（C 方案）：tenant 级配置不在白名单的 ROM 直接拒绝注册；管理员仪表盘 KPI（录音上传成功率 / 实时分析覆盖率 / 设备健康趋势）
- **Sprint v2.3 — 自动告警**：设备连续 3 次自检 incompatible → 系统通知管理员
- **Sprint v2.4 — VoIP 备用通道**：Android 14+ 用户改走 VoIP 桥接（接 SIP 网关）规避系统录音封禁
