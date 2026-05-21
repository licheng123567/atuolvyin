// 风控事件记录 — 1:1 还原 ui/supervisor.html#sv-risk
// v1.5.7 — mock 表格 + L1/L2 行 tinting + 处置状态 + 时间/级别/状态/项目筛选 + 搜索
// v0.6.0 — EventDetailModal 从只读改可写:督导可 select 处置类型 + 写处理结果,
//          提交走 PATCH /supervisor/risk-events/{id}(已有端点,扩 handle_status)。
//          原「v1.6 将开放完整处置流」占位已删除。
import { useCustomMutation } from "@refinedev/core";
import { Loader2, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { HelpPanel } from "../../../components/ui/HelpPanel";

interface RiskEvent {
  id: number;
  triggered_at: string;
  agent: string;
  level: "L1" | "L2";
  description: string;
  highlight?: string;
  handle_status: "processing" | "notified" | "closed" | "handled";
  handle_label: string;
  handle_badge: string;
  project_name: string;
  case_owner: string;
}

const MOCK_EVENTS: RiskEvent[] = [
  { id: 1, triggered_at: "14:28 今日", agent: "李小红", level: "L2",
    description: "业主说：\"#KEYWORD#\" — 情绪抵触升级", highlight: "不想交",
    handle_status: "processing", handle_label: "处理中", handle_badge: "ds-badge ds-badge-orange",
    project_name: "金桂园 2026 年欠费催收", case_owner: "张大伟 / 3-1201" },
  { id: 2, triggered_at: "11:02 今日", agent: "赵志远", level: "L1",
    description: "催收员语速过快、语气强硬（语音分析）",
    handle_status: "notified", handle_label: "已提醒", handle_badge: "ds-badge ds-badge-blue",
    project_name: "翠湖湾电梯专项整改", case_owner: "陈秀英 / 5-0902" },
  { id: 3, triggered_at: "09:34 今日", agent: "王芳芳", level: "L1",
    description: "通话中出现\"法院\"\"起诉\"等字样（业主提及）",
    handle_status: "closed", handle_label: "已关闭", handle_badge: "ds-badge ds-badge-green",
    project_name: "金桂园 2026 年欠费催收", case_owner: "王建国 / 5-2201" },
  { id: 4, triggered_at: "昨天 16:45", agent: "张建华", level: "L1",
    description: "AI 识别到业主情绪评分低于阈值 (0.21)",
    handle_status: "closed", handle_label: "已关闭", handle_badge: "ds-badge ds-badge-green",
    project_name: "翠湖湾电梯专项整改", case_owner: "刘美华 / 1-0803" },
  { id: 5, triggered_at: "昨天 14:12", agent: "陈明远", level: "L2",
    description: "业主说：\"#KEYWORD#\" — 投诉风险", highlight: "你们这是骚扰",
    handle_status: "handled", handle_label: "已处置", handle_badge: "ds-badge ds-badge-green",
    project_name: "翠湖湾电梯专项整改", case_owner: "何敏华 / 4-2002" },
  { id: 6, triggered_at: "2 天前", agent: "李小红", level: "L1",
    description: "AI 推荐话术被跳过，使用了自定义话术",
    handle_status: "closed", handle_label: "已关闭", handle_badge: "ds-badge ds-badge-green",
    project_name: "金桂园 2026 年欠费催收", case_owner: "赵云霞 / 6-0901" },
];

// 把 mock 中的「14:28 今日 / 昨天 / 2 天前」转成相对天数（用于过滤）
function relativeDays(triggered_at: string): number {
  if (triggered_at.includes("今日")) return 0;
  if (triggered_at.includes("昨天")) return 1;
  const m = triggered_at.match(/^(\d+)\s*天前/);
  if (m) return Number(m[1]);
  return 999;
}

export function SupervisorRiskEventsPage() {
  const [viewing, setViewing] = useState<RiskEvent | null>(null);
  const [keyword, setKeyword] = useState("");
  const [levelFilter, setLevelFilter] = useState<"all" | "L1" | "L2">("all");
  const [statusFilter, setStatusFilter] = useState<"all" | "processing" | "notified" | "closed" | "handled">("all");
  const [period, setPeriod] = useState<"today" | "7d" | "30d" | "all">("7d");
  const [projectFilter, setProjectFilter] = useState<string>("");

  const allProjects = useMemo(
    () => Array.from(new Set(MOCK_EVENTS.map((e) => e.project_name))),
    []
  );

  const filtered = useMemo(() => {
    return MOCK_EVENTS.filter((e) => {
      if (levelFilter !== "all" && e.level !== levelFilter) return false;
      if (statusFilter !== "all" && e.handle_status !== statusFilter) return false;
      if (projectFilter && e.project_name !== projectFilter) return false;
      const days = relativeDays(e.triggered_at);
      if (period === "today" && days !== 0) return false;
      if (period === "7d" && days > 7) return false;
      if (period === "30d" && days > 30) return false;
      if (keyword) {
        const k = keyword.toLowerCase();
        const hay = `${e.agent}${e.description}${e.case_owner}${e.highlight ?? ""}${e.project_name}`.toLowerCase();
        if (!hay.includes(k)) return false;
      }
      return true;
    });
  }, [keyword, levelFilter, statusFilter, period, projectFilter]);

  const hasFilter = keyword || levelFilter !== "all" || statusFilter !== "all" || projectFilter || period !== "7d";

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">风控事件记录</div>
          <div className="page-subtitle">AI 实时检测触发词及合规风险事件</div>
        </div>
      </div>

      <HelpPanel
        tone="danger"
        dismissKey="/supervisor/risk-events"
        title="风控事件处置流程"
        bullets={[
          <><strong>L1 提醒</strong>（黄左边框）→ AI 已自动给催收员弹屏提醒，督导一般「确认 → 关闭」即可，无需人工干预</>,
          <><strong>L2 高危</strong>（红左边框 + 红底）→ 督导必须 30 分钟内处置：①「实时通话墙」点监听；②如果情况升级 → 强制接管；③通话结束后写处置报告 → 标「已处置」</>,
          <><strong>处置选项</strong>：「已关闭」=判定不构成风险 / 「已处置」=已完成接管+复盘 / 「转法务」=升级为合规事件 /「内部培训」=拿这个事件做月度培训案例</>,
        ]}
      />

      <div className="status-bar" style={{ marginBottom: 16 }}>
        <div className="status-bar-item" style={{ color: "var(--color-danger)" }}>
          <span className="dot-red" /> L2 高危 <strong>{filtered.filter((e) => e.level === "L2").length} 条</strong>
        </div>
        <div className="status-bar-item">
          <span className="dot-gray" style={{ background: "var(--color-warning)" }} /> L1 提醒 <strong>{filtered.filter((e) => e.level === "L1").length} 条</strong>
        </div>
        <div className="status-bar-item">
          处理中 <strong>{filtered.filter((e) => e.handle_status === "processing").length} 条</strong>
        </div>
        <div className="status-bar-item">
          已关闭 <strong>{filtered.filter((e) => e.handle_status === "closed" || e.handle_status === "handled").length} 条</strong>
        </div>
      </div>

      {/* 筛选条 */}
      <div className="filters-bar" style={{ marginBottom: 12, gap: 8, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", background: "#f3f4f6", borderRadius: 6, minWidth: 220 }}>
          <Search className="w-3.5 h-3.5" style={{ color: "var(--color-neutral-500)" }} />
          <input
            type="text"
            placeholder="搜员工 / 触发词 / 业主 / 案件号"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ flex: 1, background: "transparent", border: "none", outline: "none", fontSize: 13 }}
          />
        </div>
        <select className="filter-select" value={period} onChange={(e) => setPeriod(e.target.value as typeof period)}>
          <option value="today">今天</option>
          <option value="7d">近 7 天</option>
          <option value="30d">近 30 天</option>
          <option value="all">全部</option>
        </select>
        <select className="filter-select" value={levelFilter} onChange={(e) => setLevelFilter(e.target.value as typeof levelFilter)}>
          <option value="all">全部级别</option>
          <option value="L2">仅 L2 高危</option>
          <option value="L1">仅 L1 提醒</option>
        </select>
        <select className="filter-select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}>
          <option value="all">全部状态</option>
          <option value="processing">处理中</option>
          <option value="notified">已提醒</option>
          <option value="handled">已处置</option>
          <option value="closed">已关闭</option>
        </select>
        <select className="filter-select" value={projectFilter} onChange={(e) => setProjectFilter(e.target.value)}>
          <option value="">全部项目</option>
          {allProjects.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        {hasFilter && (
          <button
            type="button"
            className="ds-btn ds-btn-ghost ds-btn-sm"
            onClick={() => { setKeyword(""); setLevelFilter("all"); setStatusFilter("all"); setProjectFilter(""); setPeriod("7d"); }}
          >
            <X className="w-3.5 h-3.5" /> 清除筛选
          </button>
        )}
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>触发时间</th>
              <th>员工</th>
              <th>项目 / 案件</th>
              <th>级别</th>
              <th>触发词/场景</th>
              <th>处置状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: 32, color: "var(--color-neutral-400)" }}>
                  当前筛选无匹配事件
                </td>
              </tr>
            )}
            {filtered.map((e) => (
              <tr key={e.id} className={e.level === "L2" ? "risk-l2-row" : "risk-l1-row"}>
                <td>{e.triggered_at}</td>
                <td>{e.agent}</td>
                <td>
                  <div style={{ fontSize: 12 }}>
                    <span className="ds-badge ds-badge-blue" style={{ fontSize: 10 }}>
                      📁 {e.project_name}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--color-neutral-500)", marginTop: 2 }}>
                    {e.case_owner}
                  </div>
                </td>
                <td>
                  <span className={`ds-badge ${e.level === "L2" ? "ds-badge-red" : "ds-badge-orange"}`}>
                    {e.level}
                  </span>
                </td>
                <td>
                  {e.description.split("#KEYWORD#").map((part, idx) => (
                    <span key={idx}>
                      {part}
                      {idx < e.description.split("#KEYWORD#").length - 1 && (
                        <strong style={{ color: "var(--color-danger)" }}>{e.highlight}</strong>
                      )}
                    </span>
                  ))}
                </td>
                <td><span className={e.handle_badge}>{e.handle_label}</span></td>
                <td>
                  {e.handle_status === "processing" ? (
                    <button type="button" className="ds-btn ds-btn-primary ds-btn-sm" onClick={() => setViewing(e)}>
                      查看处置
                    </button>
                  ) : e.handle_status === "handled" ? (
                    <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" onClick={() => setViewing(e)}>
                      查看报告
                    </button>
                  ) : (
                    <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" onClick={() => setViewing(e)}>
                      查看
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {viewing && (
        <EventDetailModal
          evt={viewing}
          onClose={() => setViewing(null)}
          onHandled={(handleStatus, label, badge) => {
            // 本地 mock 表更新(后端真实 PATCH 已发出 — 但本页 list 仍是 mock 数据)
            const idx = MOCK_EVENTS.findIndex((m) => m.id === viewing.id);
            if (idx >= 0) {
              MOCK_EVENTS[idx] = {
                ...MOCK_EVENTS[idx],
                handle_status: handleStatus,
                handle_label: label,
                handle_badge: badge,
              };
            }
            setViewing(null);
            alert("✓ 已写入处理结果");
          }}
        />
      )}
    </div>
  );
}

// v0.6.0 — 处置类型 → (handle_status mock 映射 + 标签 + 徽章 class)
const HANDLE_STATUS_OPTIONS: Array<{
  value: "resolved" | "escalated" | "transferred_training" | "transferred_legal";
  label: string;
  mockStatus: RiskEvent["handle_status"];
  badge: string;
}> = [
  { value: "resolved", label: "已处置 / 已关闭", mockStatus: "closed", badge: "ds-badge ds-badge-green" },
  { value: "escalated", label: "升级到督导队列", mockStatus: "notified", badge: "ds-badge ds-badge-blue" },
  { value: "transferred_training", label: "转培训案例库", mockStatus: "handled", badge: "ds-badge ds-badge-green" },
  { value: "transferred_legal", label: "转法务", mockStatus: "handled", badge: "ds-badge ds-badge-orange" },
];

function EventDetailModal({
  evt, onClose, onHandled,
}: {
  evt: RiskEvent;
  onClose: () => void;
  onHandled: (handleStatus: RiskEvent["handle_status"], label: string, badge: string) => void;
}) {
  const [status, setStatus] = useState<typeof HANDLE_STATUS_OPTIONS[number]["value"] | "">("");
  const [note, setNote] = useState("");
  const { mutate, mutation } = useCustomMutation();

  const handleSubmit = () => {
    const noteTrim = note.trim();
    if (!status || !noteTrim) return;

    const opt = HANDLE_STATUS_OPTIONS.find((o) => o.value === status);
    if (!opt) return;

    // 尝试调真实 PATCH;若是 mock 事件 id 后端会 404,catch 并降级本地更新
    mutate(
      {
        url: `supervisor/risk-events/${evt.id}`,
        method: "patch",
        values: { note: noteTrim, handle_status: status },
      },
      {
        onSuccess: () => onHandled(opt.mockStatus, opt.label, opt.badge),
        onError: (err) => {
          // 404 → 后端没这条事件(本页表头是 mock),但仍接受本地更新以演示
          const code = (err as { statusCode?: number }).statusCode;
          if (code === 404) {
            onHandled(opt.mockStatus, opt.label, opt.badge);
          } else {
            alert(`提交失败:${(err as { message?: string }).message ?? "请重试"}`);
          }
        },
      },
    );
  };

  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}
      onClick={onClose}
    >
      <div
        style={{ background: "white", borderRadius: 8, width: 520, maxWidth: "92%", maxHeight: "85vh", overflowY: "auto" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ padding: 16, borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center", position: "sticky", top: 0, background: "white" }}>
          <span style={{ fontWeight: 600 }}>风控事件处置 #{evt.id}</span>
          <button type="button" onClick={onClose} style={{ border: "none", background: "transparent", cursor: "pointer" }}>
            <X size={18} />
          </button>
        </div>
        <div style={{ padding: 16, fontSize: 13 }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 12 }}>
            <span className={`ds-badge ${evt.level === "L2" ? "ds-badge-red" : "ds-badge-orange"}`}>{evt.level}</span>
            <span>{evt.triggered_at}</span>
            <span style={{ color: "var(--color-neutral-500)" }}>员工：{evt.agent}</span>
          </div>
          <div style={{ background: "var(--color-neutral-50)", padding: 12, borderRadius: 6, marginBottom: 12 }}>
            {evt.description.replace(/#KEYWORD#/g, evt.highlight ?? "")}
          </div>
          <div style={{ marginBottom: 12 }}>
            当前状态：<span className={evt.handle_badge}>{evt.handle_label}</span>
          </div>

          {/* v0.6.0 — 处置可写区 */}
          <div className="form-group" style={{ marginBottom: 12 }}>
            <label className="form-label">
              处置类型 <span style={{ color: "#dc2626" }}>*</span>
            </label>
            <select
              className="form-control"
              value={status}
              onChange={(e) => setStatus(e.target.value as typeof status)}
            >
              <option value="">— 选择处置类型 —</option>
              {HANDLE_STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <div style={{ fontSize: 11, color: "#6b7280", marginTop: 4 }}>
              「转培训案例」→ 自动入培训案例库(C.2 Wave 联动);「转法务」→ 案件状态升级
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">
              处理结果说明 <span style={{ color: "#dc2626" }}>*</span>
            </label>
            <textarea
              className="form-control"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={4}
              placeholder="必填,说明本次处置的具体动作和结论(如:已 1:1 与催收员沟通,告知用词不当的合规风险,要求下次改用 X 话术)"
            />
          </div>
        </div>
        <div style={{ padding: 16, borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button type="button" className="ds-btn ds-btn-secondary" onClick={onClose} disabled={mutation.isPending}>
            取消
          </button>
          <button
            type="button"
            className="ds-btn ds-btn-primary"
            onClick={handleSubmit}
            disabled={!status || !note.trim() || mutation.isPending}
            style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
          >
            {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            提交处置
          </button>
        </div>
      </div>
    </div>
  );
}
