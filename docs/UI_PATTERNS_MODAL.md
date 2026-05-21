# UI 弹窗交互模式约定 — v0.5.6

> 本文是「**何时用中间 Dialog、何时用右侧 Drawer**」的产品 + 工程约定。新写弹窗前先翻这里;改老弹窗也按这里走。配套实现见 `frontend/src/components/ui/RightDrawer.tsx`。

## 背景

v0.5.6 之前,全项目 15+ 个弹窗组件**全部是中间居中 Modal**(`.ds-modal` 或 Tailwind 原生 fixed centered),0 个右侧 Drawer 实现。问题是:

- 「分配 / 重新分配 / 标记承诺缴费 / 法务接单选包」这类场景,操作时**业主信息列表需要持续可见**,被居中弹窗挡住屏幕中央就让人摸不到上下文。
- 弹窗宽度写死(常见 `max-w-md` 即 448px / `max-w-2xl` 即 896px),不同表单需要的宽度差异巨大,用户不能自己拖动调整。
- 大量信息展示(订单详情 / 文档列表)被压在窄居中弹窗里,纵向滚动疲惫。

v0.5.6 起,前端区分「中间 Dialog」与「右侧 Drawer」两类,按内容性质选。**不要求一次性全迁移**;新写按下表,老代码渐进改。

---

## 决策矩阵

| 内容类型 | 推荐 | 示例 |
|---|---|---|
| **简单确认** — 是/否、驳回理由 1 输入框 | 中间 Dialog ≤ **420px** | `RejectRequestModal` / `EscalateToAdminModal` 当前态 |
| **表单 ≤ 3 字段** — 升级督导、申请转法务、创建工单 | 中间 Dialog ≤ **520px** | `EscalateSupervisorModal` / `WorkOrderCreateModal` / `RequestLegalConversionModal` |
| **表单 ≥ 4 字段 / 需边看列表上下文** — 分配 / 重新分配 / 标记承诺缴费 / 法务接单选包 / 大额减免审批 | **右侧 Drawer**(可拖宽度) | `SupervisorReassignModal`(v0.5.6 已迁) / `LegalFinalizeModal`(下期迁) |
| **大量信息展示** — 订单详情、文书列表、活动时间线全量 | **右侧 Drawer ≥ 700px** 或全屏路由页 | `LegalDocumentModal`(下期迁) |
| **移动端** | 底部 BottomSheet 或全屏 | App-only,与桌面端解耦 |

边界情况:**如果你的弹窗在「3 字段」附近犹豫**,优先看「用户提交前是否需要参考左侧列表/上下文」。需要 → 右侧 Drawer;不需要 → 中间 Dialog。

---

## 实现规范

### 中间 Dialog(保留现有 `.ds-modal` 模式)

- 用 `<div className="modal-overlay">` + `<div className="ds-modal">` 标准三段式(modal-header / modal-body / modal-footer)
- 宽度通过 inline `style={{ maxWidth: 420 }}` 控制
- 关闭:点击 overlay 或 header X 按钮
- 不需要装额外依赖
- 参考:`frontend/src/components/admin/WorkOrderCreateModal.tsx`

### 右侧 Drawer(用 `RightDrawer` 共享组件)

```tsx
import { RightDrawer } from "@/components/ui/RightDrawer";

<RightDrawer
  open={open}
  onClose={() => setOpen(false)}
  title="重新分配案件"
  drawerKey="supervisor-reassign"     // ← 必填,每个 drawer 唯一,用于持久化宽度
  defaultWidth={520}                  // 可选,默认 480px
  footer={                            // 可选,放确认/取消按钮
    <>
      <button onClick={onClose}>取消</button>
      <button onClick={submit}>确认</button>
    </>
  }
>
  {/* drawer body content */}
</RightDrawer>
```

特性:

- 基于 `@radix-ui/react-dialog`(已装),自带 a11y(焦点陷阱 / ESC 关闭 / role=dialog)
- 左边缘可拖动调整宽度,范围 360px–80vw
- 关闭后宽度记 `localStorage["right-drawer-width-{drawerKey}"]`,下次打开自动还原
- 自带滑入动画 + overlay 淡入,与中间 Dialog 视觉风格一致

### 不要混用

- 同一交互场景不要既有 Dialog 又有 Drawer 入口(混乱)
- 不要在 Drawer 里套另一个 Drawer(嵌套层级失控);需要更深操作就开新页面

---

## 迁移进度

### v0.5.6(已落地)
- `SupervisorReassignModal`(督导重新分配)— 样板迁移

### v0.5.6 同期新增(直接用 Drawer 起步)
- `ProviderAssignDrawer`(服务商管理员分配案件)

### v0.5.8(2026-05-20 完成)— 6 个 modal 批量迁
- `LegalFinalizeModal`(法务接单选包,640px)
- `LegalDocumentModal`(文书查看,720px,大量信息)
- `ConvertToLegalModal`(申请/审批转法务,640px,2 模式)
- `MarkPromiseModal`(标记承诺缴费,520px,4 字段 + 需对照金额)
- `DiscountRequestModal`(减免申请,520px,4 字段)
- `RequestLegalConversionModal`(催收员申请转法务,520px,7 预设原因)

### 不迁(已对齐矩阵,中间 Dialog 合适)
- `RejectRequestModal` / `EscalateToAdminModal` / `EscalateSupervisorModal`(1-2 字段简单确认)
- `WorkOrderCreateModal` / `FollowUpNoteModal`(3 字段表单)
- `SupervisorCaseActionModal`(单 textarea)
- `PaymentLinkQrModal` / `InviteQrModal`(二维码扫码场景,居中合适)
- `AppIntroModal`(全屏引导)

### 总览

| 模态 类型 | 数量 | 比例 |
|---|---|---|
| 右侧 Drawer | 8 | 50% |
| 中间 Dialog | 8 | 50% |

---

## 与 DESIGN_SPEC.md 的关系

`docs/DESIGN_SPEC.md §2.1` 的「弹窗」表格被本文档拆细。设计文档保留对应表项 + 链接到本文,这里是 source of truth。
