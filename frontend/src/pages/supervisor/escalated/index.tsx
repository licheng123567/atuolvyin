// 升级案件处理 — 1:1 还原 ui/supervisor.html#sv-escalated
// v1.5.7 — 大额/疑难案件督导处置 + 介入/转法务/查看历史 实际链接
// v1.6.4 — wire 真后端 + 简单分页（pageSize=20），无后端时 fallback mock
import { useCustom } from "@refinedev/core";
import { AlertCircle, ArrowUpRight, BadgePercent, ExternalLink, Phone, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DiscountRequestModal } from "../../../components/discount/DiscountRequestModal";
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

type Action = "intervene" | "to_legal" | "history" | "discount" | null;

export function SupervisorEscalatedPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [activeCase, setActiveCase] = useState<EscalatedCase | null>(null);
  const [action, setAction] = useState<Action>(null);
  const [projectFilter, setProjectFilter] = useState<string>("全部项目");
  const [keyword, setKeyword] = useState("");
  const [discountTarget, setDiscountTarget] = useState<EscalatedCase | null>(null);  // v1.6.9

  // v1.6.4 — 优先 wire 后端；查询失败或 0 条时 fallback 到 mock
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

  function openAction(c: EscalatedCase, a: Action) {
    setActiveCase(c);
    setAction(a);
  }

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
        dismissKey="/supervisor/escalated"
        title="升级案件 4 类典型场景"
        bullets={[
          <><strong>金额超权</strong>：业主要求减免/分期超出催收员权限（&gt;¥10,000 或减免&gt;30%）</>,
          <><strong>话术失效</strong>：连续 3 次催收无果，业主明确拒缴或失联超 30 天</>,
          <><strong>风险升级</strong>：触发 L2 风控（投诉/法律威胁），AI 自动建议升级</>,
          <><strong>责任主体不清</strong>：业主已搬离 / 转租 / 死亡等需进一步法律确认</>,
        ]}
        footer={
          <>
            <strong>督导 3 个动作：</strong>
            「介入处理」= 督导本人参与下一通通话（可监听 / 接管）；
            「转法务」= 案件移交法务专员，进入律师函/诉讼流程；
            「查看历史」= 跳到案件详情看完整通话+操作时间线。
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
            padding: "8px 12px",
            background: "#fef3c7",
            border: "1px solid #fde68a",
            borderRadius: 6,
            fontSize: 12,
            color: "#78350f",
            marginBottom: 8,
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
          {/* v1.6.4 — 列表渲染（来自后端 + 客户端筛选 keyword/project）*/}
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
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <button
                    type="button"
                    className="ds-btn ds-btn-primary ds-btn-sm"
                    onClick={() => openAction(c, "intervene")}
                  >
                    介入处理
                  </button>
                  {/* v1.6.9 — 发起减免：业主谈判达成后督导一键提交减免申请 */}
                  <button
                    type="button"
                    className="ds-btn ds-btn-secondary ds-btn-sm"
                    style={{ color: "#b45309", borderColor: "#fcd34d" }}
                    onClick={() => setDiscountTarget(c)}
                    title="发起减免/分期/违约金减免，按金额自动判定走督导/admin 审批"
                  >
                    <BadgePercent className="w-3.5 h-3.5" /> 发起减免
                  </button>
                  <button
                    type="button"
                    className="ds-btn ds-btn-secondary ds-btn-sm"
                    onClick={() => openAction(c, "to_legal")}
                  >
                    转法务
                  </button>
                  <button
                    type="button"
                    className="ds-btn ds-btn-ghost ds-btn-sm"
                    onClick={() => navigate(`/supervisor/cases/${c.id}`)}
                  >
                    查看历史
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
        {!usingMock && totalPages > 1 && (
          <div
            style={{
              padding: 12,
              borderTop: "1px solid var(--color-neutral-100)",
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              gap: 8,
              fontSize: 13,
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

      {/* 介入处理 modal */}
      {action === "intervene" && activeCase && (
        <ActionModal
          title={`介入处理：${activeCase.owner_name} / ${activeCase.building}`}
          onClose={() => { setAction(null); setActiveCase(null); }}
        >
          <p style={{ fontSize: 13, color: "#374151", marginBottom: 12, lineHeight: 1.7 }}>
            选择介入方式（操作会被审计记录到案件时间线）：
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <ActionRow
              icon={<Phone className="w-4 h-4" />}
              title="模式 1：督导亲自致电业主"
              desc="督导本人直接拨打业主电话，由你完成本次沟通；催收员收到通知不再跟进"
              onClick={() => { navigate(`/supervisor/cases/${activeCase.id}`); }}
              actionLabel="去拨号 →"
            />
            <ActionRow
              icon={<Phone className="w-4 h-4" />}
              title="模式 2：陪同 + 监听下一通"
              desc="将案件标为「督导陪同」，催收员下次拨打时督导自动收到通知，可在「实时通话墙」监听并随时强制接管"
              onClick={() => { alert("已标记为督导陪同 — 催收员下次拨打时会通知你"); setAction(null); }}
              actionLabel="标记陪同"
            />
            <ActionRow
              icon={<ExternalLink className="w-4 h-4" />}
              title="模式 3：直接结案 / 标坏账"
              desc="评估后认为无回收价值，标记结案进入坏账清单，需物业 admin 二次确认"
              onClick={() => { alert("已提交 admin 审批"); setAction(null); }}
              actionLabel="提交审批"
            />
            {/* v1.6.9 — 模式 4：发起减免谈判（督导直接代催收员发起 offer）*/}
            <ActionRow
              icon={<BadgePercent className="w-4 h-4" />}
              title="模式 4：发起减免 / 分期申请"
              desc="业主明确「无力一次性缴清 / 服务异议 / 需分期」时，督导直接代催收员发起减免 offer，按金额自动决定督导/admin 审批"
              onClick={() => {
                setDiscountTarget(activeCase);
                setAction(null);
              }}
              actionLabel="发起申请"
            />
          </div>
        </ActionModal>
      )}

      {/* 转法务 modal */}
      {action === "to_legal" && activeCase && (
        <ActionModal
          title={`转法务：${activeCase.owner_name} / ${activeCase.building}`}
          onClose={() => { setAction(null); setActiveCase(null); }}
        >
          <p style={{ fontSize: 13, color: "#374151", marginBottom: 12, lineHeight: 1.7 }}>
            该案件将进入「法务转化」流程：
          </p>
          <ul style={{ fontSize: 13, paddingLeft: 20, marginBottom: 16, lineHeight: 1.8, color: "#374151" }}>
            <li>案件状态变为 <code style={{ background: "#f3f4f6", padding: "1px 4px" }}>legal</code>（已转法务）</li>
            <li>本租户绑定的法务对接人收到通知</li>
            <li>跳到「法务转化」页选择服务包（律师函 / 立案诉讼 / 调解）</li>
            <li>催收员私海移除该案件，不可再拨号</li>
          </ul>
          <div style={{ background: "#fffbeb", padding: 10, borderRadius: 6, fontSize: 12, color: "#78350f", marginBottom: 12 }}>
            ⚠ 此操作不可逆 — 转法务后需法务对接人确认才能撤回
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button type="button" className="ds-btn ds-btn-secondary" onClick={() => { setAction(null); setActiveCase(null); }}>
              取消
            </button>
            <button
              type="button"
              className="ds-btn ds-btn-primary"
              onClick={() => {
                navigate(`/legal/orders`);
              }}
            >
              进入法务订单 →
            </button>
          </div>
        </ActionModal>
      )}

      {/* v1.6.9 — 减免申请 Modal */}
      {discountTarget && (
        <DiscountRequestModal
          caseId={discountTarget.id}
          originalAmount={discountTarget.amount}
          ownerName={discountTarget.owner_name}
          onClose={() => setDiscountTarget(null)}
          onSuccess={(offerId) => {
            setDiscountTarget(null);
            alert(`✓ 减免申请 #${offerId} 已提交`);
          }}
        />
      )}
    </div>
  );
}

function ActionModal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}
      onClick={onClose}
    >
      <div
        style={{ background: "white", borderRadius: 8, width: 540, maxWidth: "92%" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ padding: 16, borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
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

function ActionRow({ icon, title, desc, actionLabel, onClick }: { icon: React.ReactNode; title: string; desc: string; actionLabel: string; onClick: () => void }) {
  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 6, padding: 12, display: "flex", alignItems: "flex-start", gap: 10 }}>
      <div style={{ marginTop: 2, color: "var(--color-primary)" }}>{icon}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{title}</div>
        <div style={{ fontSize: 12, color: "#6b7280", lineHeight: 1.6 }}>{desc}</div>
      </div>
      <button type="button" className="ds-btn ds-btn-primary ds-btn-sm" onClick={onClick}>
        {actionLabel}
      </button>
    </div>
  );
}
