// 案件超期 / 失联报警 — v1.5.7 ⭐⭐
// 防止案件烂在催收员私海：N 天未联系 / 连续失联 / 接触阻断 自动入此队列
// v1.6.5 — 加分页 + debounce 搜索
import { AlertTriangle, CheckCircle2, Phone, RefreshCw, UserX, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { HelpPanel } from "../../../components/ui/HelpPanel";
import { PaginationBar } from "../../../components/ui/PaginationBar";
import { SearchInput } from "../../../components/ui/SearchInput";
import { useDebouncedValue } from "../../../hooks/useDebouncedValue";
import { SUPERVISOR_PROJECT_FILTERS } from "../_shared/projectFilters";

const PAGE_SIZE = 15;

interface CaseAlert {
  id: number;
  owner: string;
  building: string;
  amount: number;
  agent: string;
  alert_type: "stale" | "unreachable" | "blocked";
  alert_label: string;
  alert_badge: string;
  days: number;
  last_contact: string;
  project_name: string;
}

const MOCK_ALERTS: CaseAlert[] = [
  { id: 1, owner: "梁建国", building: "7-2301", amount: 6840, agent: "李小红",
    alert_type: "stale", alert_label: "停滞 14 天", alert_badge: "ds-badge ds-badge-orange",
    days: 14, last_contact: "2026-04-24", project_name: "金桂园 2026 年欠费催收" },
  { id: 2, owner: "吴雪梅", building: "2-1105", amount: 4920, agent: "陈明远",
    alert_type: "unreachable", alert_label: "连续 5 通失联", alert_badge: "ds-badge ds-badge-red",
    days: 5, last_contact: "2026-05-05", project_name: "翠湖湾电梯专项整改" },
  { id: 3, owner: "徐明华", building: "1-0402", amount: 9360, agent: "王芳芳",
    alert_type: "blocked", alert_label: "已被业主拉黑", alert_badge: "ds-badge ds-badge-red",
    days: 8, last_contact: "2026-04-30", project_name: "金桂园 2026 年欠费催收" },
  { id: 4, owner: "郑丽娟", building: "4-1801", amount: 3280, agent: "张建华",
    alert_type: "stale", alert_label: "停滞 21 天", alert_badge: "ds-badge ds-badge-red",
    days: 21, last_contact: "2026-04-17", project_name: "翠湖湾电梯专项整改" },
];

const REASSIGN_TARGETS = ["李小红", "王芳芳", "陈明远", "张建华", "刘晓娟"];

type AlertTypeFilter = "all" | "stale" | "unreachable" | "blocked";

export function SupervisorCaseAlertsPage() {
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState<CaseAlert[]>(MOCK_ALERTS);
  const [handled, setHandled] = useState<Map<number, string>>(new Map()); // id -> 处置标签
  const [typeFilter, setTypeFilter] = useState<AlertTypeFilter>("all");
  const [projectFilter, setProjectFilter] = useState<string>("全部项目");
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(1);
  const debouncedKw = useDebouncedValue(keyword, 300);
  const [reassignTarget, setReassignTarget] = useState<CaseAlert | null>(null);
  const [confirmRelease, setConfirmRelease] = useState<CaseAlert | null>(null);

  const filtered = useMemo(() => {
    const kw = debouncedKw.trim().toLowerCase();
    return alerts.filter((a) => {
      if (typeFilter !== "all" && a.alert_type !== typeFilter) return false;
      if (projectFilter !== "全部项目" && a.project_name !== projectFilter) return false;
      if (kw && !`${a.owner} ${a.building}`.toLowerCase().includes(kw)) return false;
      return true;
    });
  }, [alerts, typeFilter, projectFilter, debouncedKw]);
  const total = filtered.length;
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  function handleUrge(a: CaseAlert) {
    alert(`已给催收员 ${a.agent} 发送催办通知（业主：${a.owner} / ${a.building}）`);
    setHandled((prev) => new Map(prev).set(a.id, "已催办"));
  }

  function handleReassignConfirm(targetAgent: string) {
    if (!reassignTarget) return;
    alert(`已将 ${reassignTarget.owner} / ${reassignTarget.building} 重派给 ${targetAgent}`);
    setAlerts((prev) => prev.filter((x) => x.id !== reassignTarget.id));
    setReassignTarget(null);
  }

  function handleReleaseConfirm() {
    if (!confirmRelease) return;
    alert(`已将 ${confirmRelease.owner} / ${confirmRelease.building} 释放回公海`);
    setAlerts((prev) => prev.filter((x) => x.id !== confirmRelease.id));
    setConfirmRelease(null);
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">案件超期 / 失联报警</div>
          <div className="page-subtitle">自动监测「烂在私海」的案件，督导决定释放 / 重派 / 转法务</div>
        </div>
      </div>

      <HelpPanel
        tone="warn"
        dismissKey="/supervisor/case-alerts"
        title="3 类报警自动入队规则"
        bullets={[
          <><strong>停滞</strong>（橙）：案件 ≥14 天未拨打，催收员可能在拖延或忘了；推荐操作「催办」让催收员收到提醒</>,
          <><strong>连续失联</strong>（红）：连续 5 通拨号未接通，业主可能换号或刻意躲；推荐「派给老带新」或「调整时段」</>,
          <><strong>被拉黑</strong>（红）：业主明确表示拒接 / 加黑名单 / 投诉骚扰；必须「释放回公海 + 换催收员」否则继续打就是违规</>,
        ]}
        footer="本页只是「报警入口」，案件本身仍在催收员私海。督导操作后才会变更归属。"
      />

      {/* 顶部过滤条 */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <SearchInput
          value={keyword}
          onChange={(v) => { setKeyword(v); setPage(1); }}
          placeholder="按业主姓名 / 房号搜索"
          width={220}
        />
        <select className="filter-select" value={projectFilter} onChange={(e) => { setProjectFilter(e.target.value); setPage(1); }}>
          {SUPERVISOR_PROJECT_FILTERS.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        {(keyword || projectFilter !== "全部项目" || typeFilter !== "all") && (
          <button type="button" className="ds-btn ds-btn-ghost ds-btn-sm" onClick={() => { setKeyword(""); setProjectFilter("全部项目"); setTypeFilter("all"); setPage(1); }}>
            清空筛选
          </button>
        )}
      </div>

      <div className="filters-bar" style={{ marginBottom: 12 }}>
        {[
          { v: "all" as const, label: `全部 (${alerts.length})` },
          { v: "stale" as const, label: `停滞 (${alerts.filter((a) => a.alert_type === "stale").length})` },
          { v: "unreachable" as const, label: `失联 (${alerts.filter((a) => a.alert_type === "unreachable").length})` },
          { v: "blocked" as const, label: `被拉黑 (${alerts.filter((a) => a.alert_type === "blocked").length})` },
        ].map((f) => (
          <button
            key={f.v}
            type="button"
            className={`ds-btn ${typeFilter === f.v ? "ds-btn-primary" : "ds-btn-secondary"} ds-btn-sm`}
            onClick={() => { setTypeFilter(f.v); setPage(1); }}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>业主 / 房号</th>
              <th>项目</th>
              <th>金额</th>
              <th>催收员</th>
              <th>报警类型</th>
              <th>上次联系</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 && (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: 32, color: "var(--color-neutral-400)" }}>
                  暂无符合条件的报警
                </td>
              </tr>
            )}
            {visible.map((a) => {
              const handledLabel = handled.get(a.id);
              return (
                <tr key={a.id} style={handledLabel ? { background: "#f9fafb", opacity: 0.7 } : {}}>
                  <td><strong>{a.owner}</strong> / {a.building}</td>
                  <td style={{ fontSize: 12, color: "var(--color-primary)" }}>📁 {a.project_name}</td>
                  <td>¥{a.amount.toLocaleString("zh-CN")}</td>
                  <td>{a.agent}</td>
                  <td>
                    <span className={a.alert_badge}>{a.alert_label}</span>
                    {a.alert_type === "blocked" && <UserX className="w-3 h-3" style={{ color: "var(--color-danger)", marginLeft: 4, display: "inline" }} />}
                    {handledLabel && (
                      <span className="ds-badge ds-badge-gray" style={{ fontSize: 10, marginLeft: 4 }}>
                        <CheckCircle2 className="w-3 h-3" style={{ display: "inline", marginRight: 2 }} />
                        {handledLabel}
                      </span>
                    )}
                  </td>
                  <td style={{ fontSize: 12, color: "var(--color-neutral-500)" }}>{a.last_contact}</td>
                  <td>
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                      {a.alert_type === "stale" && (
                        <button type="button" className="ds-btn ds-btn-primary ds-btn-sm" onClick={() => handleUrge(a)} disabled={!!handledLabel}>
                          <Phone className="w-3 h-3" /> 催办
                        </button>
                      )}
                      {a.alert_type === "unreachable" && (
                        <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" onClick={() => setReassignTarget(a)}>
                          <RefreshCw className="w-3 h-3" /> 重派
                        </button>
                      )}
                      {a.alert_type === "blocked" && (
                        <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" style={{ color: "var(--color-danger)" }} onClick={() => setConfirmRelease(a)}>
                          <AlertTriangle className="w-3 h-3" /> 释放公海
                        </button>
                      )}
                      <button type="button" className="ds-btn ds-btn-ghost ds-btn-sm" onClick={() => navigate(`/supervisor/cases/${a.id}`)}>详情</button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <PaginationBar
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          onPageChange={setPage}
        />
      </div>

      {/* 重派 modal */}
      {reassignTarget && (
        <ReassignModal
          target={reassignTarget}
          onClose={() => setReassignTarget(null)}
          onConfirm={handleReassignConfirm}
        />
      )}

      {/* 释放公海确认 */}
      {confirmRelease && (
        <ConfirmModal
          title={`释放回公海：${confirmRelease.owner} / ${confirmRelease.building}`}
          message="该案件将从当前催收员私海移除，回到公海池等待重新分配。该操作将记入审计日志。"
          confirmLabel="确认释放"
          confirmDanger
          onClose={() => setConfirmRelease(null)}
          onConfirm={handleReleaseConfirm}
        />
      )}
    </div>
  );
}

function ReassignModal({ target, onClose, onConfirm }: { target: CaseAlert; onClose: () => void; onConfirm: (agent: string) => void }) {
  const [agent, setAgent] = useState("");
  const candidates = REASSIGN_TARGETS.filter((n) => n !== target.agent);
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }} onClick={onClose}>
      <div style={{ background: "white", borderRadius: 8, width: 460, maxWidth: "92%" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ padding: 16, borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontWeight: 600 }}>重派案件：{target.owner} / {target.building}</span>
          <button type="button" onClick={onClose} style={{ border: "none", background: "transparent", cursor: "pointer" }}><X size={18} /></button>
        </div>
        <div style={{ padding: 16 }}>
          <p style={{ fontSize: 13, color: "#374151", marginBottom: 12, lineHeight: 1.7 }}>
            当前催收员：<strong>{target.agent}</strong>。该业主连续 5 通失联，建议改派给善于多次跟进的催收员。
          </p>
          <div className="form-group">
            <label className="form-label">重派给<span className="req">*</span></label>
            <select className="form-control" value={agent} onChange={(e) => setAgent(e.target.value)}>
              <option value="">请选择催收员</option>
              {candidates.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <div style={{ background: "#fffbeb", padding: 10, borderRadius: 6, fontSize: 12, color: "#78350f" }}>
            ⚠ 重派后原催收员将看到该案件已转出，新催收员收到通知；操作记入审计日志。
          </div>
        </div>
        <div style={{ padding: 16, borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button type="button" className="ds-btn ds-btn-secondary" onClick={onClose}>取消</button>
          <button type="button" className="ds-btn ds-btn-primary" disabled={!agent} onClick={() => onConfirm(agent)}>确认重派</button>
        </div>
      </div>
    </div>
  );
}

function ConfirmModal({ title, message, confirmLabel, confirmDanger, onClose, onConfirm }: { title: string; message: string; confirmLabel: string; confirmDanger?: boolean; onClose: () => void; onConfirm: () => void }) {
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }} onClick={onClose}>
      <div style={{ background: "white", borderRadius: 8, width: 440, maxWidth: "92%" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ padding: 16, borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontWeight: 600 }}>{title}</span>
          <button type="button" onClick={onClose} style={{ border: "none", background: "transparent", cursor: "pointer" }}><X size={18} /></button>
        </div>
        <div style={{ padding: 16, fontSize: 13.5, color: "#374151", lineHeight: 1.7 }}>{message}</div>
        <div style={{ padding: 16, borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button type="button" className="ds-btn ds-btn-secondary" onClick={onClose}>取消</button>
          <button
            type="button"
            className="ds-btn ds-btn-primary"
            style={confirmDanger ? { background: "var(--color-danger)", borderColor: "var(--color-danger)" } : undefined}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
