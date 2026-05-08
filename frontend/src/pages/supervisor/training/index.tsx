// 培训案例库 — v1.5.7 ⭐⭐
// L2 处置完后，督导一键「转培训案例」，沉淀到本库
// 新人入职可学，月度复盘可用
import { BookMarked, Filter, Headphones, Star } from "lucide-react";
import { useState } from "react";
import { HelpPanel } from "../../../components/ui/HelpPanel";

interface TrainingCase {
  id: number;
  title: string;
  category: "investigate" | "negotiate" | "escalate" | "objection";
  category_label: string;
  category_badge: string;
  scenario: string;       // 场景描述
  lesson: string;         // 复盘要点
  duration: string;       // 通话时长
  raw_call_id: number | null;
  created_by: string;     // 录入督导
  created_at: string;
  rating: number;         // 1-5 星
  views: number;
}

const MOCK_CASES: TrainingCase[] = [
  { id: 1, title: "经济困难型业主：3 个月分期方案达成承诺",
    category: "negotiate", category_label: "协商成功", category_badge: "ds-badge ds-badge-green",
    scenario: "业主刚经历失业，明确表示无力一次性缴清。催收员李小红用「分期方案 + 不影响信用」组合话术，业主承诺次月起每月 ¥820 分 3 期，已兑现 1 期。",
    lesson: "① 先共情再谈数字，不要一上来报金额；② 给业主退路（分期/缓交），不让他没台阶；③ 用「不影响您信用」作为 closing trigger",
    duration: "5:42", raw_call_id: 1024, created_by: "督导小李", created_at: "2026-05-03",
    rating: 5, views: 23 },
  { id: 2, title: "L2 风控：业主投诉骚扰的紧急止损（接管案例）",
    category: "escalate", category_label: "升级处置", category_badge: "ds-badge ds-badge-red",
    scenario: "业主第 6 通拒接后接通即喊「你们这是骚扰」，AI 触发 L2，督导小李 30 秒内强制接管，向业主道歉并承诺 30 天不再致电，案件转法务走律师函。",
    lesson: "① L2 接管的窗口很短（&lt; 1 分钟），督导必须始终在线；② 道歉 + 暂停拨打 + 律师函，三步一起说；③ 录音留作合规证据",
    duration: "1:48", raw_call_id: 1108, created_by: "督导小李", created_at: "2026-05-05",
    rating: 5, views: 41 },
  { id: 3, title: "服务质量异议：电梯故障投诉转化",
    category: "objection", category_label: "异议处理", category_badge: "ds-badge ds-badge-orange",
    scenario: "业主 5-2201 一开口就抱怨电梯坏了 3 次，王芳芳没回避问题，承诺「48 小时给反馈 + 工单已备」，业主答应先缴纳本月物业费。",
    lesson: "① 不抢话不否认，先承认问题存在；② 给具体时限（48h/72h），不要「尽快」「我们关注」；③ 把维修和物业费分账目单独说清",
    duration: "4:28", raw_call_id: 956, created_by: "督导张敏", created_at: "2026-04-30",
    rating: 4, views: 18 },
  { id: 4, title: "失联业主：通过家属代缴策略",
    category: "investigate", category_label: "调查定位", category_badge: "ds-badge ds-badge-blue",
    scenario: "业主连续 8 通失联，张建华查到房产登记联系人为业主父亲，致电父亲沟通后由父亲代缴。",
    lesson: "① 失联超 5 通 → 查房产登记关系人；② 跟父辈沟通用「您的孩子」「家里的事」更软；③ 不强求当场缴，留电话让对方主动联系",
    duration: "3:15", raw_call_id: 887, created_by: "督导王慧", created_at: "2026-04-25",
    rating: 4, views: 12 },
];

const CATEGORIES = [
  { v: "all", label: "全部" },
  { v: "negotiate", label: "协商成功" },
  { v: "escalate", label: "升级处置" },
  { v: "objection", label: "异议处理" },
  { v: "investigate", label: "调查定位" },
] as const;

export function SupervisorTrainingPage() {
  const [filter, setFilter] = useState<typeof CATEGORIES[number]["v"]>("all");
  const visible = MOCK_CASES.filter((c) => filter === "all" || c.category === filter);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">培训案例库</div>
          <div className="page-subtitle">L2 处置 / 优秀通话沉淀为案例，新人入职 + 月度复盘必学</div>
        </div>
      </div>

      <HelpPanel
        tone="tip"
        dismissKey="/supervisor/training"
        title="案例库的两个用途"
        bullets={[
          <><strong>新人入职培训</strong>：每名催收员入职 7 天必看 5 个 5 星案例，学完通过测试才能上岗（v1.6 上线测试模块）</>,
          <><strong>月度复盘</strong>：督导每月初挑 3 个本月案例（含失败案例）做团队培训会，识别共性问题</>,
        ]}
        footer="录入方式：在「质检复核」「风控事件」「升级案件」处置完成后，点「转培训案例」可一键沉淀到此库"
      />

      <div className="filters-bar" style={{ marginBottom: 16 }}>
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

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 16 }}>
        {visible.map((c) => (
          <div
            key={c.id}
            className="ds-card"
            style={{ cursor: "pointer", transition: "box-shadow 0.15s" }}
            onMouseEnter={(e) => (e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.08)")}
            onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "")}
          >
            <div className="card-body" style={{ padding: 16 }}>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 8 }}>
                <span className={c.category_badge} style={{ fontSize: 11 }}>{c.category_label}</span>
                <div style={{ display: "flex", gap: 1 }}>
                  {[1, 2, 3, 4, 5].map((s) => (
                    <Star key={s} className="w-3 h-3" style={{ color: s <= c.rating ? "#f59e0b" : "var(--color-neutral-300)", fill: s <= c.rating ? "#f59e0b" : "transparent" }} />
                  ))}
                </div>
              </div>

              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, lineHeight: 1.4 }}>
                <BookMarked className="w-3.5 h-3.5" style={{ display: "inline", marginRight: 4, color: "var(--color-primary)" }} />
                {c.title}
              </div>

              <div style={{ fontSize: 12, color: "var(--color-neutral-700)", lineHeight: 1.6, marginBottom: 8 }}>
                <strong>场景：</strong>{c.scenario}
              </div>

              <div style={{ fontSize: 12, color: "var(--color-neutral-700)", lineHeight: 1.6, marginBottom: 12, padding: 8, background: "#f9fafb", borderRadius: 4 }}>
                <strong style={{ color: "var(--color-success)" }}>📌 复盘要点：</strong><br />
                {c.lesson}
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 11, color: "var(--color-neutral-500)" }}>
                <span>录入：{c.created_by} · {c.created_at}</span>
                <span>{c.views} 人学过</span>
              </div>

              <div style={{ marginTop: 8 }}>
                <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" style={{ width: "100%" }}>
                  <Headphones className="w-3 h-3" /> 听原通话录音 ({c.duration})
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
