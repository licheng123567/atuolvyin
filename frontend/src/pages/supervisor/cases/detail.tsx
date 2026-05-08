// 督导侧案件详情 — v1.6
// 优先调后端 GET /api/v1/supervisor/cases/:id；后端 404 / 加载失败 → fallback 到 mock，保留 demo 演示能力
// 路径在 /supervisor/cases/:id 但后端 endpoint 允许 supervisor / admin / legal 三种角色访问（按 tenant_id 隔离）
import { useCustom, useGetIdentity } from "@refinedev/core";
import { ArrowLeft, BadgePercent, Briefcase, ClipboardList, FileText, Headphones, Phone, X } from "lucide-react";
import type { AuthUser } from "../../../providers/auth-provider";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { OFFER_TYPE_LABELS, type OfferType } from "../../discount/_mock";
import { useCreateDiscountOffer } from "../../discount/api";
import { useDiscountPolicy, useDiscountPolicyForCase, decideApproverRoleWithPolicy } from "../../../hooks/useDiscountPolicy";

interface BackendWorkOrder {
  id: number;
  order_type: string;
  description: string;
  status: string;
  priority: string;
  resolution: string | null;
  created_at: string | null;
}

interface BackendCaseDetail {
  id: number;
  owner_name: string | null;
  building: string | null;
  room: string | null;
  phone_masked: string | null;
  amount: number | null;
  principal_amount: number | null;
  late_fee_amount: number | null;
  bill_period_start: string | null;
  bill_period_end: string | null;
  arrears_reason: string | null;
  months_overdue: number | null;
  status: string;
  agent_name: string | null;
  project_name: string | null;
  project_id: number | null;
  project_info?: ProjectInfo | null;
  notes: string | null;
  recent_calls: {
    id: number;
    date: string | null;
    duration_sec: number | null;
    agent: string;
    result_tag: string | null;
    emotion_tag: string | null;
    ai_summary: string | null;
    risk_flagged: boolean;
  }[];
  timeline: { time: string | null; type: string; desc: string }[];
  work_orders: BackendWorkOrder[];
}

function fmtDuration(sec: number | null): string {
  if (sec === null) return "—";
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

interface CallRecord {
  id: number;
  date: string;
  duration: string;
  agent: string;
  result: string;
  result_badge: string;
  ai_intent: string;
}

interface TimelineEvent {
  time: string;
  type: "call" | "label" | "promise" | "escalate" | "alert";
  desc: string;
}

interface CaseSnapshot {
  id: number;
  owner_name: string;
  building: string;
  phone: string;
  amount: number;
  months_overdue: number;
  status: string;
  status_badge: string;
  agent: string;
  raised_by: string | null;
  raised_at: string | null;
  raised_reason: string | null;
  project_name: string;
  recent_calls: CallRecord[];
  timeline: TimelineEvent[];
  // v1.6 — 真实账单 + 工单 + 欠费理由（mock 阶段可缺省）
  principal_amount?: number | null;
  late_fee_amount?: number | null;
  bill_period_start?: string | null;
  bill_period_end?: string | null;
  arrears_reason?: string | null;
  work_orders?: BackendWorkOrder[];
  // v1.6.3 — 项目基本信息（合同 + 收费）
  project_info?: ProjectInfo | null;
}

interface ProjectInfo {
  name: string;
  charge_rate_text: string | null;
  charge_period: string | null;
  contract_type: string | null;
  contract_start_date: string | null;
  contract_end_date: string | null;
  contract_attachment_key: string | null;
  contract_attachment_filename: string | null;
  charge_notes: string | null;
}

const MOCK_CASES: Record<number, CaseSnapshot> = {
  101: {
    id: 101, owner_name: "张大伟", building: "3-1201", phone: "138****8801", amount: 24800, months_overdue: 18,
    status: "升级中", status_badge: "ds-badge ds-badge-red",
    agent: "李小红", raised_by: "李小红", raised_at: "2026-05-08 14:28",
    raised_reason: "业主多次拒接电话，并明确表示「不想交」，存在恶意拖欠倾向",
    project_name: "金桂园 2026 年欠费催收",
    recent_calls: [
      { id: 1240, date: "2026-05-07 10:14", duration: "0:32", agent: "李小红", result: "拒接", result_badge: "ds-badge ds-badge-gray", ai_intent: "—" },
      { id: 1235, date: "2026-05-06 14:02", duration: "1:18", agent: "李小红", result: "拒缴", result_badge: "ds-badge ds-badge-red", ai_intent: "拒缴 + 情绪激动" },
      { id: 1228, date: "2026-05-04 09:45", duration: "2:36", agent: "李小红", result: "拒缴", result_badge: "ds-badge ds-badge-red", ai_intent: "拒缴" },
    ],
    timeline: [
      { time: "2026-05-08 14:28", type: "escalate", desc: "李小红 标记升级（恶意拖欠倾向）" },
      { time: "2026-05-07 10:14", type: "call", desc: "第 6 通拨打，业主拒接 32s 挂断" },
      { time: "2026-05-06 14:02", type: "call", desc: "通话 1:18，业主明确「不想交」" },
      { time: "2026-05-04 09:45", type: "label", desc: "AI 标签：拒缴 / 情绪激动" },
      { time: "2026-04-25 10:00", type: "alert", desc: "L1 风控告警：检测到威胁性话术" },
    ],
  },
  102: {
    id: 102, owner_name: "王秀英", building: "8-0902", phone: "138****8802", amount: 12600, months_overdue: 11,
    status: "升级中", status_badge: "ds-badge ds-badge-red",
    agent: "王芳芳", raised_by: "王芳芳", raised_at: "2026-05-08 11:15",
    raised_reason: "业主反映物业服务质量问题，要求减免 50%，金额超出协调员权限",
    project_name: "金桂园 2026 年欠费催收",
    recent_calls: [
      { id: 1238, date: "2026-05-08 10:50", duration: "5:42", agent: "王芳芳", result: "异议", result_badge: "ds-badge ds-badge-orange", ai_intent: "服务质量异议 + 减免诉求" },
    ],
    timeline: [
      { time: "2026-05-08 11:15", type: "escalate", desc: "王芳芳 标记升级（金额超权）" },
      { time: "2026-05-08 10:50", type: "call", desc: "通话 5:42，业主要求减免 50%（¥6,300）" },
      { time: "2026-05-02 09:00", type: "promise", desc: "业主承诺先缴 30%（未兑现）" },
    ],
  },
  103: {
    id: 103, owner_name: "刘建国", building: "1-0301", phone: "138****8803", amount: 8400, months_overdue: 8,
    status: "升级中", status_badge: "ds-badge ds-badge-red",
    agent: "张建华", raised_by: "张建华", raised_at: "2026-05-07 16:42",
    raised_reason: "业主已搬离 6 个月，新住户拒绝代缴，需法务介入确认责任主体",
    project_name: "翠湖湾电梯专项整改",
    recent_calls: [
      { id: 1230, date: "2026-05-07 14:30", duration: "3:12", agent: "张建华", result: "失联", result_badge: "ds-badge ds-badge-gray", ai_intent: "—" },
    ],
    timeline: [
      { time: "2026-05-07 16:42", type: "escalate", desc: "张建华 标记升级（责任主体不清）" },
      { time: "2026-05-07 14:30", type: "call", desc: "新住户回应：原业主已搬走，拒绝代缴" },
      { time: "2026-05-01 10:15", type: "alert", desc: "连续 3 通拨打无人接听" },
    ],
  },
};

const TIMELINE_ICON: Record<TimelineEvent["type"], { icon: string; color: string }> = {
  call: { icon: "📞", color: "var(--color-primary)" },
  label: { icon: "🏷", color: "var(--color-warning)" },
  promise: { icon: "✋", color: "var(--color-success)" },
  escalate: { icon: "⬆", color: "var(--color-danger)" },
  alert: { icon: "⚠", color: "var(--color-warning)" },
};

// 兜底生成器：传任何 ID 都返回合理的 mock，便于公海/超期预警/升级 三类入口测试
const FALLBACK_OWNERS = ["梁建国", "吴雪梅", "徐明华", "郑丽娟", "黄志强", "曹秀英", "孙志远", "赵云霞"];
const FALLBACK_AGENTS = ["李小红", "王芳芳", "陈明远", "张建华", "刘晓娟"];
const FALLBACK_PROJECTS = ["金桂园 2026 年欠费催收", "翠湖湾电梯专项整改"];

const CHARGE_PERIOD_LABELS: Record<string, string> = {
  monthly: "按月",
  quarterly: "按季",
  semiannual: "按半年",
  annual: "按年",
};
const CONTRACT_TYPE_LABELS: Record<string, string> = {
  preliminary_service: "前期物业服务合同",
  elected: "选聘合同",
  re_elected: "续聘合同",
  interim_management: "临时管理合同",
};

function ProjectInfoCard({ info }: { info: ProjectInfo }) {
  // v1.6.3 — 项目基本情况（合同 + 收费）。让案件相关人员一眼看到合规依据
  return (
    <div className="ds-card" style={{ marginBottom: 16, borderLeft: "3px solid #6366f1" }}>
      <div className="card-header" style={{ padding: "12px 16px", borderBottom: "1px solid var(--color-neutral-100)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>📁 项目基本情况</span>
          <span className="ds-badge ds-badge-blue" style={{ fontSize: 10 }}>{info.name}</span>
        </div>
      </div>
      <div style={{ padding: 12, display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10, fontSize: 13 }}>
        {info.charge_rate_text && (
          <div style={{ gridColumn: "span 2" }}>
            <div style={{ fontSize: 11, color: "var(--color-neutral-500)", marginBottom: 4 }}>收费标准</div>
            <div style={{ whiteSpace: "pre-wrap", color: "var(--color-neutral-700)", lineHeight: 1.6 }}>{info.charge_rate_text}</div>
          </div>
        )}
        {info.charge_period && (
          <div>
            <div style={{ fontSize: 11, color: "var(--color-neutral-500)", marginBottom: 2 }}>收费周期</div>
            <div>{CHARGE_PERIOD_LABELS[info.charge_period] ?? info.charge_period}</div>
          </div>
        )}
        {info.contract_type && (
          <div>
            <div style={{ fontSize: 11, color: "var(--color-neutral-500)", marginBottom: 2 }}>合同类型</div>
            <div>{CONTRACT_TYPE_LABELS[info.contract_type] ?? info.contract_type}</div>
          </div>
        )}
        {(info.contract_start_date || info.contract_end_date) && (
          <div style={{ gridColumn: "span 2" }}>
            <div style={{ fontSize: 11, color: "var(--color-neutral-500)", marginBottom: 2 }}>合同期</div>
            <div>{info.contract_start_date ?? "—"} ~ {info.contract_end_date ?? "—"}</div>
          </div>
        )}
        {info.contract_attachment_key && (
          <div style={{ gridColumn: "span 2" }}>
            <div style={{ fontSize: 11, color: "var(--color-neutral-500)", marginBottom: 2 }}>合同附件</div>
            <div>📎 {info.contract_attachment_filename ?? "已上传"}</div>
          </div>
        )}
        {info.charge_notes && (
          <div style={{ gridColumn: "span 2" }}>
            <div style={{ fontSize: 11, color: "var(--color-neutral-500)", marginBottom: 4 }}>收费备注</div>
            <div style={{ whiteSpace: "pre-wrap", color: "var(--color-neutral-700)", lineHeight: 1.6 }}>{info.charge_notes}</div>
          </div>
        )}
      </div>
    </div>
  );
}

function BillBreakdownCard({ snapshot }: { snapshot: CaseSnapshot }) {
  // v1.6.3 — 不再按月推算明细；直接展示导入时录入的总额（物业费 + 违约金 = 欠费总额）
  const principal = snapshot.principal_amount ?? 0;
  const lateFee = snapshot.late_fee_amount ?? 0;
  const total = snapshot.amount;
  const fmt = (n: number) => `¥${n.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}`;
  return (
    <div className="ds-card" style={{ marginBottom: 16 }}>
      <div className="card-header" style={{ padding: "12px 16px", borderBottom: "1px solid var(--color-neutral-100)" }}>
        <span style={{ fontWeight: 600, fontSize: 14 }}>欠费明细</span>
        {(snapshot.bill_period_start || snapshot.bill_period_end) && (
          <div style={{ fontSize: 12, color: "var(--color-neutral-700)", marginTop: 4 }}>
            账单期：{snapshot.bill_period_start ?? "—"} ~ {snapshot.bill_period_end ?? "—"}
          </div>
        )}
      </div>
      <div style={{ padding: "12px 16px", display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
        <div style={{ padding: 10, background: "#f9fafb", borderRadius: 6 }}>
          <div style={{ fontSize: 11, color: "var(--color-neutral-500)" }}>物业费</div>
          <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2 }}>{fmt(principal)}</div>
        </div>
        <div style={{ padding: 10, background: "#fef3c7", borderRadius: 6 }}>
          <div style={{ fontSize: 11, color: "#92400e" }}>违约金</div>
          <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2, color: "#92400e" }}>{fmt(lateFee)}</div>
        </div>
        <div style={{ padding: 10, background: "#fee2e2", borderRadius: 6 }}>
          <div style={{ fontSize: 11, color: "#991b1b" }}>欠费总额</div>
          <div style={{ fontSize: 18, fontWeight: 700, marginTop: 2, color: "#991b1b" }}>{fmt(total)}</div>
        </div>
      </div>
      {snapshot.principal_amount == null && snapshot.late_fee_amount == null && (
        <div style={{ padding: "0 16px 12px", fontSize: 11, color: "var(--color-neutral-500)" }}>
          ⓘ 此案件未录入物业费 / 违约金拆分，仅显示欠费总额
        </div>
      )}
    </div>
  );
}

function WorkOrdersCard({ workOrders }: { workOrders: BackendWorkOrder[] }) {
  const orderTypeLabels: Record<string, string> = {
    quality: "服务质量",
    reduction: "减免申请",
    dispute: "争议",
    other: "其他",
  };
  const statusLabels: Record<string, { label: string; cls: string }> = {
    open: { label: "待处理", cls: "ds-badge ds-badge-orange" },
    in_progress: { label: "处理中", cls: "ds-badge ds-badge-blue" },
    resolved: { label: "已解决", cls: "ds-badge ds-badge-green" },
    closed: { label: "已关闭", cls: "ds-badge ds-badge-gray" },
  };
  return (
    <div className="ds-card" style={{ marginTop: 16 }}>
      <div className="card-header" style={{ display: "flex", alignItems: "center", gap: 6, padding: "12px 16px", borderBottom: "1px solid var(--color-neutral-100)" }}>
        <ClipboardList className="w-4 h-4" style={{ color: "var(--color-primary)" }} />
        <span style={{ fontWeight: 600, fontSize: 14 }}>关联工单（{workOrders.length}）</span>
      </div>
      {workOrders.length === 0 ? (
        <div style={{ padding: 16, fontSize: 12, color: "var(--color-neutral-400)" }}>
          暂无工单 — 通话中识别到「服务质量异议 / 减免申请」会自动创建
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>工单号</th>
                <th>类型</th>
                <th>描述</th>
                <th>优先级</th>
                <th>状态</th>
                <th>创建时间</th>
              </tr>
            </thead>
            <tbody>
              {workOrders.map((w) => {
                const s = statusLabels[w.status] ?? { label: w.status, cls: "ds-badge ds-badge-gray" };
                return (
                  <tr key={w.id}>
                    <td style={{ color: "var(--color-primary)" }}>#{w.id}</td>
                    <td>{orderTypeLabels[w.order_type] ?? w.order_type}</td>
                    <td style={{ fontSize: 12, maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={w.description}>{w.description}</td>
                    <td><span className="ds-badge ds-badge-gray" style={{ fontSize: 10 }}>{w.priority}</span></td>
                    <td><span className={s.cls}>{s.label}</span></td>
                    <td style={{ fontSize: 12, color: "var(--color-neutral-500)" }}>{w.created_at?.replace("T", " ").slice(0, 16) ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function generateFallback(caseId: number): CaseSnapshot {
  const seed = Math.abs(caseId);
  const owner = FALLBACK_OWNERS[seed % FALLBACK_OWNERS.length];
  const agent = FALLBACK_AGENTS[seed % FALLBACK_AGENTS.length];
  const project = FALLBACK_PROJECTS[seed % FALLBACK_PROJECTS.length];
  const months = (seed % 8) + 2;
  const amount = months * 1240;
  const building = `${(seed % 9) + 1}-${String(((seed * 17) % 32) + 1).padStart(2, "0")}0${(seed % 4) + 1}`;
  return {
    id: caseId,
    owner_name: owner,
    building,
    phone: `138****${String((seed * 13) % 10000).padStart(4, "0")}`,
    amount,
    months_overdue: months,
    status: "跟进中",
    status_badge: "ds-badge ds-badge-blue",
    agent,
    raised_by: null,
    raised_at: null,
    raised_reason: null,
    project_name: project,
    recent_calls: [
      { id: 9000 + seed, date: "2026-05-07 10:14", duration: "2:18", agent, result: "异议", result_badge: "ds-badge ds-badge-orange", ai_intent: "经济困难 + 暂缓诉求" },
      { id: 9001 + seed, date: "2026-05-04 14:02", duration: "1:36", agent, result: "失联", result_badge: "ds-badge ds-badge-gray", ai_intent: "—" },
    ],
    timeline: [
      { time: "2026-05-07 10:14", type: "call", desc: `通话 2:18，业主表达经济困难，请求暂缓` },
      { time: "2026-05-04 14:02", type: "call", desc: `第 ${(seed % 5) + 2} 通拨打，业主未接听` },
      { time: "2026-04-28 09:00", type: "label", desc: "AI 标签：经济困难 / 暂缓" },
    ],
  };
}

export function SupervisorCaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const caseId = Number(id);
  const [discountModalOpen, setDiscountModalOpen] = useState(false);
  // v1.6.1 — 按 caseId 拉 effective policy（项目级覆盖租户级）
  const policy = useDiscountPolicyForCase(caseId);
  const { data: identity } = useGetIdentity<AuthUser>();
  // 仅 supervisor + admin 可发起减免；legal 角色看完整案件但不发起
  const canStartDiscount = identity?.role === "supervisor" || identity?.role === "admin";

  // 优先调后端
  const { query } = useCustom<BackendCaseDetail>({
    url: `supervisor/cases/${caseId}`,
    method: "get",
    queryOptions: { enabled: !!caseId, retry: false },
  });
  const backend = query.data?.data;

  // 优先级：后端 → 静态 mock → 兜底生成
  const c: CaseSnapshot = backend
    ? {
        id: backend.id,
        owner_name: backend.owner_name ?? "—",
        building: backend.building ?? backend.room ?? "—",
        phone: backend.phone_masked ?? "—",
        amount: backend.amount ?? 0,
        months_overdue: backend.months_overdue ?? 0,
        status: backend.status === "escalated" ? "升级中" : (backend.status === "promised" ? "承诺缴费" : "跟进中"),
        status_badge: backend.status === "escalated" ? "ds-badge ds-badge-red" : "ds-badge ds-badge-blue",
        agent: backend.agent_name ?? "—",
        raised_by: backend.status === "escalated" ? backend.agent_name : null,
        raised_at: null,
        raised_reason: backend.notes,
        project_name: backend.project_name ?? "—",
        recent_calls: backend.recent_calls.map((r) => ({
          id: r.id,
          date: r.date?.replace("T", " ").slice(0, 19) ?? "—",
          duration: fmtDuration(r.duration_sec),
          agent: r.agent || "—",
          result: r.result_tag ?? "—",
          result_badge: r.risk_flagged
            ? "ds-badge ds-badge-red"
            : r.result_tag === "拒缴"
              ? "ds-badge ds-badge-red"
              : r.result_tag === "承诺"
                ? "ds-badge ds-badge-orange"
                : "ds-badge ds-badge-gray",
          ai_intent: r.ai_summary ?? "—",
        })),
        timeline: backend.timeline.map((t) => ({
          time: t.time?.replace("T", " ").slice(0, 19) ?? "—",
          type: (["call", "label", "promise", "escalate", "alert"].includes(t.type)
            ? t.type
            : "call") as TimelineEvent["type"],
          desc: t.desc,
        })),
        principal_amount: backend.principal_amount,
        late_fee_amount: backend.late_fee_amount,
        bill_period_start: backend.bill_period_start,
        bill_period_end: backend.bill_period_end,
        arrears_reason: backend.arrears_reason,
        work_orders: backend.work_orders,
        project_info: backend.project_info ?? null,
      }
    : MOCK_CASES[caseId] ?? generateFallback(caseId);

  return (
    <div>
      <div className="page-header">
        <div>
          <Link to="/supervisor/escalated" style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "var(--color-neutral-500)", fontSize: 13, textDecoration: "none", marginBottom: 6 }}>
            <ArrowLeft className="w-3.5 h-3.5" /> 返回升级案件
          </Link>
          <div className="page-title">{c.owner_name} / {c.building}</div>
          <div className="page-subtitle">案件 #{c.id} · {c.phone}</div>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span className={c.status_badge}>{c.status}</span>
          <span className="ds-badge ds-badge-blue" style={{ fontSize: 11 }}>📁 {c.project_name}</span>
        </div>
      </div>

      {/* 顶部基本信息 */}
      <div className="status-bar" style={{ marginBottom: 16 }}>
        <div className="status-bar-item" style={{ color: "var(--color-danger)" }}>
          欠费金额 <strong>¥{c.amount.toLocaleString("zh-CN")}</strong>
        </div>
        <div className="status-bar-item">欠 <strong>{c.months_overdue} 个月</strong></div>
        <div className="status-bar-item">归属催收员 <strong>{c.agent}</strong></div>
      </div>

      {/* v1.6 — 欠费理由（导入时录入） */}
      {c.arrears_reason && (
        <div className="ds-card" style={{ marginBottom: 16, borderLeft: "3px solid var(--color-warning)" }}>
          <div className="card-body" style={{ padding: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
              <Briefcase size={14} style={{ color: "var(--color-warning)" }} />
              <span style={{ fontWeight: 600, fontSize: 14 }}>欠费理由（导入时录入）</span>
            </div>
            <div style={{ fontSize: 13, color: "var(--color-neutral-700)", lineHeight: 1.7 }}>{c.arrears_reason}</div>
          </div>
        </div>
      )}

      {c.raised_by && (
        <div className="ds-card" style={{ marginBottom: 16, borderLeft: "3px solid var(--color-danger)" }}>
          <div className="card-body" style={{ padding: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
              <Briefcase size={14} style={{ color: "var(--color-danger)" }} />
              <span style={{ fontWeight: 600, fontSize: 14 }}>升级理由</span>
              <span style={{ fontSize: 12, color: "var(--color-neutral-500)", marginLeft: "auto" }}>
                {c.raised_by} · {c.raised_at}
              </span>
            </div>
            <div style={{ fontSize: 13, color: "var(--color-neutral-700)", lineHeight: 1.7 }}>{c.raised_reason}</div>
          </div>
        </div>
      )}

      {/* v1.6.3 — 项目基本情况（合同 + 收费） */}
      {c.project_info && <ProjectInfoCard info={c.project_info} />}

      {/* v1.6.3 — 欠费明细（物业费 + 违约金 + 总额，不再按月推算） */}
      <BillBreakdownCard snapshot={c} />

      {/* 通话记录 */}
      <div className="ds-card" style={{ marginBottom: 16 }}>
        <div className="card-header" style={{ display: "flex", alignItems: "center", gap: 6, padding: "12px 16px", borderBottom: "1px solid var(--color-neutral-100)" }}>
          <Phone className="w-4 h-4" style={{ color: "var(--color-primary)" }} />
          <span style={{ fontWeight: 600, fontSize: 14 }}>近期通话记录（{c.recent_calls.length}）</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>通话</th>
                <th>时间</th>
                <th>时长</th>
                <th>催收员</th>
                <th>结果</th>
                <th>AI 标签</th>
                <th>录音</th>
              </tr>
            </thead>
            <tbody>
              {c.recent_calls.map((r) => (
                <tr key={r.id}>
                  <td style={{ color: "var(--color-primary)" }}>#{r.id}</td>
                  <td>{r.date}</td>
                  <td>{r.duration}</td>
                  <td>{r.agent}</td>
                  <td><span className={r.result_badge}>{r.result}</span></td>
                  <td style={{ fontSize: 12 }}>{r.ai_intent}</td>
                  <td>
                    <button type="button" className="ds-btn ds-btn-ghost ds-btn-sm">
                      <Headphones className="w-3 h-3" /> 听
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 操作时间线 */}
      <div className="ds-card">
        <div className="card-header" style={{ display: "flex", alignItems: "center", gap: 6, padding: "12px 16px", borderBottom: "1px solid var(--color-neutral-100)" }}>
          <ClipboardList className="w-4 h-4" style={{ color: "var(--color-primary)" }} />
          <span style={{ fontWeight: 600, fontSize: 14 }}>案件时间线</span>
        </div>
        <div className="card-body" style={{ padding: 16 }}>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {c.timeline.map((t, i) => {
              const meta = TIMELINE_ICON[t.type];
              return (
                <li key={i} style={{ display: "flex", gap: 10, paddingBottom: 14, position: "relative" }}>
                  <div style={{ width: 28, flexShrink: 0, textAlign: "center" }}>
                    <span style={{ fontSize: 16 }}>{meta.icon}</span>
                  </div>
                  <div style={{ flex: 1, paddingBottom: i < c.timeline.length - 1 ? 6 : 0, borderBottom: i < c.timeline.length - 1 ? "1px solid #f3f4f6" : "none" }}>
                    <div style={{ fontSize: 13, color: "#1f2937" }}>{t.desc}</div>
                    <div style={{ fontSize: 11, color: "var(--color-neutral-500)", marginTop: 2 }}>{t.time}</div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      </div>

      {/* v1.6 — 工单情况 */}
      <WorkOrdersCard workOrders={c.work_orders ?? []} />

      {/* 操作区：发起减免申请（仅 supervisor + admin）*/}
      {canStartDiscount && (
      <div className="ds-card" style={{ marginTop: 16, borderLeft: `3px solid ${policy.disabled ? "var(--color-neutral-300)" : "var(--color-warning)"}` }}>
        <div className="card-body" style={{ padding: 16, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 240 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <span style={{ fontSize: 14, fontWeight: 600 }}>协商打折 / 减免申请</span>
              {policy.source === "project" && (
                <span className="ds-badge ds-badge-blue" style={{ fontSize: 10 }}>
                  按本项目策略
                </span>
              )}
            </div>
            <div style={{ fontSize: 12, color: "var(--color-neutral-600)", lineHeight: 1.6 }}>
              {policy.disabled ? (
                <span style={{ color: "var(--color-danger)" }}>
                  ⚠ 本{policy.source === "project" ? "项目" : "租户"}已停用减免功能
                  {policy.source === "project" && policy.projectName ? `（${policy.projectName}）` : ""}
                  （admin 可在{policy.source === "project" ? "项目设置" : "系统配置"}开启）
                </span>
              ) : (
                <>
                  当业主明确表示「无力一次性缴清 / 主张服务质量异议 / 需分期」时，可发起减免申请。
                  {policy.autoThreshold === 0 ? (
                    <>所有减免均需人工审批；</>
                  ) : (
                    <>&lt; {policy.autoThreshold}% 自动通过；</>
                  )}
                  {policy.autoThreshold}–{policy.supervisorMax}% 督导审批；&gt; {policy.supervisorMax}% 转 admin。
                  {policy.source === "project" && policy.projectName && (
                    <span style={{ color: "var(--color-primary)" }}>（来自项目「{policy.projectName}」覆盖）</span>
                  )}
                </>
              )}
            </div>
          </div>
          <button
            type="button"
            className="ds-btn ds-btn-primary"
            onClick={() => setDiscountModalOpen(true)}
            disabled={policy.disabled}
          >
            <BadgePercent className="w-4 h-4" /> 发起减免申请
          </button>
        </div>
      </div>
      )}

      <div style={{ marginTop: 12, fontSize: 12, color: "var(--color-neutral-500)", display: "flex", alignItems: "center", gap: 4 }}>
        <FileText size={12} />
        v1.6 接入后端后，本页将显示完整通话录音、文书、转法务订单等关联数据
      </div>

      {discountModalOpen && canStartDiscount && (
        <DiscountRequestModal
          caseSnapshot={c}
          policy={policy}
          onClose={() => setDiscountModalOpen(false)}
          onSubmitted={(offerId, decision) => {
            setDiscountModalOpen(false);
            if (decision === "auto") {
              alert(`减免申请 #${offerId} 已自动批准（折扣 < ${policy.autoThreshold}%）`);
            } else if (decision === "supervisor") {
              alert(`减免申请 #${offerId} 已提交督导审批`);
              navigate("/supervisor/discount-approvals");
            } else {
              alert(`减免申请 #${offerId} 已提交 admin 审批（折扣 > ${policy.supervisorMax}%）`);
              navigate("/supervisor/discount-approvals");
            }
          }}
        />
      )}
    </div>
  );
}

function DiscountRequestModal({ caseSnapshot, policy, onClose, onSubmitted }: {
  caseSnapshot: CaseSnapshot;
  policy: ReturnType<typeof useDiscountPolicy>;
  onClose: () => void;
  onSubmitted: (offerId: number, decision: "auto" | "supervisor" | "admin") => void;
}) {
  const [offerType, setOfferType] = useState<OfferType>("principal_discount");
  const [proposedAmount, setProposedAmount] = useState(String(Math.round(caseSnapshot.amount * 0.8)));
  const [installmentMonths, setInstallmentMonths] = useState(3);
  const [reason, setReason] = useState("");
  const { createOffer, isPending } = useCreateDiscountOffer();

  const proposedNum = Number(proposedAmount) || 0;
  const discountPct = caseSnapshot.amount > 0
    ? Math.round(((caseSnapshot.amount - proposedNum) / caseSnapshot.amount) * 100)
    : 0;
  const decision = decideApproverRoleWithPolicy(discountPct, policy);
  const decisionLabel =
    decision === "auto" ? `✅ 自动批准（折扣 < ${policy.autoThreshold}%）`
      : decision === "supervisor" ? `→ 督导审批（${policy.autoThreshold}–${policy.supervisorMax}%）`
      : `→ 转 admin 审批（折扣 > ${policy.supervisorMax}%）`;
  const decisionColor =
    decision === "auto" ? "var(--color-success)"
      : decision === "supervisor" ? "var(--color-warning)"
      : "var(--color-danger)";

  function submit() {
    if (!reason.trim()) return alert("请填写申请理由");
    if (proposedNum < 0 || proposedNum > caseSnapshot.amount) return alert("业主同意支付金额需在 0 ~ 原欠费之间");
    createOffer(
      {
        case_id: caseSnapshot.id,
        offer_type: offerType,
        original_amount: caseSnapshot.amount,
        proposed_amount: offerType === "installment" ? caseSnapshot.amount : proposedNum,
        installment_months: offerType === "installment" ? installmentMonths : null,
        reason: reason.trim(),
      },
      {
        onSuccess: (offer) => onSubmitted(offer.id, decision),
        onError: (e) => {
          const detail = (e as { response?: { data?: { detail?: { message?: string } } } })?.response?.data?.detail;
          alert(detail?.message ?? "提交失败，请重试");
        },
      },
    );
  }

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }} onClick={onClose}>
      <div style={{ background: "white", borderRadius: 8, width: 540, maxWidth: "92%" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ padding: 16, borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between" }}>
          <span style={{ fontWeight: 600 }}>发起减免申请：{caseSnapshot.owner_name} / {caseSnapshot.building}</span>
          <button type="button" onClick={onClose} style={{ border: "none", background: "transparent", cursor: "pointer" }}><X size={18} /></button>
        </div>
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12, maxHeight: "70vh", overflowY: "auto" }}>
          <div style={{ background: "#f9fafb", borderRadius: 6, padding: 10, fontSize: 13 }}>
            原欠费：<strong>¥{caseSnapshot.amount.toLocaleString("zh-CN")}</strong> · 欠 {caseSnapshot.months_overdue} 月
          </div>
          <div className="form-group">
            <label className="form-label">减免类型</label>
            <select className="form-control" value={offerType} onChange={(e) => setOfferType(e.target.value as OfferType)}>
              {Object.entries(OFFER_TYPE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          {offerType === "installment" ? (
            <div className="form-group">
              <label className="form-label">分期月数</label>
              <input type="number" className="form-control" value={installmentMonths} onChange={(e) => setInstallmentMonths(Number(e.target.value))} min={2} max={24} />
              <div style={{ fontSize: 11, color: "var(--color-neutral-500)", marginTop: 4 }}>
                每期金额约 ¥{Math.round(caseSnapshot.amount / Math.max(installmentMonths, 1)).toLocaleString("zh-CN")}
                {installmentMonths > 12 && <span style={{ color: "var(--color-danger)", marginLeft: 6 }}>· &gt; 12 期需 admin 审批</span>}
              </div>
            </div>
          ) : (
            <div className="form-group">
              <label className="form-label">业主同意支付金额（¥）</label>
              <input type="number" className="form-control" value={proposedAmount} onChange={(e) => setProposedAmount(e.target.value)} />
              <div style={{ fontSize: 11, color: decisionColor, marginTop: 4, fontWeight: 600 }}>
                折扣 {discountPct}% — {decisionLabel}
              </div>
            </div>
          )}
          <div className="form-group">
            <label className="form-label">申请理由 <span className="req">*</span></label>
            <textarea
              className="form-control"
              rows={4}
              placeholder="请详细说明：业主原话 / 经济困难 / 服务质量异议 / 房屋空置等。审批人将基于此判断。"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          <div style={{ background: "#fffbeb", padding: 10, borderRadius: 6, fontSize: 12, color: "#78350f", lineHeight: 1.6 }}>
            ⚠ 提交后，业主必须在 7 天内按方案缴清，否则 offer 失效需重新申请。<br />
            ⚠ 整个审批链记入审计日志，admin 可追溯。
          </div>
        </div>
        <div style={{ padding: 16, borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button type="button" className="ds-btn ds-btn-secondary" onClick={onClose}>取消</button>
          <button type="button" className="ds-btn ds-btn-primary" onClick={submit} disabled={isPending}>
            {isPending ? "提交中…" : "提交申请"}
          </button>
        </div>
      </div>
    </div>
  );
}
