// 培训案例库 — v0.6.0 接通真实后端
// 数据源 GET /supervisor/training-cases(后端 0 条时 fallback mock 展示 4 个示例)
// 「手动入库」按钮 POST /supervisor/training-cases
// 「转培训」按钮在风险事件 modal 已联动:督导处置 status=transferred_training
// → 后端 supervisor_extras PATCH 调 from_risk_event() 自动 insert TrainingCase
import { useCustom, useCustomMutation } from "@refinedev/core";
import { BookMarked, Filter, Headphones, Loader2, Plus, Sparkles, Star, X } from "lucide-react";
import { useState } from "react";
import { HelpPanel } from "../../../components/ui/HelpPanel";

interface TrainingCase {
  id: number;
  title: string;
  category: "investigate" | "negotiate" | "escalate" | "objection";
  scenario: string;
  lesson: string;
  raw_call_id: number | null;
  raw_risk_event_id: number | null;
  source: "auto" | "manual";
  created_by_name: string | null;
  created_at: string;
  rating: number;
  views: number;
}

interface ListResp {
  items: TrainingCase[];
  total: number;
}

const CATEGORY_META: Record<
  TrainingCase["category"],
  { label: string; badge: string }
> = {
  negotiate: { label: "协商成功", badge: "ds-badge ds-badge-green" },
  escalate: { label: "升级处置", badge: "ds-badge ds-badge-red" },
  objection: { label: "异议处理", badge: "ds-badge ds-badge-orange" },
  investigate: { label: "调查定位", badge: "ds-badge ds-badge-blue" },
};

const CATEGORIES = [
  { v: "all", label: "全部" },
  { v: "negotiate", label: "协商成功" },
  { v: "escalate", label: "升级处置" },
  { v: "objection", label: "异议处理" },
  { v: "investigate", label: "调查定位" },
] as const;

// fallback mock — 后端 0 条时显示
const MOCK_CASES: TrainingCase[] = [
  {
    id: -1, title: "经济困难型业主:3 个月分期方案达成承诺",
    category: "negotiate",
    scenario: "业主刚经历失业,明确表示无力一次性缴清。催收员李小红用「分期方案 + 不影响信用」组合话术,业主承诺次月起每月 ¥820 分 3 期。",
    lesson: "① 先共情再谈数字;② 给业主退路(分期/缓交);③ 用「不影响您信用」作为 closing trigger",
    raw_call_id: 1024, raw_risk_event_id: null, source: "manual",
    created_by_name: "督导小李(示例)", created_at: "2026-05-03T10:00:00Z",
    rating: 5, views: 23,
  },
  {
    id: -2, title: "L2 风控:业主投诉骚扰的紧急止损",
    category: "escalate",
    scenario: "业主第 6 通拒接后接通即喊「你们这是骚扰」,AI 触发 L2,督导 30 秒内强制接管,向业主道歉并承诺 30 天不再致电,案件转法务。",
    lesson: "① L2 接管的窗口很短(<1 分钟);② 道歉 + 暂停拨打 + 律师函;③ 录音留作合规证据",
    raw_call_id: 1108, raw_risk_event_id: null, source: "auto",
    created_by_name: "系统自动入库", created_at: "2026-05-05T14:00:00Z",
    rating: 5, views: 41,
  },
];

export function SupervisorTrainingPage() {
  const [filter, setFilter] = useState<(typeof CATEGORIES)[number]["v"]>("all");
  const [sourceFilter, setSourceFilter] = useState<"all" | "auto" | "manual">("all");
  const [createOpen, setCreateOpen] = useState(false);

  const { query } = useCustom<ListResp>({
    url: "supervisor/training-cases",
    method: "get",
    config: {
      query: {
        ...(filter !== "all" ? { category: filter } : {}),
        ...(sourceFilter !== "all" ? { source: sourceFilter } : {}),
        page: 1,
        page_size: 60,
      },
    },
    queryOptions: { retry: false },
  });

  const resp = query.data?.data;
  const items: TrainingCase[] = resp && resp.items.length > 0 ? resp.items
    : (resp ? [] : MOCK_CASES);
  const usingMock = !resp;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">培训案例库</div>
          <div className="page-subtitle">L2 处置 / 优秀通话沉淀为案例,新人入职 + 月度复盘必学</div>
        </div>
        <button
          type="button"
          className="ds-btn ds-btn-primary"
          onClick={() => setCreateOpen(true)}
        >
          <Plus className="w-3.5 h-3.5" /> 手动入库
        </button>
      </div>

      <HelpPanel
        tone="tip"
        dismissKey="/supervisor/training-v060"
        title="入库的两条路径"
        bullets={[
          <><strong>自动入库</strong>:督导在「风险事件」页处置时选「转培训案例」,后端自动建训练案;<Sparkles className="w-3 h-3 inline" /> 标签</>,
          <><strong>手动入库</strong>:督导抓到一通优秀对话(对照录音),点上方「手动入库」录入</>,
        ]}
        footer="入库后用于:① 新人入职 7 天 5 星案例必学;② 督导每月初挑 3 个案例做团队复盘会"
      />

      <div className="filters-bar" style={{ marginBottom: 16, gap: 12, display: "flex", flexWrap: "wrap" }}>
        <Filter className="w-4 h-4" style={{ color: "var(--color-neutral-500)" }} />
        {CATEGORIES.map((c) => (
          <button
            key={c.v}
            type="button"
            className={`ds-btn ${filter === c.v ? "ds-btn-primary" : "ds-btn-secondary"} ds-btn-sm`}
            onClick={() => setFilter(c.v)}
          >
            {c.label}
          </button>
        ))}
        <span style={{ width: 1, background: "var(--color-neutral-200)", margin: "0 4px" }} />
        {(["all", "auto", "manual"] as const).map((s) => (
          <button
            key={s}
            type="button"
            className={`ds-btn ${sourceFilter === s ? "ds-btn-primary" : "ds-btn-ghost"} ds-btn-sm`}
            onClick={() => setSourceFilter(s)}
          >
            {s === "all" ? "全部来源" : s === "auto" ? "自动入库" : "手动入库"}
          </button>
        ))}
      </div>

      {usingMock && (
        <div
          style={{
            padding: "8px 12px", background: "#fef3c7", border: "1px solid #fde68a",
            borderRadius: 6, fontSize: 12, color: "#78350f", marginBottom: 8,
          }}
        >
          ⓘ 后端暂无培训案例数据,以下为 mock 演示。点「手动入库」录第一条真实案例。
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 16 }}>
        {items.map((c) => (
          <CaseCard key={c.id} c={c} />
        ))}
      </div>

      {createOpen && (
        <CreateCaseModal
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            setCreateOpen(false);
            void query.refetch();
          }}
        />
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// 案例卡片
// ──────────────────────────────────────────────────────────────
function CaseCard({ c }: { c: TrainingCase }) {
  const meta = CATEGORY_META[c.category];
  const { mutate: viewMutate } = useCustomMutation();

  const handleListen = () => {
    if (c.id > 0) {
      // 实际案例 — 调 view counter;录音播放暂走 alert 占位
      viewMutate({
        url: `supervisor/training-cases/${c.id}/view`,
        method: "post",
        values: {},
      });
    }
    if (c.raw_call_id) {
      alert(`即将播放通话 #${c.raw_call_id} 录音 — 录音播放器待集成`);
    } else {
      alert("本案例无原始通话,仅作书面复盘材料");
    }
  };

  return (
    <div
      className="ds-card"
      style={{ cursor: "default", transition: "box-shadow 0.15s" }}
      onMouseEnter={(e) => (e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.08)")}
      onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "")}
    >
      <div className="card-body" style={{ padding: 16 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 8 }}>
          <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            <span className={meta.badge} style={{ fontSize: 11 }}>{meta.label}</span>
            {c.source === "auto" && (
              <span className="ds-badge ds-badge-blue" style={{ fontSize: 10 }}>
                <Sparkles className="w-2.5 h-2.5 inline" style={{ marginRight: 2 }} />
                自动入库
              </span>
            )}
          </div>
          <div style={{ display: "flex", gap: 1 }}>
            {[1, 2, 3, 4, 5].map((s) => (
              <Star
                key={s}
                className="w-3 h-3"
                style={{
                  color: s <= c.rating ? "#f59e0b" : "var(--color-neutral-300)",
                  fill: s <= c.rating ? "#f59e0b" : "transparent",
                }}
              />
            ))}
          </div>
        </div>

        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, lineHeight: 1.4 }}>
          <BookMarked
            className="w-3.5 h-3.5"
            style={{ display: "inline", marginRight: 4, color: "var(--color-primary)" }}
          />
          {c.title}
        </div>

        <div style={{ fontSize: 12, color: "var(--color-neutral-700)", lineHeight: 1.6, marginBottom: 8 }}>
          <strong>场景:</strong>
          <div style={{ whiteSpace: "pre-wrap" }}>{c.scenario}</div>
        </div>

        <div
          style={{
            fontSize: 12, color: "var(--color-neutral-700)", lineHeight: 1.6,
            marginBottom: 12, padding: 8, background: "#f9fafb", borderRadius: 4,
            whiteSpace: "pre-wrap",
          }}
        >
          <strong style={{ color: "var(--color-success)" }}>📌 复盘要点:</strong><br />
          {c.lesson}
        </div>

        <div
          style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            fontSize: 11, color: "var(--color-neutral-500)",
          }}
        >
          <span>
            {c.created_by_name ?? "—"} · {new Date(c.created_at).toLocaleDateString("zh-CN")}
          </span>
          <span>{c.views} 人学过</span>
        </div>

        <div style={{ marginTop: 8 }}>
          <button
            type="button"
            className="ds-btn ds-btn-secondary ds-btn-sm"
            style={{ width: "100%" }}
            onClick={handleListen}
          >
            <Headphones className="w-3 h-3" /> 听原通话录音
            {c.raw_call_id ? ` (#${c.raw_call_id})` : ""}
          </button>
        </div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// 手动入库 modal
// ──────────────────────────────────────────────────────────────
function CreateCaseModal({
  onClose, onCreated,
}: { onClose: () => void; onCreated: () => void }) {
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState<TrainingCase["category"]>("negotiate");
  const [scenario, setScenario] = useState("");
  const [lesson, setLesson] = useState("");
  const [rawCallId, setRawCallId] = useState("");
  const [rating, setRating] = useState(4);
  const { mutate, mutation } = useCustomMutation();

  const canSubmit = title.trim().length >= 2
    && scenario.trim().length > 0
    && lesson.trim().length > 0;

  const handleSubmit = () => {
    if (!canSubmit) return;
    mutate(
      {
        url: "supervisor/training-cases",
        method: "post",
        values: {
          title: title.trim(),
          category,
          scenario: scenario.trim(),
          lesson: lesson.trim(),
          raw_call_id: rawCallId.trim() ? Number(rawCallId.trim()) : null,
          rating,
        },
      },
      {
        onSuccess: () => onCreated(),
        onError: (err) => alert(`录入失败:${(err as { message?: string }).message ?? "请重试"}`),
      },
    );
  };

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "white", borderRadius: 8, width: 560, maxWidth: "92%",
          maxHeight: "90vh", overflowY: "auto",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            padding: 16, borderBottom: "1px solid #e5e7eb",
            display: "flex", justifyContent: "space-between", alignItems: "center",
            position: "sticky", top: 0, background: "white",
          }}
        >
          <span style={{ fontWeight: 600 }}>手动录入培训案例</span>
          <button type="button" onClick={onClose} style={{ border: "none", background: "transparent", cursor: "pointer" }}>
            <X size={18} />
          </button>
        </div>
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="form-group">
            <label className="form-label">
              标题 <span style={{ color: "#dc2626" }}>*</span>
            </label>
            <input
              type="text"
              className="form-control"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="如:经济困难型业主:3 个月分期方案达成承诺"
              maxLength={256}
            />
          </div>
          <div className="form-group">
            <label className="form-label">
              分类 <span style={{ color: "#dc2626" }}>*</span>
            </label>
            <select
              className="form-control"
              value={category}
              onChange={(e) => setCategory(e.target.value as TrainingCase["category"])}
            >
              <option value="negotiate">协商成功</option>
              <option value="escalate">升级处置</option>
              <option value="objection">异议处理</option>
              <option value="investigate">调查定位</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">
              场景描述 <span style={{ color: "#dc2626" }}>*</span>
            </label>
            <textarea
              className="form-control"
              rows={4}
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
              placeholder="2-3 句话说明:业主背景 / 催收员动作 / 结果"
            />
          </div>
          <div className="form-group">
            <label className="form-label">
              复盘要点 <span style={{ color: "#dc2626" }}>*</span>
            </label>
            <textarea
              className="form-control"
              rows={4}
              value={lesson}
              onChange={(e) => setLesson(e.target.value)}
              placeholder="3-5 条 bullet 概括关键技巧(用 ①②③ 标号便于阅读)"
            />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div className="form-group">
              <label className="form-label">原通话 ID(选填)</label>
              <input
                type="text"
                className="form-control"
                value={rawCallId}
                onChange={(e) => setRawCallId(e.target.value.replace(/[^0-9]/g, ""))}
                placeholder="如:1024"
              />
            </div>
            <div className="form-group">
              <label className="form-label">星级(0-5)</label>
              <select
                className="form-control"
                value={rating}
                onChange={(e) => setRating(Number(e.target.value))}
              >
                {[0, 1, 2, 3, 4, 5].map((r) => (
                  <option key={r} value={r}>{"★".repeat(r) || "(无)"}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
        <div
          style={{
            padding: 16, borderTop: "1px solid #e5e7eb",
            display: "flex", justifyContent: "flex-end", gap: 8,
          }}
        >
          <button
            type="button"
            className="ds-btn ds-btn-secondary"
            onClick={onClose}
            disabled={mutation.isPending}
          >
            取消
          </button>
          <button
            type="button"
            className="ds-btn ds-btn-primary"
            onClick={handleSubmit}
            disabled={!canSubmit || mutation.isPending}
            style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
          >
            {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            录入案例
          </button>
        </div>
      </div>
    </div>
  );
}
