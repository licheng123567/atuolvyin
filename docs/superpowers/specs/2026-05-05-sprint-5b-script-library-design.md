# Sprint 5b Design Spec — 话术库管理 + LLM 调优体系

**日期：** 2026-05-05  
**范围：** 后端 + PC 前端（无 Android 变更）  
**依赖：** Sprint 5a（`suggestion_feedback` 表已存在，`SuggestionFeedback` ORM 已有）

---

## 1. 背景与目标

当前实时 AI 建议引擎（`RealtimeSuggestionEngine`）使用硬编码的通用 prompt，无法按租户定制，也没有评估推送效果的机制。

Sprint 5b 目标：
1. 建立话术库（`script_template`），管理员可增删改查 + Excel 导入 + 版本回滚
2. 运行时将话术库内容注入 LLM prompt（few-shot 示例），提升推荐相关性
3. 督导对 AI 推送话术标注好/差（信号 2），业务结果自动推断信号（信号 3）
4. 夜间计算每条话术的采用率/转化率/A-D 评分，D 级自动禁用
5. 租户可配置推送灵敏度和单次推送上限

---

## 2. 数据模型

### 2.1 新建：`script_template`

```sql
CREATE TABLE script_template (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER REFERENCES tenant(id) ON DELETE CASCADE,  -- NULL = 平台预置
    title           VARCHAR(128) NOT NULL,
    trigger_intent  VARCHAR(64) NOT NULL,  -- 房屋质量 / 经济困难 / 服务不满 / 联系困难 / 其他
    content         TEXT NOT NULL,
    notes           TEXT,
    version         INTEGER NOT NULL DEFAULT 1,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    usage_count     INTEGER NOT NULL DEFAULT 0,
    adoption_rate   FLOAT,          -- 夜间计算，NULL = 数据不足
    conversion_rate FLOAT,          -- 夜间计算
    score_grade     CHAR(1),        -- A/B/C/D，NULL = 数据不足
    created_by      INTEGER REFERENCES user_account(id),
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT now()
);
CREATE INDEX idx_script_template_tenant ON script_template(tenant_id);
CREATE INDEX idx_script_template_active ON script_template(tenant_id, is_active);
```

### 2.2 新建：`script_template_version`

每次编辑主表前先写快照，支持查看历史和回滚。

```sql
CREATE TABLE script_template_version (
    id                 SERIAL PRIMARY KEY,
    script_template_id INTEGER NOT NULL REFERENCES script_template(id) ON DELETE CASCADE,
    version            INTEGER NOT NULL,
    title              VARCHAR(128) NOT NULL,
    trigger_intent     VARCHAR(64) NOT NULL,
    content            TEXT NOT NULL,
    notes              TEXT,
    edited_by          INTEGER REFERENCES user_account(id),
    edited_at          TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(script_template_id, version)
);
```

**回滚逻辑：** 回滚到版本 N → 将版本 N 的快照内容写回 `script_template`，version +1，并在 `script_template_version` 写一条新快照（标注来源是回滚）。

### 2.3 新建：`tenant_suggestion_config`

```sql
CREATE TABLE tenant_suggestion_config (
    id           SERIAL PRIMARY KEY,
    tenant_id    INTEGER NOT NULL UNIQUE REFERENCES tenant(id) ON DELETE CASCADE,
    sensitivity  SMALLINT NOT NULL DEFAULT 3 CHECK (sensitivity BETWEEN 1 AND 5),
    max_per_push SMALLINT NOT NULL DEFAULT 3 CHECK (max_per_push BETWEEN 1 AND 10),
    updated_at   TIMESTAMP WITH TIME ZONE DEFAULT now()
);
```

`sensitivity` 映射：1 = 仅置信度 ≥ 0.85 触发，3 = ≥ 0.65（默认），5 = ≥ 0.45。

### 2.4 修改：`suggestion_feedback`（新增 5 列）

```sql
ALTER TABLE suggestion_feedback
    ADD COLUMN supervisor_label   VARCHAR(16),  -- 'good' | 'bad'
    ADD COLUMN supervisor_note    TEXT,
    ADD COLUMN supervisor_id      INTEGER REFERENCES user_account(id),
    ADD COLUMN supervisor_at      TIMESTAMP WITH TIME ZONE,
    ADD COLUMN inferred_signal    SMALLINT,     -- +1 / 0 / -1
    ADD COLUMN script_template_id INTEGER REFERENCES script_template(id);
```

---

## 3. 后端 API

所有路径前缀 `/api/v1/`，错误格式 `{"code": "ERR_XXX", "message": "..."}`。

### 3.1 话术库 CRUD（角色：admin / platform_super）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/scripts` | 分页列表；支持 `?q=`（标题/内容模糊）`&intent=`（类型）`&status=active\|inactive`；返回 `PaginatedResponse[ScriptTemplateOut]` |
| POST | `/admin/scripts` | 新建；创建时同步写版本快照 v1 |
| PATCH | `/admin/scripts/{id}` | 编辑；先写版本快照，再更新主表，version +1 |
| POST | `/admin/scripts/{id}/toggle` | 启用/禁用切换 |
| DELETE | `/admin/scripts/{id}` | 软删除（`is_active=False`）；已禁用话术才能删除 |
| GET | `/admin/scripts/{id}/versions` | 版本历史列表，按 version DESC |
| POST | `/admin/scripts/{id}/rollback` | Body: `{"to_version": N}`；回滚并写新快照 |
| POST | `/admin/scripts/import` | multipart/form-data，Excel 文件；返回 `ImportResultOut` |

**角色隔离：** `admin` 只能操作自己 tenant_id 的话术，`platform_super` 可操作所有（含 tenant_id=NULL 的平台预置）。

### 3.2 督导标注

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/supervisor/script-labels` | 待标注话术列表（该租户近 7 天有 `script_template_id` 的 feedback，按 call 时间 DESC）；支持 `?unread_only=true` |
| POST | `/supervisor/script-labels/{feedback_id}` | Body: `{"label": "good"\|"bad", "note": "..."}`；`bad` 时 note 必填 |

### 3.3 推送配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/suggestion-config` | 读取（如无记录返回默认值） |
| PUT | `/admin/suggestion-config` | 全量更新 |

### 3.4 Pydantic Schemas

```python
class ScriptTemplateCreate(BaseModel):
    title: str = Field(..., max_length=128)
    trigger_intent: str = Field(..., max_length=64)
    content: str
    notes: str | None = None

class ScriptTemplateUpdate(BaseModel):
    title: str | None = Field(None, max_length=128)
    trigger_intent: str | None = None
    content: str | None = None
    notes: str | None = None

class ScriptTemplateOut(BaseModel):
    id: int
    tenant_id: int | None
    title: str
    trigger_intent: str
    content: str
    notes: str | None
    version: int
    is_active: bool
    usage_count: int
    adoption_rate: float | None
    conversion_rate: float | None
    score_grade: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ScriptVersionOut(BaseModel):
    version: int
    title: str
    trigger_intent: str
    content: str
    notes: str | None
    edited_by: int | None
    edited_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ImportResultOut(BaseModel):
    success: int
    skipped: int      # 重复标题
    failed: int       # 格式错误
    errors: list[str] # 前 10 条错误描述

class SupervisorLabelCreate(BaseModel):
    label: Literal["good", "bad"]
    note: str | None = None

    @model_validator(mode="after")
    def note_required_for_bad(self) -> "SupervisorLabelCreate":
        if self.label == "bad" and not self.note:
            raise ValueError("差话术标注必须填写点评")
        return self

class SuggestionConfigOut(BaseModel):
    sensitivity: int
    max_per_push: int

class SuggestionConfigUpdate(BaseModel):
    sensitivity: int = Field(..., ge=1, le=5)
    max_per_push: int = Field(..., ge=1, le=10)
```

---

## 4. 运行时 Prompt 注入

### 4.1 注入时机

`RealtimeSuggestionEngine.__init__()` 接受 `tenant_id: int | None` 参数。初始化时调用 `_load_scripts(db, tenant_id)`：

```python
async def _load_scripts(db: AsyncSession, tenant_id: int | None) -> dict[str, list[str]]:
    """返回 {trigger_intent: [content, ...]} 的字典，只含启用话术。"""
    rows = await db.execute(
        select(ScriptTemplate)
        .where(
            ScriptTemplate.is_active == True,
            or_(ScriptTemplate.tenant_id == tenant_id,
                ScriptTemplate.tenant_id == None)  # 含平台预置
        )
        .order_by(ScriptTemplate.trigger_intent)
    )
    result: dict[str, list[str]] = {}
    for row in rows.scalars():
        result.setdefault(row.trigger_intent, []).append(row.content)
    return result
```

### 4.2 Prompt 格式

```python
def _build_system_prompt(scripts: dict[str, list[str]], base_prompt: str) -> str:
    if not scripts:
        return base_prompt
    sections = []
    for intent, contents in scripts.items():
        examples = "\n".join(f"  - 「{c[:80]}」" for c in contents[:3])
        sections.append(f"[参考话术 - {intent}]\n{examples}")
    script_block = "\n\n".join(sections)
    return f"{base_prompt}\n\n{script_block}"
```

### 4.3 灵敏度控制

从 `tenant_suggestion_config` 读取 `sensitivity`，映射到置信度阈值：

```python
SENSITIVITY_THRESHOLD = {1: 0.85, 2: 0.75, 3: 0.65, 4: 0.55, 5: 0.45}
```

`max_per_push` 限制 LLM 单次返回的话术卡片数量（截断 response 列表）。

### 4.4 `usage_count` 累计

`RealtimeSuggestionEngine` 生成建议时，若本次是基于话术库内容触发（`script_template_id` 不为 NULL），写 `suggestion_feedback` 时同时 `UPDATE script_template SET usage_count = usage_count + 1`。

---

## 5. 业务信号推断（信号 3）

调用 `POST /calls/{id}/tag` 成功后，触发异步函数 `infer_signals_for_call(call_id, intent)`：

```python
async def infer_signals_for_call(call_id: int, intent: str, db: AsyncSession) -> None:
    if intent in ("payment_confirmed", "promise_made"):
        signal = 1
    elif intent in ("complaint",):
        signal = -1
    else:
        signal = 0

    await db.execute(
        update(SuggestionFeedback)
        .where(SuggestionFeedback.call_id == call_id,
               SuggestionFeedback.script_template_id != None)
        .values(inferred_signal=signal)
    )
    await db.commit()
```

---

## 6. Celery 夜间评分任务

任务名：`tasks.compute_script_grades`，cron: `0 2 * * *`（每天 02:00）。

### 评分算法

针对每条 `script_template`，统计 **最近 30 天** 有 `script_template_id` 匹配的 `suggestion_feedback`：

```
adoption_rate  = COUNT(action='adopt') / (COUNT(action='adopt') + COUNT(action='ignore'))
conversion_rate = COUNT(inferred_signal=1) / COUNT(DISTINCT call_id)
```

**评分规则：**

| 条件 | 评分 |
|------|------|
| `adoption_rate ≥ 0.60` | A |
| `adoption_rate ≥ 0.40` | B |
| `adoption_rate ≥ 0.20` | C |
| `adoption_rate < 0.20` 或 `conversion_rate < 0.05`（且 `usage_count ≥ 20`） | D |

**D 级自动禁用：** `usage_count ≥ 20` 且评分 = D → `is_active = False`，写系统日志（`SystemLog` 表或 Python logger）。

---

## 7. Excel 导入规范

### 7.1 模板列顺序

| 列 | 字段 | 必填 | 说明 |
|----|------|------|------|
| A | 话术标题 | ✅ | max 128 字符 |
| B | 异议类型 | ✅ | 枚举：房屋质量 / 经济困难 / 服务不满 / 联系困难 / 其他 |
| C | 话术内容 | ✅ | 话术正文 |
| D | 编写说明 | ❌ | 可空 |

### 7.2 导入逻辑

1. 读取所有行（用 `openpyxl`），跳过表头
2. 验证必填字段；异议类型不在枚举内 → failed
3. 同一租户下 `title` 重复 → skipped（不报错）
4. 合法行批量 INSERT，同时每行写版本快照 v1
5. 返回 `ImportResultOut`

---

## 8. 前端页面

### 8.1 `/admin/scripts` — 话术库列表

参照 `ui/admin.html` `#a-scripts` 区块。

- 表格列：话术标题 / 异议类型 / 版本 / 使用次数 / 采用率 / 转化率 / 综合评分（A/B/C/D 彩色徽章）/ 状态 / 操作
- 操作列：编辑（打开新增/编辑抽屉）/ 启用禁用切换 / 版本历史
- 顶部：搜索 + 异议类型下拉 + 状态下拉 + 「新增话术」+ 「批量导入」
- D 级自动禁用警告横幅（有被自动禁用的话术时显示）
- Refine `useList` 分页，20 条/页

### 8.2 新增/编辑 Sheet（侧边抽屉）

字段：标题（必填）/ 异议类型下拉（必填）/ 话术内容 textarea / 编写说明（可选）。
编辑时显示「当前版本 v{n}，保存后自动升版为 v{n+1}」提示。

### 8.3 `/admin/scripts/{id}/versions` — 版本历史

时间线列表：版本号 / 编辑人 / 编辑时间 / 内容前 80 字预览。
每行有「展开全文」+ 「回滚到此版本」按钮。
回滚 Confirm Dialog：「将覆盖当前 v{n}，生成 v{n+1}，确认继续？」

### 8.4 Excel 批量导入弹窗

1. 下载模板按钮（后端生成含表头的空 xlsx）
2. 文件选择（accept=".xlsx,.xls"）
3. 解析预览（前 10 行）
4. 确认导入 → `POST /api/v1/admin/scripts/import`
5. 结果展示：成功 N 条 / 跳过 N 条 / 失败 N 条

### 8.5 `/supervisor/script-labels` — 督导话术标注

参照 `ui/supervisor.html` `#s-scripts` 区块。

- 表格列：话术内容（截断 80 字）/ 通话信息（催收员 + 时间）/ 催收员反馈（采用/忽略/—）/ 督导标注
- 督导标注列：未标注 → 「好话术」「差话术」两个按钮；已标注 → 对应徽章 + 「修改」
- 「差话术」弹窗：标注结果（好/差）+ 点评文本框（差话术时必填）
- 顶部筛选：「仅看未标注」开关

### 8.6 系统设置扩展（已有页面）

在「录音与 AI 配置」区块补充：
- 推送灵敏度：1-5 Radio 组（1=保守 / 3=中（默认）/ 5=积极）
- 单次最多推送：下拉（1/2/3/5 条）
- 保存按钮 → `PUT /api/v1/admin/suggestion-config`

（`ui/admin.html` 已有此 UI，后端接线即可）

---

## 9. 测试覆盖目标

### 后端（pytest）

| 文件 | 测试内容 |
|------|---------|
| `tests/api/test_admin_scripts.py` | CRUD + 版本快照 + 回滚 + 角色权限 |
| `tests/api/test_script_import.py` | 正常导入 / 重复跳过 / 格式错误 |
| `tests/api/test_supervisor_labels.py` | 标注写入 + bad 无 note 报错 |
| `tests/api/test_suggestion_config.py` | 读写 + 默认值 |
| `tests/services/test_prompt_injection.py` | 有话术 → few-shot 注入 / 无话术 → 通用 prompt |
| `tests/tasks/test_script_grading.py` | A/B/C/D 四档 + D 自动禁用（usage_count ≥ 20） |
| `tests/services/test_signal_inference.py` | payment_confirmed → +1 / complaint → -1 / 其他 → 0 |

覆盖率目标：话术库 + 评分 + 信号推断模块 ≥ 85%。

### 前端（Vitest）

| 文件 | 测试内容 |
|------|---------|
| `list.test.tsx` | `getScoreGradeColor()` 辅助函数（A→绿 / B→蓝 / C→橙 / D→红）|
| `import-parser.test.ts` | 必填字段缺失 / 重复标题 / 枚举校验 |
| `supervisor-labels.test.tsx` | `getLabelStatus()` 已标注/未标注判断 |
| `signal-inference.test.ts` | `inferSignalFromIntent()` 纯函数 |

---

## 10. 文件落点

### 后端

| 文件 | 操作 |
|------|------|
| `requirements.txt` | 新增 `openpyxl` |
| `alembic/versions/5b_001_script_library.py` | 新建（down_revision = 最新 5a migration） |
| `app/models/script.py` | 新建：`ScriptTemplate` + `ScriptTemplateVersion` + `TenantSuggestionConfig` |
| `app/models/__init__.py` | 导入新 ORM |
| `app/models/call.py` | 修改 `SuggestionFeedback`（加 5 列） |
| `app/schemas/script.py` | 新建：所有 Pydantic schema |
| `app/api/admin_scripts.py` | 新建：CRUD + 版本 + 回滚 + 导入 |
| `app/api/supervisor_labels.py` | 新建：标注 API |
| `app/api/admin_suggestion_config.py` | 新建：配置读写 |
| `app/services/realtime_llm.py` | 修改：注入话术 + 灵敏度 + max_per_push |
| `app/tasks/script_grading.py` | 新建：夜间评分 Celery 任务 |
| `app/services/signal_inference.py` | 新建：业务信号推断函数 |
| `app/api/calls_v1.py` | 修改：tag 写入后调用 `infer_signals_for_call` |
| `app/main.py` | 注册新路由 |
| `tests/api/test_admin_scripts.py` | 新建 |
| `tests/api/test_script_import.py` | 新建 |
| `tests/api/test_supervisor_labels.py` | 新建 |
| `tests/api/test_suggestion_config.py` | 新建 |
| `tests/services/test_prompt_injection.py` | 新建 |
| `tests/tasks/test_script_grading.py` | 新建 |
| `tests/services/test_signal_inference.py` | 新建 |

### PC 前端

| 文件 | 操作 |
|------|------|
| `src/pages/admin/scripts/list.tsx` | 新建 |
| `src/pages/admin/scripts/versions.tsx` | 新建 |
| `src/pages/admin/scripts/ScriptSheet.tsx` | 新建（新增/编辑抽屉） |
| `src/pages/admin/scripts/ImportModal.tsx` | 新建 |
| `src/pages/supervisor/script-labels.tsx` | 新建 |
| `src/App.tsx` | 修改：注册新路由 |
| `src/pages/admin/scripts/__tests__/list.test.tsx` | 新建 |
| `src/pages/admin/scripts/__tests__/import-parser.test.ts` | 新建 |
| `src/pages/supervisor/__tests__/supervisor-labels.test.tsx` | 新建 |
| `src/services/__tests__/signal-inference.test.ts` | 新建 |
