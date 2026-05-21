// 承诺催付清单 — v1.5.7 ⭐⭐⭐
// 业主在通话中承诺缴费 → AI 自动入清单 → 到期前 1 天提醒催收员回访
// v1.6.5 — 加分页 + debounce 搜索
// v0.6.0 — 催回访按钮实装(原 alert mock)→ 改用 SupervisorCaseActionModal,
//          调通用 POST /supervisor/cases/{id}/urge 接口(与案件详情催办共用);
//          删除「升级督导」按钮(语义错误 — 督导自己升级自己不通)
import { CalendarClock, CheckCircle2, Clock, Eye, Phone } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SupervisorCaseActionModal } from "../../../components/supervisor/SupervisorCaseActionModal";
import { HelpPanel } from "../../../components/ui/HelpPanel";
import { PaginationBar } from "../../../components/ui/PaginationBar";
import { SearchInput } from "../../../components/ui/SearchInput";
import { useDebouncedValue } from "../../../hooks/useDebouncedValue";
import { SUPERVISOR_PROJECT_FILTERS } from "../_shared/projectFilters";

const PAGE_SIZE = 15;

interface Promise {
  id: number;
  owner: string;
  building: string;
  amount: number;
  promised_at: string;       // 业主承诺日（通话当天）
  due_date: string;          // 业主承诺缴费截止日
  agent: string;
  status: "pending" | "due_today" | "overdue" | "paid" | "broken";
  status_label: string;
  status_badge: string;
  project_name: string;
  agent_phone: string;
}

const MOCK_PROMISES: Promise[] = [
  { id: 1, owner: "张大伟", building: "3-1201", amount: 3680, promised_at: "2026-05-05", due_date: "2026-05-08",
    agent: "李小红", agent_phone: "139****0005", status: "due_today", status_label: "今天到期", status_badge: "ds-badge ds-badge-orange",
    project_name: "金桂园 2026 年欠费催收" },
  { id: 2, owner: "王秀英", building: "8-0902", amount: 1240, promised_at: "2026-05-04", due_date: "2026-05-09",
    agent: "王芳芳", agent_phone: "139****0006", status: "pending", status_label: "明天到期", status_badge: "ds-badge ds-badge-blue",
    project_name: "金桂园 2026 年欠费催收" },
  { id: 3, owner: "刘建国", building: "1-0301", amount: 8400, promised_at: "2026-05-01", due_date: "2026-05-06",
    agent: "张建华", agent_phone: "139****0007", status: "overdue", status_label: "超期 2 天", status_badge: "ds-badge ds-badge-red",
    project_name: "翠湖湾电梯专项整改" },
  { id: 4, owner: "陈秀英", building: "5-0902", amount: 920, promised_at: "2026-04-28", due_date: "2026-05-02",
    agent: "陈明远", agent_phone: "139****0008", status: "paid", status_label: "✓ 已缴清", status_badge: "ds-badge ds-badge-green",
    project_name: "翠湖湾电梯专项整改" },
  { id: 5, owner: "孙志远", building: "4-1504", amount: 2100, promised_at: "2026-04-26", due_date: "2026-04-30",
    agent: "刘晓娟", agent_phone: "139****0009", status: "broken", status_label: "✗ 失约", status_badge: "ds-badge ds-badge-gray",
    project_name: "金桂园 2026 年欠费催收" },
  { id: 6, owner: "赵云霞", building: "6-0901", amount: 5200, promised_at: "2026-05-06", due_date: "2026-05-12",
    agent: "李小红", agent_phone: "139****0005", status: "pending", status_label: "5 天后到期", status_badge: "ds-badge ds-badge-blue",
    project_name: "金桂园 2026 年欠费催收" },
];

type StatusFilter = "all" | "pending" | "overdue" | "paid";
type DueRange = "all" | "this_week" | "next_week" | "overdue";

function dayDiff(from: string, to: string): number {
  const a = new Date(from + "T00:00:00").getTime();
  const b = new Date(to + "T00:00:00").getTime();
  return Math.round((b - a) / 86400000);
}

export function SupervisorPromisesPage() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [dueRange, setDueRange] = useState<DueRange>("all");
  const [projectFilter, setProjectFilter] = useState<string>("全部项目");
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(1);
  const [urgeCaseId, setUrgeCaseId] = useState<number | null>(null);  // v0.6.0
  const debouncedKw = useDebouncedValue(keyword, 300);

  const today = new Date().toISOString().slice(0, 10);

  const filtered = useMemo(() => {
    const kw = debouncedKw.trim().toLowerCase();
    return MOCK_PROMISES.filter((p) => {
      // 状态 filter
      if (filter === "pending" && !(p.status === "pending" || p.status === "due_today")) return false;
      if (filter === "overdue" && !(p.status === "overdue" || p.status === "broken")) return false;
      if (filter === "paid" && p.status !== "paid") return false;
      // 项目 filter
      if (projectFilter !== "全部项目" && p.project_name !== projectFilter) return false;
      // 搜索
      if (kw && !`${p.owner} ${p.building}`.toLowerCase().includes(kw)) return false;
      // 时间段（基于 due_date）
      if (dueRange !== "all") {
        const diff = dayDiff(today, p.due_date);
        if (dueRange === "this_week" && !(diff >= 0 && diff <= 6)) return false;
        if (dueRange === "next_week" && !(diff >= 7 && diff <= 13)) return false;
        if (dueRange === "overdue" && !(diff < 0 && p.status !== "paid")) return false;
      }
      return true;
    });
  }, [filter, projectFilter, debouncedKw, dueRange, today]);

  const total = filtered.length;
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const counts = {
    pending: MOCK_PROMISES.filter((p) => p.status === "pending" || p.status === "due_today").length,
    overdue: MOCK_PROMISES.filter((p) => p.status === "overdue" || p.status === "broken").length,
    paid: MOCK_PROMISES.filter((p) => p.status === "paid").length,
    total_amount: MOCK_PROMISES.filter((p) => p.status !== "broken" && p.status !== "paid").reduce((s, p) => s + p.amount, 0),
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">承诺催付清单</div>
          <div className="page-subtitle">业主承诺缴费的案件 → 到期前自动提醒回访，承诺兑现率是核心指标</div>
        </div>
      </div>

      <HelpPanel
        tone="warn"
        dismissKey="/supervisor/promises"
        title="承诺催付怎么用"
        bullets={[
          <><strong>自动入清单</strong>：AI 在通话中识别到业主说「下周一打」「这个月底交」等承诺关键词后，自动写入此清单 + 设置截止日</>,
          <><strong>到期前 1 天提醒</strong>：系统自动给原催收员推送任务（App 通知 + PC 红点），提示「明日到期，请回访 / 确认 / 收款」</>,
          <><strong>到期当天</strong>：标橙色「今天到期」，催收员未回访则自动升级到督导</>,
          <><strong>超期处理</strong>：超过截止日仍未到账 → 自动标红「失约」→ 计入业主信用历史，下次催收策略调整</>,
          <><strong>核心指标</strong>：承诺兑现率（已缴清 / 总承诺）。&gt; 60% 表示话术质量好，&lt; 40% 说明业主在敷衍，需要话术升级</>,
        ]}
      />

      <div className="status-bar">
        <div className="status-bar-item" style={{ color: "var(--color-warning)" }}>
          <Clock className="w-4 h-4" /> 待回访 <strong>{counts.pending} 单</strong>
        </div>
        <div className="status-bar-item" style={{ color: "var(--color-danger)" }}>
          <CalendarClock className="w-4 h-4" /> 已超期 <strong>{counts.overdue} 单</strong>
        </div>
        <div className="status-bar-item" style={{ color: "var(--color-success)" }}>
          <CheckCircle2 className="w-4 h-4" /> 已缴清 <strong>{counts.paid} 单</strong>
        </div>
        <div className="status-bar-item">
          待回款金额 <strong>¥{counts.total_amount.toLocaleString("zh-CN")}</strong>
        </div>
      </div>

      {/* 顶部三维过滤：项目 + 搜索 + 时间段 */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10, flexWrap: "wrap" }}>
        <SearchInput
          value={keyword}
          onChange={(v) => { setKeyword(v); setPage(1); }}
          placeholder="按业主姓名 / 房号搜索"
          width={200}
        />
        <select className="filter-select" value={projectFilter} onChange={(e) => { setProjectFilter(e.target.value); setPage(1); }}>
          {SUPERVISOR_PROJECT_FILTERS.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select className="filter-select" value={dueRange} onChange={(e) => { setDueRange(e.target.value as DueRange); setPage(1); }}>
          <option value="all">全部到期日</option>
          <option value="this_week">本周到期</option>
          <option value="next_week">下周到期</option>
          <option value="overdue">已超期</option>
        </select>
        {(keyword || projectFilter !== "全部项目" || dueRange !== "all" || filter !== "all") && (
          <button type="button" className="ds-btn ds-btn-ghost ds-btn-sm" onClick={() => { setKeyword(""); setProjectFilter("全部项目"); setDueRange("all"); setFilter("all"); setPage(1); }}>
            清空筛选
          </button>
        )}
      </div>

      <div className="filters-bar" style={{ marginBottom: 12 }}>
        {[
          { v: "all" as const, label: "全部" },
          { v: "pending" as const, label: "待回访" },
          { v: "overdue" as const, label: "已超期" },
          { v: "paid" as const, label: "已缴清" },
        ].map((f) => (
          <button
            key={f.v}
            type="button"
            className={`ds-btn ${filter === f.v ? "ds-btn-primary" : "ds-btn-secondary"} ds-btn-sm`}
            onClick={() => { setFilter(f.v); setPage(1); }}
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
              <th>承诺日</th>
              <th>截止日</th>
              <th>催收员</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 && (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: 32, color: "var(--color-neutral-400)" }}>
                  暂无符合条件的承诺
                </td>
              </tr>
            )}
            {visible.map((p) => (
              <tr key={p.id} style={p.status === "overdue" ? { background: "#fef2f2" } : p.status === "due_today" ? { background: "#fffbeb" } : {}}>
                <td><strong>{p.owner}</strong> / {p.building}</td>
                <td style={{ fontSize: 12, color: "var(--color-primary)" }}>📁 {p.project_name}</td>
                <td>¥{p.amount.toLocaleString("zh-CN")}</td>
                <td style={{ fontSize: 12, color: "var(--color-neutral-500)" }}>{p.promised_at}</td>
                <td><strong>{p.due_date}</strong></td>
                <td>{p.agent}<div style={{ fontSize: 11, color: "var(--color-neutral-500)" }}>{p.agent_phone}</div></td>
                <td><span className={p.status_badge}>{p.status_label}</span></td>
                <td>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {/* v0.6.0 — 催回访 / 超期 case 的「催办」合并为同一入口,
                        都打开 SupervisorCaseActionModal type=urge */}
                    {p.status !== "paid" && (
                      <button
                        type="button"
                        className="ds-btn ds-btn-primary ds-btn-sm"
                        onClick={() => setUrgeCaseId(p.id)}
                      >
                        <Phone className="w-3 h-3" /> 催办
                      </button>
                    )}
                    <button type="button" className="ds-btn ds-btn-ghost ds-btn-sm" onClick={() => navigate(`/supervisor/cases/${p.id}`)}>
                      <Eye className="w-3 h-3" /> 详情
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <PaginationBar
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          onPageChange={setPage}
        />
      </div>

      {/* v0.6.0 — 催办 modal(复用案件详情同款) */}
      {urgeCaseId !== null && (
        <SupervisorCaseActionModal
          caseId={urgeCaseId}
          type="urge"
          onClose={() => setUrgeCaseId(null)}
          onDone={() => {
            setUrgeCaseId(null);
            alert("✓ 已写入案件时间线并通知催收员");
          }}
        />
      )}
    </div>
  );
}
