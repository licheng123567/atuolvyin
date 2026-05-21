// v0.7.0 — 催收员侧培训案例库(只读浏览)
//
// 后端:
//   GET  /api/v1/agent/me/training-cases?category=&page=&page_size=
//   POST /api/v1/agent/me/training-cases/{id}/view  (+1 学习计数)
//
// 复用 supervisor/training 设计:category 4 种 filter chip + 卡片网格 + 详情 modal。
// 与 supervisor 不同:只读、无「手动入库」按钮、无「转培训」入口(那是督导的)。
// App WebView 也能加载本页面 — 催收员在 Android 端通过 WebView 访问。
import { useCustom, useCustomMutation } from "@refinedev/core";
import { BookMarked, Filter, Headphones, Loader2, Sparkles, Star, X } from "lucide-react";
import { useState } from "react";

interface TrainingCase {
  id: number;
  title: string;
  category: "investigate" | "negotiate" | "escalate" | "objection";
  scenario: string;
  lesson: string;
  raw_call_id: number | null;
  source: "auto" | "manual";
  rating: number;
  views: number;
  created_at: string;
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

export function AgentTrainingPage() {
  const [filter, setFilter] = useState<(typeof CATEGORIES)[number]["v"]>("all");
  const [viewing, setViewing] = useState<TrainingCase | null>(null);

  const { query } = useCustom<ListResp>({
    url: "agent/me/training-cases",
    method: "get",
    config: {
      query: {
        ...(filter !== "all" ? { category: filter } : {}),
        page: 1,
        page_size: 60,
      },
    },
    queryOptions: { retry: false },
  });

  const items: TrainingCase[] = query.data?.data?.items ?? [];

  return (
    <div style={{ padding: 16 }}>
      <div className="page-header" style={{ marginBottom: 12 }}>
        <div>
          <div className="page-title" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <BookMarked className="w-5 h-5" />
            培训案例库
          </div>
          <div className="page-subtitle">
            学习督导沉淀的优秀通话案例 — 协商技巧 / 异议处理 / 失联调查 / 风险升级
          </div>
        </div>
      </div>

      <div className="filters-bar" style={{ marginBottom: 16, gap: 8, display: "flex", flexWrap: "wrap" }}>
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
      </div>

      {query.isLoading && (
        <div style={{ padding: 32, textAlign: "center", color: "#9ca3af" }}>
          加载中…
        </div>
      )}

      {!query.isLoading && items.length === 0 && (
        <div
          style={{
            padding: 32,
            textAlign: "center",
            color: "#9ca3af",
            background: "white",
            border: "1px dashed #e5e7eb",
            borderRadius: 8,
          }}
        >
          本租户暂无培训案例 — 督导沉淀后会展示在这里
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
          gap: 12,
        }}
      >
        {items.map((c) => (
          <CaseCard key={c.id} c={c} onOpen={() => setViewing(c)} />
        ))}
      </div>

      {viewing && (
        <DetailModal
          c={viewing}
          onClose={() => {
            setViewing(null);
            // 刷新列表以更新 view 计数
            void query.refetch();
          }}
        />
      )}
    </div>
  );
}

function CaseCard({ c, onOpen }: { c: TrainingCase; onOpen: () => void }) {
  const meta = CATEGORY_META[c.category];
  return (
    <div
      className="ds-card"
      style={{ cursor: "pointer", transition: "box-shadow 0.15s" }}
      onClick={onOpen}
      onMouseEnter={(e) => (e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.08)")}
      onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "")}
    >
      <div className="card-body" style={{ padding: 14 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 6 }}>
          <div style={{ display: "flex", gap: 4, alignItems: "center", flexWrap: "wrap" }}>
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

        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6, lineHeight: 1.4 }}>
          {c.title}
        </div>

        <div
          style={{
            fontSize: 12,
            color: "var(--color-neutral-600)",
            lineHeight: 1.5,
            display: "-webkit-box",
            WebkitLineClamp: 3,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
            marginBottom: 8,
          }}
        >
          {c.scenario}
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: 11,
            color: "var(--color-neutral-500)",
          }}
        >
          <span>{c.views} 人学过</span>
          <span style={{ color: "var(--color-primary)" }}>点击查看 →</span>
        </div>
      </div>
    </div>
  );
}

function DetailModal({ c, onClose }: { c: TrainingCase; onClose: () => void }) {
  const meta = CATEGORY_META[c.category];
  const { mutate: viewMutate, mutation } = useCustomMutation();
  const [opened, setOpened] = useState(false);

  // 打开时 +1 view 计数
  if (!opened) {
    setOpened(true);
    viewMutate({
      url: `agent/me/training-cases/${c.id}/view`,
      method: "post",
      values: {},
    });
  }

  const handleListen = () => {
    if (c.raw_call_id) {
      alert(`即将播放通话 #${c.raw_call_id} 录音 — 录音播放器待集成`);
    } else {
      alert("本案例无原始通话录音,仅作书面复盘材料");
    }
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
          background: "white", borderRadius: 8, width: 600, maxWidth: "92%",
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
          <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            <span className={meta.badge} style={{ fontSize: 11 }}>{meta.label}</span>
            <strong style={{ fontSize: 15 }}>{c.title}</strong>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ border: "none", background: "transparent", cursor: "pointer" }}
          >
            <X size={18} />
          </button>
        </div>

        <div style={{ padding: 16 }}>
          {/* 评分 + 学习人数 */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 14,
              fontSize: 12,
              color: "var(--color-neutral-600)",
            }}
          >
            <div style={{ display: "flex", gap: 2 }}>
              {[1, 2, 3, 4, 5].map((s) => (
                <Star
                  key={s}
                  className="w-3.5 h-3.5"
                  style={{
                    color: s <= c.rating ? "#f59e0b" : "var(--color-neutral-300)",
                    fill: s <= c.rating ? "#f59e0b" : "transparent",
                  }}
                />
              ))}
              <span style={{ marginLeft: 6 }}>督导评级</span>
            </div>
            <span>{c.views} 人学过</span>
          </div>

          {/* 场景 */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4, color: "#374151" }}>
              📋 场景描述
            </div>
            <div
              style={{
                fontSize: 13, color: "var(--color-neutral-700)", lineHeight: 1.7,
                whiteSpace: "pre-wrap", padding: 10,
                background: "#f9fafb", borderRadius: 4,
              }}
            >
              {c.scenario}
            </div>
          </div>

          {/* 复盘要点 */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4, color: "var(--color-success)" }}>
              📌 复盘要点
            </div>
            <div
              style={{
                fontSize: 13, color: "var(--color-neutral-700)", lineHeight: 1.7,
                whiteSpace: "pre-wrap", padding: 10,
                background: "#f0fdf4", borderRadius: 4,
                border: "1px solid #bbf7d0",
              }}
            >
              {c.lesson}
            </div>
          </div>

          {/* 听录音按钮 */}
          {c.raw_call_id && (
            <button
              type="button"
              className="ds-btn ds-btn-secondary"
              style={{ width: "100%", display: "flex", alignItems: "center", gap: 6, justifyContent: "center" }}
              onClick={handleListen}
            >
              {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <Headphones className="w-3.5 h-3.5" />
              听原通话录音 (#{c.raw_call_id})
            </button>
          )}
        </div>

        <div
          style={{
            padding: 12, borderTop: "1px solid #e5e7eb",
            fontSize: 11, color: "var(--color-neutral-500)", textAlign: "center",
          }}
        >
          {c.source === "auto" ? "系统自动入库" : "督导手工录入"} · {new Date(c.created_at).toLocaleDateString("zh-CN")}
        </div>
      </div>
    </div>
  );
}

export default AgentTrainingPage;
