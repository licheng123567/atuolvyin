// 升级案件处理 — v0.6.0 彻底重构(按用户描述)
//
// 用户反馈:外层 4 按钮重复(发起减免 / 转法务 / 查看历史 / 介入处理);
// 介入处理弹窗模式 4 与「发起减免」重复;模式 2-3 是 mock alert 无后端。
// 重构方案:
//   外层只留 2 按钮:[介入处理] + [详情](原「查看历史」)
//   介入处理弹窗内嵌 5 选项:
//     ① 亲自致电业主(导航到案件详情拨号)
//     ② 标记陪同监听 → POST /supervisor/escalated/{id}/mark-shadow-listening
//     ③ 直接结案/标坏账(必填原因) → POST /supervisor/escalated/{id}/close-as-uncollectible
//     ④ 发起减免/分期 → 打开 DiscountRequestModal
//     ⑤ 转法务 → 打开 TransferLegalDirectModal(与案件详情页同款)
import { useCustom, useCustomMutation } from "@refinedev/core";
import {
  AlertCircle, ArrowUpRight, BadgePercent,
  ExternalLink, Headphones, Loader2, Phone, Scale, Search, X,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DiscountRequestModal } from "../../../components/discount/DiscountRequestModal";
import { TransferLegalDirectModal } from "../../../components/supervisor/TransferLegalDirectModal";
import { HelpPanel } from "../../../components/ui/HelpPanel";
import { SUPERVISOR_PROJECT_FILTERS } from "../_shared/projectFilters";

interface EscalatedCase {
  id: number;
  owner_name: string;
  building: string;
  amount: number;
  months_overdue: number;
  reason: string;
  raised_by: string;
  raised_at: string;
  priority: "high" | "medium";
  project_name: string;
}

interface EscalatedListResp {
  items: EscalatedCase[];
  total: number;
  page: number;
  page_size: number;
}

const PAGE_SIZE = 20;

const MOCK_CASES: EscalatedCase[] = [
  {
    id: 101, owner_name: "张大伟", building: "3-1201",
    amount: 24800, months_overdue: 18,
    reason: "业主多次拒接电话，并明确表示「不想交」，存在恶意拖欠倾向",
    raised_by: "李小红", raised_at: "今天 14:28",
    priority: "high", project_name: "金桂园 2026 年欠费催收",
  },
  {
    id: 102, owner_name: "王秀英", building: "8-0902",
    amount: 12600, months_overdue: 11,
    reason: "业主反映物业服务质量问题，要求减免 50%，金额超出协调员权限",
    raised_by: "王芳芳", raised_at: "今天 11:15",
    priority: "high", project_name: "金桂园 2026 年欠费催收",
  },
  {
    id: 103, owner_name: "刘建国", building: "1-0301",
    amount: 8400, months_overdue: 8,
    reason: "业主已搬离 6 个月，新住户拒绝代缴，需法务介入确认责任主体",
    raised_by: "张建华", raised_at: "昨天 16:42",
    priority: "medium", project_name: "翠湖湾电梯专项整改",
  },
];

export function SupervisorEscalatedPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [activeCase, setActiveCase] = useState<EscalatedCase | null>(null);
  // v0.6.0 — 介入处理统一一个 modal,内部 5 选项;额外 sub-modal:close / discount / transfer-legal
  const [intervenOpen, setIntervenOpen] = useState(false);
  const [closeTarget, setCloseTarget] = useState<EscalatedCase | null>(null);
  const [discountTarget, setDiscountTarget] = useState<EscalatedCase | null>(null);
  const [transferLegalTarget, setTransferLegalTarget] = useState<EscalatedCase | null>(null);
  const [projectFilter, setProjectFilter] = useState<string>("全部项目");
  const [keyword, setKeyword] = useState("");

  // v1.6.4 — 优先 wire 后端;查询失败或 0 条时 fallback 到 mock
  const { query } = useCustom<EscalatedListResp>({
    url: "supervisor/escalated-cases",
    method: "get",
    config: { query: { page, page_size: PAGE_SIZE } },
    queryOptions: { staleTime: 30_000, retry: false },
  });
  const resp = query.data?.data;
  const cases: EscalatedCase[] =
    resp && resp.items.length > 0 ? resp.items : (resp ? [] : MOCK_CASES);
  const total = resp?.total ?? cases.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const usingMock = !resp;

  const visible = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    return cases.filter((c) => {
      if (projectFilter !== "全部项目" && c.project_name !== projectFilter) return false;
      if (kw && !`${c.owner_name} ${c.building}`.toLowerCase().includes(kw)) return false;
      return true;
    });
  }, [cases, projectFilter, keyword]);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">升级案件处理</div>
          <div className="page-subtitle">大额/疑难案件督导处置 — 由催收员标记升级，需督导介入</div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <div style={{ position: "relative" }}>
            <Search size={14} style={{ position: "absolute", left: 8, top: "50%", transform: "translateY(-50%)", color: "var(--color-neutral-400)" }} />
            <input
              type="text"
              className="form-control"
              placeholder="按业主姓名 / 房号搜索"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              style={{ paddingLeft: 28, width: 200, height: 32 }}
            />
          </div>
          <select
            className="filter-select"
            value={projectFilter}
            onChange={(e) => setProjectFilter(e.target.value)}
          >
            {SUPERVISOR_PROJECT_FILTERS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
      </div>

      <HelpPanel
        tone="warn"
        dismissKey="/supervisor/escalated-v060"
        title="升级案件 4 类典型场景"
        bullets={[
          <><strong>金额超权</strong>：业主要求减免/分期超出催收员权限（&gt;¥10,000 或减免&gt;30%）</>,
          <><strong>话术失效</strong>：连续 3 次催收无果，业主明确拒缴或失联超 30 天</>,
          <><strong>风险升级</strong>：触发 L2 风控（投诉/法律威胁），AI 自动建议升级</>,
          <><strong>责任主体不清</strong>：业主已搬离 / 转租 / 死亡等需进一步法律确认</>,
        ]}
        footer={
          <>
            <strong>v0.6.0 改版:</strong>外层只保留<strong>「介入处理」</strong>(打开 5
            选项弹窗:亲自致电 / 陪同监听 / 直接结案 / 减免分期 / 转法务) +
            <strong>「详情」</strong>(查看案件完整历史)。原外层「发起减免」「转法务」「查看历史」
            已合并 / 重命名,避免重复。
          </>
        }
      />

      <div className="status-bar">
        <div className="status-bar-item" style={{ color: "var(--color-danger)" }}>
          <AlertCircle className="w-4 h-4" /> 高优先级 <strong>{visible.filter((c) => c.priority === "high").length} 条</strong>
        </div>
        <div className="status-bar-item">
          <ArrowUpRight className="w-4 h-4" /> 待处理 <strong>{visible.length} 条</strong>
        </div>
      </div>

      {usingMock && (
        <div
          style={{
            padding: "8px 12px", background: "#fef3c7", border: "1px solid #fde68a",
            borderRadius: 6, fontSize: 12, color: "#78350f", marginBottom: 8,
          }}
        >
          ⓘ 后端无升级案件数据，当前展示 mock 演示数据
        </div>
      )}

      <div className="ds-card">
        <div className="card-body" style={{ padding: 0 }}>
          {visible.length === 0 && (
            <div style={{ padding: 32, textAlign: "center", color: "var(--color-neutral-400)" }}>
              暂无符合条件的升级案件
            </div>
          )}
          {visible.map((c) => (
            <div
              key={c.id}
              style={{
                padding: 16,
                borderBottom: "1px solid var(--color-neutral-100)",
                borderLeft: c.priority === "high" ? "3px solid var(--color-danger)" : "3px solid var(--color-warning)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6, flexWrap: "wrap" }}>
                    <span style={{ fontWeight: 600, fontSize: 14 }}>
                      {c.owner_name} / {c.building}
                    </span>
                    <span className="ds-badge ds-badge-blue" style={{ fontSize: 11 }} title={c.project_name}>
                      📁 {c.project_name}
                    </span>
                    <span className="ds-badge ds-badge-red" style={{ fontSize: 11 }}>
                      ¥{c.amount.toLocaleString("zh-CN")}
                    </span>
                    <span className="ds-badge ds-badge-orange" style={{ fontSize: 11 }}>
                      欠 {c.months_overdue} 月
                    </span>
                    {c.priority === "high" && (
                      <span className="ds-badge ds-badge-red" style={{ fontSize: 11 }}>高优先级</span>
                    )}
                  </div>
                  <div style={{ fontSize: 13, color: "var(--color-neutral-700)", marginBottom: 6 }}>
                    {c.reason}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--color-neutral-500)" }}>
                    催收员 <strong>{c.raised_by}</strong> 于 {c.raised_at} 升级
                  </div>
                </div>
                {/* v0.6.0 — 外层精简为 2 按钮 */}
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <button
                    type="button"
                    className="ds-btn ds-btn-primary ds-btn-sm"
                    onClick={() => { setActiveCase(c); setIntervenOpen(true); }}
                  >
                    <Headphones className="w-3.5 h-3.5" />
                    介入处理
                  </button>
                  <button
                    type="button"
                    className="ds-btn ds-btn-ghost ds-btn-sm"
                    onClick={() => navigate(`/supervisor/cases/${c.id}`)}
                  >
                    详情
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
        {!usingMock && totalPages > 1 && (
          <div
            style={{
              padding: 12, borderTop: "1px solid var(--color-neutral-100)",
              display: "flex", justifyContent: "center", alignItems: "center",
              gap: 8, fontSize: 13,
            }}
          >
            <button
              type="button"
              className="ds-btn ds-btn-ghost ds-btn-sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              ‹ 上一页
            </button>
            <span style={{ color: "var(--color-neutral-500)" }}>
              第 {page} / {totalPages} 页 · 共 {total} 条
            </span>
            <button
              type="button"
              className="ds-btn ds-btn-ghost ds-btn-sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              下一页 ›
            </button>
          </div>
        )}
      </div>

      {/* v0.6.0 — 介入处理统一弹窗,5 个选项 */}
      {intervenOpen && activeCase && (
        <InterveneActionsModal
          activeCase={activeCase}
          onClose={() => { setIntervenOpen(false); setActiveCase(null); }}
          onCall={() => navigate(`/supervisor/cases/${activeCase.id}`)}
          onShadowMarked={() => {
            setIntervenOpen(false);
            setActiveCase(null);
            void query.refetch();
            alert("✓ 已标记为督导陪同 — 催收员下次拨打时会通知你");
          }}
          onPickClose={() => { setIntervenOpen(false); setCloseTarget(activeCase); }}
          onPickDiscount={() => { setIntervenOpen(false); setDiscountTarget(activeCase); }}
          onPickTransferLegal={() => { setIntervenOpen(false); setTransferLegalTarget(activeCase); }}
        />
      )}

      {/* ③ 直接结案 / 标坏账 — 必填原因 */}
      {closeTarget && (
        <CloseAsUncollectibleModal
          activeCase={closeTarget}
          onClose={() => { setCloseTarget(null); setActiveCase(null); }}
          onDone={() => {
            setCloseTarget(null);
            setActiveCase(null);
            void query.refetch();
            alert("✓ 已提交物业管理员审批");
          }}
        />
      )}

      {/* ④ 减免申请 modal */}
      {discountTarget && (
        <DiscountRequestModal
          caseId={discountTarget.id}
          originalAmount={discountTarget.amount}
          ownerName={discountTarget.owner_name}
          onClose={() => { setDiscountTarget(null); setActiveCase(null); }}
          onSuccess={(offerId) => {
            setDiscountTarget(null);
            setActiveCase(null);
            alert(`✓ 减免申请 #${offerId} 已提交`);
          }}
        />
      )}

      {/* ⑤ 直接转法务 — 复用案件详情页同款 modal */}
      {transferLegalTarget && (
        <TransferLegalDirectModal
          caseId={transferLegalTarget.id}
          caseLabel={`${transferLegalTarget.owner_name} / ${transferLegalTarget.building}`}
          onClose={() => { setTransferLegalTarget(null); setActiveCase(null); }}
          onDone={() => {
            setTransferLegalTarget(null);
            setActiveCase(null);
            void query.refetch();
            alert("✓ 案件已直接移交法务");
          }}
        />
      )}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
// 介入处理 5 选项弹窗
// ────────────────────────────────────────────────────────────────
function InterveneActionsModal({
  activeCase, onClose, onCall, onShadowMarked,
  onPickClose, onPickDiscount, onPickTransferLegal,
}: {
  activeCase: EscalatedCase;
  onClose: () => void;
  onCall: () => void;
  onShadowMarked: () => void;
  onPickClose: () => void;
  onPickDiscount: () => void;
  onPickTransferLegal: () => void;
}) {
  const { mutate: markShadow, mutation: shadowMutation } = useCustomMutation();
  const handleMarkShadow = () => {
    markShadow(
      {
        url: `supervisor/escalated/${activeCase.id}/mark-shadow-listening`,
        method: "post",
        values: { note: null },
      },
      {
        onSuccess: () => onShadowMarked(),
        onError: (err) => {
          alert(`标记失败:${(err as { message?: string }).message ?? "请重试"}`);
        },
      },
    );
  };

  return (
    <BasicModal
      title={`介入处理:${activeCase.owner_name} / ${activeCase.building}`}
      onClose={onClose}
    >
      <p style={{ fontSize: 13, color: "#374151", marginBottom: 12, lineHeight: 1.7 }}>
        选择介入方式(操作会被审计记录到案件时间线):
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <ActionRow
          icon={<Phone className="w-4 h-4" />}
          title="① 督导亲自致电业主"
          desc="督导本人直接拨打业主电话,由你完成本次沟通;催收员收到通知不再跟进"
          actionLabel="去拨号 →"
          onClick={onCall}
        />
        <ActionRow
          icon={<Headphones className="w-4 h-4" />}
          title="② 标记陪同 / 监听下一通"
          desc="将案件标为「督导陪同」(case.shadow_supervisor_id 设为你),催收员下次拨打时督导自动收到通知,可在实时通话墙监听并随时强制接管"
          actionLabel={shadowMutation.isPending ? "提交中…" : "标记陪同"}
          actionPending={shadowMutation.isPending}
          onClick={handleMarkShadow}
        />
        <ActionRow
          icon={<ExternalLink className="w-4 h-4" />}
          title="③ 直接结案 / 标坏账"
          desc="评估后认为无回收价值,案件 stage 置为 pending_close(待物业管理员二审);需填写结案原因"
          actionLabel="填写原因"
          onClick={onPickClose}
        />
        <ActionRow
          icon={<BadgePercent className="w-4 h-4" />}
          title="④ 发起减免 / 分期申请"
          desc="业主明确「无力一次性缴清 / 服务异议 / 需分期」时,督导代催收员发起减免 offer,按金额自动决定督导/物业管理员审批"
          actionLabel="发起申请"
          onClick={onPickDiscount}
        />
        <ActionRow
          icon={<Scale className="w-4 h-4" />}
          title="⑤ 转法务"
          desc="案件移交法务专员,案件 stage → legal;若已有催收员转法务申请,请去案件详情走「审批转法务」"
          actionLabel="移交法务"
          onClick={onPickTransferLegal}
        />
      </div>
    </BasicModal>
  );
}

// ────────────────────────────────────────────────────────────────
// 直接结案 / 标坏账 — 必填原因
// ────────────────────────────────────────────────────────────────
function CloseAsUncollectibleModal({
  activeCase, onClose, onDone,
}: {
  activeCase: EscalatedCase;
  onClose: () => void;
  onDone: () => void;
}) {
  const [reason, setReason] = useState("");
  const { mutate, mutation } = useCustomMutation();

  const handleSubmit = () => {
    const trimmed = reason.trim();
    if (!trimmed) return;
    mutate(
      {
        url: `supervisor/escalated/${activeCase.id}/close-as-uncollectible`,
        method: "post",
        values: { reason: trimmed },
      },
      {
        onSuccess: () => onDone(),
        onError: (err) => {
          alert(`提交失败:${(err as { message?: string }).message ?? "请重试"}`);
        },
      },
    );
  };

  return (
    <BasicModal
      title={`直接结案 / 标坏账:${activeCase.owner_name} / ${activeCase.building}`}
      onClose={onClose}
    >
      <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded p-2 mb-3">
        提交后案件 stage → <strong>pending_close</strong>,等物业管理员二审。
        审计日志留痕,可回溯。
      </div>
      <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
        结案原因 <span className="text-red-500">*</span>
      </label>
      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        rows={4}
        placeholder="必填,说明为何无回收价值(如:业主已搬离失联 6 个月 + 无资产 + 调查无可执行财产 = 评估为坏账)"
        className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded resize-none"
        autoFocus
      />
      <div className="flex items-center justify-end gap-2 mt-3">
        <button
          type="button"
          onClick={onClose}
          className="px-3 py-1.5 text-sm rounded border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-50)]"
        >
          取消
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!reason.trim() || mutation.isPending}
          className="px-4 py-1.5 text-sm rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 flex items-center gap-1.5"
        >
          {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          提交审批
        </button>
      </div>
    </BasicModal>
  );
}

// ────────────────────────────────────────────────────────────────
// 基础 modal + ActionRow(本文件内部用)
// ────────────────────────────────────────────────────────────────
function BasicModal({
  title, children, onClose,
}: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}
      onClick={onClose}
    >
      <div
        style={{ background: "white", borderRadius: 8, width: 580, maxWidth: "92%", maxHeight: "85vh", overflowY: "auto" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ padding: 16, borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center", position: "sticky", top: 0, background: "white" }}>
          <span style={{ fontWeight: 600 }}>{title}</span>
          <button type="button" onClick={onClose} style={{ border: "none", background: "transparent", cursor: "pointer" }}>
            <X size={18} />
          </button>
        </div>
        <div style={{ padding: 16 }}>{children}</div>
      </div>
    </div>
  );
}

function ActionRow({
  icon, title, desc, actionLabel, actionPending, onClick,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  actionLabel: string;
  actionPending?: boolean;
  onClick: () => void;
}) {
  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 6, padding: 12, display: "flex", alignItems: "flex-start", gap: 10 }}>
      <div style={{ marginTop: 2, color: "var(--color-primary)" }}>{icon}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{title}</div>
        <div style={{ fontSize: 12, color: "#6b7280", lineHeight: 1.6 }}>{desc}</div>
      </div>
      <button
        type="button"
        className="ds-btn ds-btn-primary ds-btn-sm"
        onClick={onClick}
        disabled={actionPending}
      >
        {actionPending && <Loader2 className="w-3 h-3 animate-spin mr-1" />}
        {actionLabel}
      </button>
    </div>
  );
}
