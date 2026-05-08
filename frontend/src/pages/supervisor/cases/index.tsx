// 案件分配 — 1:1 还原 ui/supervisor.html#sv-cases
// v1.5.7 — 左：公海案件 checkbox 列表 / 右：催收员工作量 bar
import { Eye, Info, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SUPERVISOR_PROJECT_FILTERS } from "../_shared/projectFilters";

// 优先级分数算法（mock）：欠费月数 ×6 + 金额段 ×3 + 上次联系久 ×0.4，上限 100
function priorityTone(score: number): { color: string; label: string } {
  if (score >= 90) return { color: "var(--color-danger)", label: "紧急" };
  if (score >= 75) return { color: "var(--color-warning)", label: "高" };
  if (score >= 60) return { color: "#f59e0b", label: "中" };
  return { color: "var(--color-neutral-500)", label: "低" };
}

interface PoolCase {
  id: number;
  name: string;
  building: string;
  months: number;
  amount: number;
  last_contact: string;
  priority: number;
  project_name: string;
}

interface AgentLoad {
  name: string;
  current: number;
  capacity: number;
  status: "full" | "available";
}

const MOCK_POOL: PoolCase[] = [
  { id: 301, name: "梁建国", building: "7-2301", months: 4, amount: 6840, last_contact: "3 天前", priority: 97, project_name: "金桂园 2026 年欠费催收" },
  { id: 302, name: "吴雪梅", building: "2-1105", months: 3, amount: 4920, last_contact: "5 天前", priority: 91, project_name: "金桂园 2026 年欠费催收" },
  { id: 303, name: "徐明华", building: "1-0402", months: 6, amount: 9360, last_contact: "7 天前", priority: 88, project_name: "翠湖湾电梯专项整改" },
  { id: 304, name: "郑丽娟", building: "4-1801", months: 2, amount: 3280, last_contact: "2 天前", priority: 82, project_name: "翠湖湾电梯专项整改" },
  { id: 305, name: "黄志强", building: "6-0306", months: 5, amount: 8200, last_contact: "10 天前", priority: 78, project_name: "金桂园 2026 年欠费催收" },
  { id: 306, name: "曹秀英", building: "3-0902", months: 2, amount: 2640, last_contact: "1 天前", priority: 71, project_name: "翠湖湾电梯专项整改" },
];

const CAPACITY = 60;
const MOCK_LOAD: AgentLoad[] = [
  { name: "陈明远", current: 55, capacity: CAPACITY, status: "full" },
  { name: "李小红", current: 48, capacity: CAPACITY, status: "available" },
  { name: "张建华", current: 41, capacity: CAPACITY, status: "available" },
  { name: "刘晓娟", current: 32, capacity: CAPACITY, status: "available" },
  { name: "王芳芳", current: 39, capacity: CAPACITY, status: "available" },
];

export function SupervisorCasesPage() {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [showAssign, setShowAssign] = useState(false);
  const [projectFilter, setProjectFilter] = useState<string>("全部项目");
  const [keyword, setKeyword] = useState("");

  const visiblePool = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    return MOCK_POOL.filter((c) => {
      if (projectFilter !== "全部项目" && c.project_name !== projectFilter) return false;
      if (kw && !`${c.name} ${c.building}`.toLowerCase().includes(kw)) return false;
      return true;
    });
  }, [projectFilter, keyword]);

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

      <div className="cases-grid">
        {/* 左：公海案件 */}
        <div className="ds-card">
          <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", borderBottom: "1px solid var(--color-neutral-100)", flexWrap: "wrap", gap: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 14, fontWeight: 600 }}>公海案件</span>
              <span style={{ fontSize: 12, color: "var(--color-neutral-500)" }}>
                共 {visiblePool.length} 条
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
          {/* 卡内搜索框 — 比 page-header 上的更近，方便表格内快速定位 */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "10px 16px", borderBottom: "1px solid var(--color-neutral-100)", background: "#fafafa" }}>
            <Search size={14} style={{ color: "var(--color-neutral-400)" }} />
            <input
              type="text"
              placeholder="按业主姓名 / 房号在公海中搜索"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              style={{ flex: 1, border: "none", outline: "none", background: "transparent", fontSize: 13, color: "#374151" }}
            />
            <span style={{ fontSize: 11, color: "var(--color-neutral-500)", display: "inline-flex", alignItems: "center", gap: 3 }} title="优先级分数：欠费月数 + 金额段 + 上次联系时长综合计算，0-100，越高越急需处理">
              <Info size={11} /> 右侧数字为优先级分数（0-100）
            </span>
          </div>
          <div>
            {visiblePool.length === 0 ? (
              <div style={{ padding: 32, textAlign: "center", color: "var(--color-neutral-400)" }}>
                该项目暂无公海案件
              </div>
            ) : visiblePool.map((c) => {
              const tone = priorityTone(c.priority);
              return (
                <div key={c.id} className="case-row">
                  <input type="checkbox" checked={selected.has(c.id)} onChange={() => toggle(c.id)} style={{ width: 16, height: 16, cursor: "pointer", flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 600 }}>
                      {c.name} / {c.building}
                      <span className="ds-badge ds-badge-blue" style={{ fontSize: 10, marginLeft: 6 }}>
                        📁 {c.project_name}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: "var(--color-neutral-600)" }}>
                      欠费 {c.months} 个月 ¥{c.amount.toLocaleString("zh-CN")} · 上次联系：{c.last_contact}
                    </div>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2, marginRight: 8 }} title={`优先级分数 ${c.priority}/100 · ${tone.label}`}>
                    <span className="priority-score" style={{ color: tone.color }}>P {c.priority}</span>
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
                </div>
              );
            })}
          </div>
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
