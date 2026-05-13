// 案件分配 — 1:1 还原 ui/supervisor.html#sv-cases
// v1.5.7 — 左：公海案件 checkbox 列表 / 右：催收员工作量 bar
// v1.6.5 — 加分页 + debounce 搜索
// v1.6.10 — 左侧改用真实后端 GET /supervisor/cases，case.id 与 detail endpoint 对齐（修复 404）
import type { CrudFilter } from "@refinedev/core";
import { useList } from "@refinedev/core";
import { Eye, Info, MessageSquarePlus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FollowUpNoteModal } from "../../../components/case/FollowUpNoteModal";
import { PaginationBar } from "../../../components/ui/PaginationBar";
import { SearchInput } from "../../../components/ui/SearchInput";
import { useDebouncedValue } from "../../../hooks/useDebouncedValue";
import type { PaginatedResponse } from "../../../types";
import { SUPERVISOR_PROJECT_FILTERS } from "../_shared/projectFilters";

const PAGE_SIZE = 15;

function priorityTone(score: number): { color: string; label: string } {
  if (score >= 90) return { color: "var(--color-danger)", label: "紧急" };
  if (score >= 75) return { color: "var(--color-warning)", label: "高" };
  if (score >= 60) return { color: "#f59e0b", label: "中" };
  return { color: "var(--color-neutral-500)", label: "低" };
}

interface OwnerInfo {
  id: number;
  name: string;
  phone_masked: string;
  building: string | null;
  room: string | null;
  do_not_call: boolean;
}

interface BackendCase {
  id: number;
  owner: OwnerInfo;
  pool_type: string;
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
  priority_score: number;
  project_id: number | null;
  project_name: string | null;
  last_contact_at: string | null;
  assigned_to: number | null;
}

interface AgentLoad {
  name: string;
  current: number;
  capacity: number;
  status: "full" | "available";
}

const CAPACITY = 60;
// MOCK_LOAD 暂留：后端无催收员实时工作量 endpoint（下一轮）
const MOCK_LOAD: AgentLoad[] = [
  { name: "陈明远", current: 55, capacity: CAPACITY, status: "full" },
  { name: "李小红", current: 48, capacity: CAPACITY, status: "available" },
  { name: "张建华", current: 41, capacity: CAPACITY, status: "available" },
  { name: "刘晓娟", current: 32, capacity: CAPACITY, status: "available" },
  { name: "王芳芳", current: 39, capacity: CAPACITY, status: "available" },
];

function fmtRelative(iso: string | null): string {
  if (!iso) return "从未联系";
  const d = new Date(iso);
  const ms = Date.now() - d.getTime();
  const days = Math.floor(ms / (24 * 3600 * 1000));
  if (days === 0) return "今天";
  if (days === 1) return "1 天前";
  if (days < 30) return `${days} 天前`;
  return d.toISOString().slice(0, 10);
}

export function SupervisorCasesPage() {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [showAssign, setShowAssign] = useState(false);
  const [projectFilter, setProjectFilter] = useState<string>("全部项目");
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(1);
  // v1.8.0 — 列表行「记录跟进」快捷入口
  const [followUpCase, setFollowUpCase] = useState<{ id: number; ownerName: string } | null>(null);
  const debouncedKw = useDebouncedValue(keyword, 300);

  // v1.6.10 — 真实后端 GET /supervisor/cases，仅取公海未分配
  const filters: CrudFilter[] = [
    { field: "pool_type", operator: "eq", value: "public" },
  ];
  if (debouncedKw.trim()) {
    filters.push({ field: "keyword", operator: "contains", value: debouncedKw.trim() });
  }

  const { query } = useList<BackendCase>({
    resource: "supervisor/cases",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });
  const rawData = query.data?.data;
  const allItems: BackendCase[] =
    (rawData as unknown as PaginatedResponse<BackendCase>)?.items ??
    (rawData as BackendCase[] | undefined) ??
    [];
  const totalServer = query.data?.total ?? 0;

  // 项目名前端二次过滤（后端无 project filter param）
  const items =
    projectFilter === "全部项目"
      ? allItems
      : allItems.filter((c) => c.project_name === projectFilter);
  const total = projectFilter === "全部项目" ? totalServer : items.length;

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">案件分配</div>
          <div className="page-subtitle">从公海选取案件，分配给催收员</div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <SearchInput
            value={keyword}
            onChange={(v) => { setKeyword(v); setPage(1); }}
            placeholder="按业主姓名 / 房号搜索"
            width={200}
          />
          <select
            className="filter-select"
            value={projectFilter}
            onChange={(e) => { setProjectFilter(e.target.value); setPage(1); }}
          >
            {SUPERVISOR_PROJECT_FILTERS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="cases-grid">
        {/* 左：公海案件 */}
        <div className="ds-card">
          <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", borderBottom: "1px solid var(--color-neutral-100)", flexWrap: "wrap", gap: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 14, fontWeight: 600 }}>公海案件</span>
              <span style={{ fontSize: 12, color: "var(--color-neutral-500)" }}>
                共 {total} 条
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 12.5, color: "var(--color-neutral-600)" }}>
                已选 <strong>{selected.size}</strong> 条
              </span>
              <button
                type="button"
                className="ds-btn ds-btn-primary ds-btn-sm"
                disabled={selected.size === 0}
                onClick={() => setShowAssign(true)}
              >
                批量分配
              </button>
            </div>
          </div>
          {/* v1.6.5 — 移除卡内冗余搜索框（page-header 已统一搜索）*/}
          <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "10px 16px", borderBottom: "1px solid var(--color-neutral-100)", background: "#fafafa" }}>
            <span style={{ fontSize: 11, color: "var(--color-neutral-500)", display: "inline-flex", alignItems: "center", gap: 3 }} title="优先级分数：欠费月数 + 金额段 + 上次联系时长综合计算，0-100，越高越急需处理">
              <Info size={11} /> 右侧数字为优先级分数（0-100）
            </span>
          </div>
          <div>
            {query.isLoading ? (
              <div style={{ padding: 32, textAlign: "center", color: "var(--color-neutral-400)" }}>
                加载中…
              </div>
            ) : items.length === 0 ? (
              <div style={{ padding: 32, textAlign: "center", color: "var(--color-neutral-400)" }}>
                该项目暂无公海案件
              </div>
            ) : items.map((c) => {
              const tone = priorityTone(c.priority_score);
              const room =
                c.owner.building && c.owner.room
                  ? `${c.owner.building}${c.owner.room}`
                  : c.owner.building ?? c.owner.room ?? "—";
              const amount = c.amount_owed ? Number(c.amount_owed) : 0;
              return (
                <div key={c.id} className="case-row">
                  <input type="checkbox" checked={selected.has(c.id)} onChange={() => toggle(c.id)} style={{ width: 16, height: 16, cursor: "pointer", flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 600 }}>
                      {c.owner.name} / {room}
                      {c.project_name && (
                        <span className="ds-badge ds-badge-blue" style={{ fontSize: 10, marginLeft: 6 }}>
                          📁 {c.project_name}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--color-neutral-600)" }}>
                      欠费 {c.months_overdue ?? 0} 个月 ¥{amount.toLocaleString("zh-CN")} · 上次联系：{fmtRelative(c.last_contact_at)}
                    </div>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2, marginRight: 8 }} title={`优先级分数 ${c.priority_score}/100 · ${tone.label}`}>
                    <span className="priority-score" style={{ color: tone.color }}>P {c.priority_score}</span>
                    <span style={{ fontSize: 10, color: tone.color, fontWeight: 600 }}>{tone.label}</span>
                  </div>
                  <button
                    type="button"
                    className="ds-btn ds-btn-ghost ds-btn-sm"
                    onClick={(e) => { e.stopPropagation(); navigate(`/supervisor/cases/${c.id}`); }}
                    title="查看案件详情"
                    style={{ flexShrink: 0 }}
                  >
                    <Eye className="w-3 h-3" /> 详情
                  </button>
                  <button
                    type="button"
                    className="ds-btn ds-btn-ghost ds-btn-sm"
                    onClick={(e) => { e.stopPropagation(); setFollowUpCase({ id: c.id, ownerName: c.owner.name }); }}
                    title="无需进入详情页，直接写本次跟进备注"
                    style={{ flexShrink: 0 }}
                  >
                    <MessageSquarePlus className="w-3 h-3" /> 记录跟进
                  </button>
                </div>
              );
            })}
          </div>
          <PaginationBar
            page={page}
            pageSize={PAGE_SIZE}
            total={total}
            onPageChange={setPage}
          />
        </div>

        {/* 右：催收员工作量 */}
        <div className="ds-card">
          <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", borderBottom: "1px solid var(--color-neutral-100)" }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>催收员工作量</span>
            <span style={{ fontSize: 12, color: "var(--color-neutral-500)" }}>容量 = 私海上限 {CAPACITY}</span>
          </div>
          <div>
            {MOCK_LOAD.map((a) => {
              const pct = (a.current / a.capacity) * 100;
              const remain = a.capacity - a.current;
              return (
                <div key={a.name} className="workload-row">
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: 13.5 }}>{a.name}</div>
                    <div className="workload-bar"><div className="workload-fill" style={{ width: `${pct}%`, background: a.status === "full" ? "var(--color-warning)" : undefined }} /></div>
                  </div>
                  <div style={{ textAlign: "right", fontSize: 12.5, color: "var(--color-neutral-600)" }}>
                    {a.current}/{a.capacity}
                    <br />
                    {a.status === "full" ? (
                      <span style={{ color: "var(--color-warning)", fontSize: 12 }}>已满</span>
                    ) : (
                      <span style={{ color: "var(--color-success)", fontSize: 12 }}>可接 {remain}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {showAssign && (
        <AssignModal
          selectedCount={selected.size}
          loads={MOCK_LOAD}
          onClose={() => setShowAssign(false)}
          onConfirm={() => {
            alert(`已分配 ${selected.size} 条案件`);
            setSelected(new Set());
            setShowAssign(false);
          }}
        />
      )}

      {/* v1.8.0 — 列表行「记录跟进」Modal（supervisor 复用 admin/cases/{id}/stage 端点，v1.6.10 已扩权） */}
      {followUpCase && (
        <FollowUpNoteModal
          caseId={followUpCase.id}
          ownerName={followUpCase.ownerName}
          endpoint={`admin/cases/${followUpCase.id}/stage`}
          invalidateResource="supervisor/cases"
          onClose={() => setFollowUpCase(null)}
        />
      )}
    </div>
  );
}

function AssignModal({ selectedCount, loads, onClose, onConfirm }: { selectedCount: number; loads: AgentLoad[]; onClose: () => void; onConfirm: () => void }) {
  const [agent, setAgent] = useState("");
  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}
      onClick={onClose}
    >
      <div
        style={{ background: "white", borderRadius: 8, width: 460, maxWidth: "92%" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ padding: 16, borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontWeight: 600 }}>批量分配案件</span>
          <button type="button" onClick={onClose} style={{ border: "none", background: "transparent", fontSize: 20, cursor: "pointer" }}>×</button>
        </div>
        <div style={{ padding: 16 }}>
          <div style={{ marginBottom: 16, fontSize: 13.5, color: "var(--color-neutral-700)" }}>
            已选择 <strong>{selectedCount}</strong> 条案件，分配给：
          </div>
          <div className="form-group">
            <label className="form-label">选择催收员<span className="req">*</span></label>
            <select className="form-control" value={agent} onChange={(e) => setAgent(e.target.value)}>
              <option value="">请选择催收员</option>
              {loads.filter((l) => l.status !== "full").map((l) => (
                <option key={l.name} value={l.name}>{l.name}（可接 {l.capacity - l.current} 条）</option>
              ))}
            </select>
          </div>
          <div style={{ background: "var(--color-neutral-50)", borderRadius: 6, padding: 12, fontSize: 13, color: "var(--color-neutral-600)" }}>
            分配后案件将进入催收员私海，系统将自动推送任务通知。
          </div>
        </div>
        <div style={{ padding: 16, borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button type="button" className="ds-btn ds-btn-secondary" onClick={onClose}>取消</button>
          <button type="button" className="ds-btn ds-btn-primary" disabled={!agent} onClick={onConfirm}>确认分配</button>
        </div>
      </div>
    </div>
  );
}
