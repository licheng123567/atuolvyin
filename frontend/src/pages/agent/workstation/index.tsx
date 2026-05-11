// 1:1 还原 ui/agent-pc.html#workstation 工作台
// v1.6.5 — 4 列布局 + 5s 轮询 active-call 实现 App→PC 同步
// v1.6.6 — col-2 接真实后端 useOne(agent/cases/:id) + 复用 OwnerInfoCard/ProjectInfoCard/ActivityTimeline
// 所有颜色 / 圆角 / 阴影 / 字号严格按 HTML 原型
// 无 active call 时展示 demo 转写 / AI 建议（让用户看到布局效果）
import { useCreate, useCustom, useCustomMutation, useList, useOne } from "@refinedev/core";
import { Mic, MicOff, PauseCircle, Phone, PhoneOff, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { OwnerInfoCard } from "../../../components/case/OwnerInfoCard";
import { ProjectInfoCard } from "../../../components/case/ProjectInfoCard";
import { DiscountRequestModal } from "../../../components/discount/DiscountRequestModal";
import { QrDialDialog } from "../../../components/dial/QrDialDialog";
import { useCallSocket } from "../../../hooks/useCallSocket";
import type { PaginatedResponse } from "../../../types";
import type { CaseDetailResponse } from "../../../types/case";

// ── 类型 ─────────────────────────────────────────
interface OwnerInfo {
  id: number; name: string; phone_masked: string;
  building: string | null; room: string | null; do_not_call: boolean;
}
interface CaseItem {
  id: number; owner: OwnerInfo;
  pool_type: string; stage: string;
  amount_owed: string | null; months_overdue: number | null;
  project_id: number | null; project_name: string | null;
  last_contact_at?: string | null;
}
interface ActiveCallResp {
  active_call_id: number | null; case_id: number | null;
  started_at: string | null; status: string | null;
  owner_name: string | null; owner_phone_masked: string | null;
  building: string | null; room: string | null;
  amount_owed: string | null;
  project_id: number | null; project_name: string | null;
}

const STAGE_BADGE: Record<string, { label: string; bg: string; color: string }> = {
  new:         { label: "待跟进",   bg: "#fff7ed", color: "#c2410c" },
  in_progress: { label: "跟进中",   bg: "#eff6ff", color: "#1d4ed8" },
  promised:    { label: "承诺缴费", bg: "#eff6ff", color: "#1d4ed8" },
  paid:        { label: "已缴费",   bg: "#f0fdf4", color: "#15803d" },
  escalated:   { label: "升级处理", bg: "#f5f3ff", color: "#6d28d9" },
  closed:      { label: "已关闭",   bg: "#f3f4f6", color: "#6b7280" },
};

function fmtDuration(sec: number): string {
  const m = Math.floor(sec / 60).toString().padStart(2, "0");
  const s = (sec % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toTimeString().slice(0, 8);
}

// ── Demo 数据（无 active call 时展示）─────────────
interface DemoBubble { speaker: "agent" | "owner"; text: string; time: string }
const DEMO_TRANSCRIPT: DemoBubble[] = [
  { speaker: "agent", text: "您好，我是绿城锦绣物业的工作人员，请问是张建国先生吗？", time: "14:28:03" },
  { speaker: "owner", text: "是的，什么事？", time: "14:28:09" },
  { speaker: "agent", text: "您好张先生，您的 3 栋 2 单元 1201 室有 8 个月物业费共 3200 元未缴，请问您方便什么时候来缴纳？", time: "14:28:15" },
  { speaker: "owner", text: "最近手头有点紧，而且你们房子质量也有问题，我不想交。", time: "14:28:38" },
  { speaker: "agent", text: "理解您的顾虑，关于房屋问题我们可以为您提交工单处理，物业费方面您看月底之前一次性缴清行不行？", time: "14:29:05" },
];

interface DemoSuggestion {
  id: string;
  type: "objection" | "script" | "risk";
  typeLabel: string;
  title: string;
  body: string;
  trigger: string;
  confidence: number;
}
const DEMO_SUGGESTIONS: DemoSuggestion[] = [
  {
    id: "d1", type: "objection", typeLabel: "💡 异议识别",
    title: "异议类型：房屋质量投诉",
    body: "业主提及\"房子质量有问题\"，属于典型服务投诉型异议。建议先安抚情绪，承诺工单处理，再回到缴费议题，避免直接争论。",
    trigger: "房子质量有问题", confidence: 84,
  },
  {
    id: "d2", type: "script", typeLabel: "📋 话术推荐",
    title: "安抚 + 工单 + 引导缴费",
    body: "\"张先生，我完全理解您的感受。关于房屋问题，您可以告诉我具体情况，我现在就帮您提交一个紧急工单，专人跟进处理。而物业费方面，我们能否先...\"",
    trigger: "不想交", confidence: 87,
  },
  {
    id: "d3", type: "risk", typeLabel: "⚠️ 风控提示 L1",
    title: "情绪关键词检测",
    body: "检测到\"不想交\"负面情绪词，当前情绪指数：偏激动。建议立即换用安抚话术，避免语气强硬。",
    trigger: "不想交", confidence: 79,
  },
];

const CARD_STYLE: Record<string, { border: string; bg: string }> = {
  objection: { border: "#3b82f6", bg: "#f0f9ff" },
  script:    { border: "#059669", bg: "#f0fdf4" },
  risk:      { border: "#f59e0b", bg: "#fffbeb" },
};

export function AgentWorkstationIndexPage() {
  const token = localStorage.getItem("access_token") ?? "";
  const [keyword, setKeyword] = useState("");
  const [stageFilter, setStageFilter] = useState("");
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(null);
  const [qrState, setQrState] = useState<{ caseId: number; qrPayload: string; expiresAt: string } | null>(null);
  const [discountForCaseId, setDiscountForCaseId] = useState<number | null>(null);  // v1.6.9 — 减免申请 Modal
  const lastQrCaseId = useRef<number | null>(null);
  const [muted, setMuted] = useState(false);
  const [dismissedRisk, setDismissedRisk] = useState<Set<string>>(new Set());
  const [dismissedSugg, setDismissedSugg] = useState<Set<string>>(new Set());
  // v1.6.7 — 工作台默认聚合「今日待联系」（用户提议）
  const [todayMode, setTodayMode] = useState(true);

  // ── 案件列表（today=true 时后端只返今日相关）─────────────
  const caseFilters: { field: string; operator: "eq"; value: unknown }[] = [];
  if (stageFilter) caseFilters.push({ field: "stage", operator: "eq", value: stageFilter });
  if (todayMode) caseFilters.push({ field: "today", operator: "eq", value: true });

  const { query: caseListQuery } = useList<CaseItem>({
    resource: "agent/cases",
    pagination: { currentPage: 1, pageSize: 50 },
    filters: caseFilters,
  });
  const caseRaw = caseListQuery.data?.data;
  const caseItems: CaseItem[] =
    (caseRaw as unknown as PaginatedResponse<CaseItem>)?.items ??
    (caseRaw as CaseItem[] | undefined) ?? [];
  const filteredCases = keyword
    ? caseItems.filter((c) =>
        (c.owner.name ?? "").includes(keyword)
        || (c.owner.building ?? "").includes(keyword)
        || (c.owner.room ?? "").includes(keyword),
      )
    : caseItems;

  // v1.6.7 — E2 今日 KPI 进度条
  const { query: kpiQuery } = useCustom<{
    date: string; calls_today: number; calls_target: number;
    connected_today: number; promised_today: number; paid_today: number;
    minutes_used_today: number;
  }>({ url: "agent/me/today-kpi", method: "get", queryOptions: { refetchInterval: 30000 } });
  const kpi = kpiQuery.data?.data;

  // v1.6.7 — E1 「下一个」按钮：选下一条未结案、不是当前选中的
  function selectNextCase() {
    if (filteredCases.length === 0) return;
    const idx = filteredCases.findIndex((c) => c.id === selectedCaseId);
    const nextIdx = (idx + 1) % filteredCases.length;
    setSelectedCaseId(filteredCases[nextIdx].id);
  }

  // ── 5s 轮询 active-call ────────────────────
  const { query: activeCallQuery } = useCustom<ActiveCallResp>({
    url: "agent/me/active-call",
    method: "get",
    queryOptions: { refetchInterval: 5000 },
  });
  const activeCall = activeCallQuery.data?.data;
  const activeCallId = activeCall?.active_call_id ?? null;
  const hasActiveCall = activeCallId !== null && activeCallId > 0;

  useEffect(() => {
    if (activeCall?.case_id) setSelectedCaseId(activeCall.case_id);
  }, [activeCall?.case_id]);

  // ── WebSocket（仅 active 时）────────────────
  const { status: wsStatus, transcript, suggestions, risks, sendFeedback } = useCallSocket({
    callId: activeCallId ?? 0, role: "agent", token,
  });

  // 通话计时
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!hasActiveCall || !activeCall?.started_at) { setElapsed(0); return; }
    const start = new Date(activeCall.started_at).getTime();
    const u = () => setElapsed(Math.max(0, Math.floor((Date.now() - start) / 1000)));
    u(); const id = setInterval(u, 1000); return () => clearInterval(id);
  }, [hasActiveCall, activeCall?.started_at]);

  const selectedCase = useMemo(
    () => selectedCaseId ? caseItems.find((c) => c.id === selectedCaseId) ?? null : null,
    [selectedCaseId, caseItems],
  );

  // v1.6.6 — 选中案件后拉完整 detail（含 project_info / 时间线 / 服务团队）
  const { query: caseDetailQuery } = useOne<CaseDetailResponse>({
    resource: "agent/cases",
    id: selectedCaseId ?? 0,
    queryOptions: { enabled: !!selectedCaseId },
  });
  const caseDetail = caseDetailQuery.data?.data ?? null;

  // ── E4 发送缴费链接 ─────────────────────────────────
  const { mutate: sendPaymentMutate } = useCustomMutation();
  function sendPaymentLink(caseId: number) {
    sendPaymentMutate(
      { url: `agent/cases/${caseId}/send-payment-link`, method: "post", values: {} },
      {
        onSuccess: (resp) => {
          const data = resp.data as { short_link?: string; sent_to?: string };
          alert(`✓ 已发送缴费链接到 ${data.sent_to ?? "业主"}\n短链：${data.short_link ?? "—"}`);
        },
        onError: (err) => alert(`发送失败：${err.message}`),
      },
    );
  }

  // ── 工作台 quick-actions（创建工单 / 标记承诺 / 升级督导）──────
  const { mutate: workOrderMutate } = useCustomMutation();
  const { mutate: stageMutate } = useCustomMutation();
  const { mutate: intentMutate } = useCustomMutation();

  function handleCreateWorkOrder(caseId: number) {
    const description = window.prompt("工单内容（必填）：");
    if (!description?.trim()) return;
    workOrderMutate(
      {
        url: "workorders",
        method: "post",
        values: {
          case_id: caseId,
          order_type: "case_followup",
          description: description.trim(),
          priority: "normal",
        },
      },
      {
        onSuccess: (resp) => alert(`✓ 工单 #${(resp.data as { id?: number }).id ?? "?"} 已创建`),
        onError: (err) => alert(`创建失败：${err.message}`),
      },
    );
  }

  function handleMarkPromised(caseId: number) {
    const note = window.prompt("业主承诺备注（可选，例如：业主承诺月底前缴清）：") ?? "";
    stageMutate(
      {
        url: `agent/cases/${caseId}/stage`,
        method: "patch",
        values: { stage: "promised", note: note.trim() || undefined },
      },
      {
        onSuccess: () => alert("✓ 已标记为承诺缴费"),
        onError: (err) => alert(`标记失败：${err.message}`),
      },
    );
  }

  function handleEscalateSupervisor(caseId: number) {
    const note = window.prompt("升级原因（可选）：") ?? "";
    intentMutate(
      {
        url: `agent/cases/${caseId}/intent`,
        method: "post",
        values: { action: "transfer_supervisor", note: note.trim() || undefined },
      },
      {
        onSuccess: () => alert("✓ 已升级到督导队列"),
        onError: (err) => alert(`升级失败：${err.message}`),
      },
    );
  }

  // v1.6.9 — 申请转法务（写入 LegalConversionRequest，督导/admin 审批）
  function handleRequestTransferLegal(caseId: number) {
    const note = window.prompt("转法务理由（建议简述为何不可能自愿缴）：") ?? "";
    intentMutate(
      {
        url: `agent/cases/${caseId}/intent`,
        method: "post",
        values: { action: "transfer_legal", note: note.trim() || undefined },
      },
      {
        onSuccess: () => alert("✓ 申请转法务已提交，等待督导/admin 审批"),
        onError: (err) => alert(`申请失败：${err.message}`),
      },
    );
  }

  // ── 拨号 ─────────────────────────────────
  const { mutate: dialMutate } = useCreate();
  function requestQr(caseId: number) {
    lastQrCaseId.current = caseId;
    dialMutate(
      { resource: "calls/dial-request", values: { case_id: caseId, mode: "qr" } },
      {
        onSuccess: (resp) => {
          const data = resp.data as { qr_payload?: string; expires_at?: string };
          if (data.qr_payload && data.expires_at) {
            setQrState({ caseId, qrPayload: data.qr_payload, expiresAt: data.expires_at });
          } else {
            alert("拨号请求成功但未返回二维码");
          }
        },
        onError: (err) => alert(`拨号失败：${err.message ?? "未知错误"}`),
      },
    );
  }

  // 当前画像数据源（active call > selectedCase）
  const ownerName = activeCall?.owner_name ?? selectedCase?.owner.name ?? null;
  const ownerPhone = activeCall?.owner_phone_masked ?? selectedCase?.owner.phone_masked ?? null;
  const ownerBuilding = activeCall?.building ?? selectedCase?.owner.building ?? null;
  const ownerRoom = activeCall?.room ?? selectedCase?.owner.room ?? null;
  const ownerAmount = Number((activeCall?.amount_owed ?? selectedCase?.amount_owed) ?? 0);
  const ownerMonths = selectedCase?.months_overdue ?? null;

  // 显示用：转写 + 建议（无 active 时用 demo）
  const displayBubbles = hasActiveCall
    ? transcript.map((t) => ({ speaker: t.speaker as "agent" | "owner" | string, text: t.text, time: fmtTime(t.ts) }))
    : DEMO_TRANSCRIPT;
  const realSuggestions = suggestions.filter((s) => !dismissedSugg.has(s.id));
  const demoSuggestionsFiltered = DEMO_SUGGESTIONS.filter((s) => !dismissedSugg.has(s.id));
  const displayRisks = hasActiveCall ? risks.filter((r) => !dismissedRisk.has(r.risk_id)) : [];

  return (
    <>
      {/* keyframes for animated pills (blink dot, pulse, typing) */}
      <style>{`
        @keyframes ws-blink { 0%,100% { opacity: 1 } 50% { opacity: 0.3 } }
        @keyframes ws-pulse-red { 0%,100% { opacity: 1 } 50% { opacity: 0.55 } }
        @keyframes ws-typing-bounce {
          0%,80%,100% { transform: translateY(0); opacity: 0.4 }
          40% { transform: translateY(-4px); opacity: 1 }
        }
        .ws-blink-dot { animation: ws-blink 1.2s ease-in-out infinite }
        .ws-pulse { animation: ws-pulse-red 1.5s infinite }
        .ws-typing-dot { width:5px; height:5px; background:#1A56DB; border-radius:50%;
          animation: ws-typing-bounce 1.2s ease-in-out infinite }
        .ws-typing-dot:nth-child(2) { animation-delay: .2s }
        .ws-typing-dot:nth-child(3) { animation-delay: .4s }
        .ws-case-card { padding: 11px 12px; border-radius: 6px; cursor: pointer; margin-bottom: 4px;
          border: 1px solid transparent; border-left: 3px solid transparent;
          transition: background .15s, border-color .15s }
        .ws-case-card:hover { background: rgba(255,255,255,0.7); border-color: #d8dfe7 }
        .ws-case-card.active { background: #fff; border-color: #c6d6f0;
          border-left: 3px solid #1A56DB; box-shadow: 0 1px 4px rgba(26,86,219,0.08) }
        .ws-quick-btn { padding: 8px 10px; border-radius: 6px; border: 1px solid #e2e8f0;
          background: #f1f5f9; font-size: 12px; font-weight: 500; color: #374151;
          cursor: pointer; text-align: center; transition: all .15s }
        .ws-quick-btn:hover:not(:disabled) { background: #e2e8f0; border-color: #cbd5e1 }
        .ws-quick-btn:disabled { opacity: 0.45; cursor: not-allowed }
        .ws-quick-btn.danger { color: #dc2626; border-color: #fca5a5; background: #fef2f2 }
        .ws-quick-btn.danger:hover:not(:disabled) { background: #fee2e2 }
        .ws-adopt-btn { background: #f0fdf4; color: #057a55; border: 1px solid #bbf7d0;
          flex: 1; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 500;
          cursor: pointer }
        .ws-adopt-btn:hover { background: #dcfce7 }
        .ws-dismiss-btn { background: #f9fafb; color: #6b7280; border: 1px solid #e5e7eb;
          flex: 1; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 500;
          cursor: pointer }
        .ws-dismiss-btn:hover { background: #f3f4f6 }
        .ws-ctrl-btn { padding: 5px 11px; border-radius: 6px; border: 1px solid #d1d5db;
          background: white; font-size: 12px; color: #374151; cursor: pointer;
          display: inline-flex; align-items: center; gap: 5px }
        .ws-ctrl-btn:hover { background: #f9fafb }
        .ws-hangup-btn { background: #dc2626; color: white; border: none;
          box-shadow: 0 2px 6px rgba(220,38,38,0.35); padding: 5px 11px; border-radius: 6px;
          font-size: 12px; cursor: pointer; display: inline-flex; align-items: center; gap: 5px }
        .ws-hangup-btn:hover { background: #b91c1c }
      `}</style>

      {/* v1.6.7 — E2 今日 KPI 进度条 */}
      {kpi && (
        <div
          data-testid="agent-kpi-bar"
          style={{
            display: "flex", alignItems: "center", gap: 16,
            padding: "10px 16px", marginBottom: 8,
            background: "white", border: "1px solid #e2e8f0", borderRadius: 8,
            fontSize: 13,
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ fontWeight: 600, color: "#374151" }}>
                今日通话进度
              </span>
              <span style={{ fontFamily: "var(--font-mono, monospace)", color: "#1d4ed8", fontWeight: 600 }}>
                {kpi.calls_today} / {kpi.calls_target}
              </span>
            </div>
            <div style={{ height: 6, background: "#f1f5f9", borderRadius: 3, overflow: "hidden" }}>
              <div style={{
                height: "100%",
                width: `${Math.min(100, Math.round((kpi.calls_today / kpi.calls_target) * 100))}%`,
                background: kpi.calls_today >= kpi.calls_target ? "#059669" : "#1A56DB",
                borderRadius: 3,
                transition: "width 0.3s",
              }} />
            </div>
          </div>
          <KpiPill label="接通" value={kpi.connected_today} color="#1d4ed8" />
          <KpiPill label="承诺" value={kpi.promised_today} color="#c2410c" />
          <KpiPill label="缴清" value={kpi.paid_today} color="#15803d" />
          <KpiPill label="通话分钟" value={kpi.minutes_used_today} color="#6b7280" />
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "260px 300px minmax(0, 1fr) 340px",
          height: "calc(100vh - var(--topbar-height, 56px) - 24px - 56px)",
          background: "white",
          border: "1px solid var(--color-neutral-200)",
          borderRadius: 8,
          overflow: "hidden",
        }}
      >
        {/* ═══════════════════════════════════════════
            COL 1 — 案件列表 (浅色)
        ═══════════════════════════════════════════ */}
        <div style={{ display: "flex", flexDirection: "column", background: "#eef2f7",
          borderRight: "1px solid #c9d3de", boxShadow: "2px 0 8px rgba(0,0,0,0.06)", overflow: "hidden" }}>
          <div style={{ padding: 12, borderBottom: "1px solid #dde3ea" }}>
            <div style={{ position: "relative", background: "white", borderRadius: 6, border: "1px solid #d0d7de" }}>
              <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#94a3b8" }} />
              <input
                type="text"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder="搜索业主 / 楼栋..."
                style={{ width: "100%", padding: "7px 10px 7px 34px", background: "transparent",
                  border: "none", borderRadius: 6, color: "#0f172a", fontSize: 13, outline: "none" }}
              />
            </div>
            {/* v1.6.7 — 今日聚合 toggle + 「下一个」按钮 */}
            <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
              <button
                type="button"
                data-testid="ws-today-toggle"
                onClick={() => setTodayMode((v) => !v)}
                style={{
                  flex: 1, padding: "5px 8px", borderRadius: 4, fontSize: 12, fontWeight: 500,
                  cursor: "pointer",
                  border: `1px solid ${todayMode ? "#1A56DB" : "#d0d7de"}`,
                  background: todayMode ? "#1A56DB" : "white",
                  color: todayMode ? "white" : "#475569",
                }}
              >
                {todayMode ? "✓ 今日待联系" : "今日待联系"}
              </button>
              <button
                type="button"
                data-testid="ws-next-case"
                onClick={selectNextCase}
                disabled={filteredCases.length === 0}
                title="跳到下一个案件（提升 KPM）"
                style={{
                  padding: "5px 10px", borderRadius: 4, fontSize: 12, fontWeight: 500,
                  cursor: filteredCases.length === 0 ? "not-allowed" : "pointer",
                  border: "1px solid #d0d7de", background: "white", color: "#1d4ed8",
                  opacity: filteredCases.length === 0 ? 0.5 : 1,
                }}
              >
                下一个 →
              </button>
            </div>
          </div>
          <div style={{ padding: "8px 12px 4px", display: "flex", justifyContent: "space-between",
            alignItems: "center", borderBottom: "1px solid #dde3ea" }}>
            <span style={{ fontSize: 12, color: "#475569" }}>
              共 <strong style={{ color: "#0f172a" }}>{filteredCases.length}</strong> 件
            </span>
            <select
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value)}
              style={{ background: "#f8fafc", border: "1px solid #e2e8f0", color: "#475569",
                fontSize: 12, padding: "3px 6px", borderRadius: 4 }}
            >
              <option value="">全部状态</option>
              <option value="new">待跟进</option>
              <option value="in_progress">跟进中</option>
              <option value="promised">承诺缴费</option>
              <option value="paid">已缴费</option>
              <option value="escalated">升级处理</option>
            </select>
          </div>
          <div style={{ flex: 1, overflowY: "auto", padding: 8 }}>
            {caseListQuery.isLoading && (
              <div style={{ textAlign: "center", color: "#9ca3af", fontSize: 12, padding: 24 }}>加载中…</div>
            )}
            {!caseListQuery.isLoading && filteredCases.length === 0 && (
              <div style={{ textAlign: "center", color: "#9ca3af", fontSize: 12, padding: 24 }}>
                {todayMode ? (
                  <>
                    <div>今日无待联系案件</div>
                    <button
                      type="button"
                      onClick={() => setTodayMode(false)}
                      style={{
                        marginTop: 10,
                        padding: "4px 12px",
                        background: "var(--color-primary, #1A56DB)",
                        color: "white",
                        border: "none",
                        borderRadius: 4,
                        fontSize: 11,
                        cursor: "pointer",
                      }}
                    >
                      查看全部案件
                    </button>
                  </>
                ) : (
                  <div>暂无分配的案件<br /><span style={{ fontSize: 11 }}>试试到「公海池」抢一些案件</span></div>
                )}
              </div>
            )}
            {filteredCases.map((c) => {
              const isActive = selectedCaseId === c.id;
              const isLive = activeCall?.case_id === c.id && hasActiveCall;
              const stage = STAGE_BADGE[c.stage] ?? { label: c.stage, bg: "#f3f4f6", color: "#6b7280" };
              const room = c.owner.building && c.owner.room
                ? `${c.owner.building}${c.owner.room}`
                : c.owner.building ?? c.owner.room ?? "—";
              return (
                <div
                  key={c.id}
                  className={`ws-case-card ${isActive ? "active" : ""}`}
                  onClick={() => setSelectedCaseId(c.id)}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 5 }}>
                    <span style={{ fontSize: 13.5, fontWeight: 600, color: "#0f172a" }}>{c.owner.name}</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: "#dc2626" }}>
                      {c.amount_owed ? `¥${Number(c.amount_owed).toLocaleString()}` : "—"}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: "#475569", marginBottom: 5 }}>{room}</div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: 12, color: "#475569", fontFamily: "var(--font-mono, monospace)" }}>
                      {c.owner.phone_masked}
                    </span>
                    {isLive ? (
                      <span style={{ fontSize: 10.5, fontWeight: 600, padding: "1px 8px",
                        borderRadius: 10, background: "#fef2f2", color: "#b91c1c" }}>
                        通话中
                      </span>
                    ) : (
                      <span style={{ fontSize: 10.5, fontWeight: 600, padding: "1px 8px",
                        borderRadius: 10, background: stage.bg, color: stage.color }}>
                        {stage.label}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>


        {/* ═══════════════════════════════════════════
            COL 2 — 业主画像 + 项目情况 + 沟通时间线（compact 模式）
        ═══════════════════════════════════════════ */}
        <div style={{
          display: "flex", flexDirection: "column",
          background: "#f7f9fc", borderRight: "1px solid #e8ecf1",
          overflowY: "auto",
        }}>
          {!selectedCaseId ? (
            <div style={{ padding: 24, textAlign: "center", color: "#9ca3af", fontSize: 13 }}>
              请从左列选择业主
            </div>
          ) : caseDetailQuery.isLoading || !caseDetail ? (
            <div style={{ padding: 24, textAlign: "center", color: "#9ca3af", fontSize: 13 }}>
              加载中…
            </div>
          ) : (
            <div style={{ padding: 12 }}>
              {/* v1.8.0 — workstation 模式：业主画像内含 3 统计卡片 + 欠款月份 + 最近通话 accordion */}
              <OwnerInfoCard detail={caseDetail} mode="workstation" />
              <ProjectInfoCard detail={caseDetail} compact />
            </div>
          )}
        </div>

        {/* ═══════════════════════════════════════════
            COL 3 — 通话转写
        ═══════════════════════════════════════════ */}
        <div style={{ display: "flex", flexDirection: "column", background: "white",
          overflow: "hidden", position: "relative" }}>
          {/* call-control-bar */}
          <div style={{
            background: "white", borderBottom: "1px solid #e8ecf1",
            padding: "12px 16px", display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
          }}>
            <div style={{
              width: 38, height: 38, borderRadius: "50%",
              background: "var(--color-primary, #1A56DB)", color: "white",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 15, fontWeight: 700, flexShrink: 0,
            }}>
              {(ownerName ?? "?").slice(0, 1)}
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#0f172a" }}>
                {ownerName ?? "—"}
              </div>
              <div style={{ fontSize: 12, color: "#475569" }}>
                {ownerBuilding ?? ""}{ownerRoom ? ` · ${ownerRoom}` : ""}
                {ownerPhone ? ` · ${ownerPhone}` : ""}
              </div>
            </div>

            {/* duration pill (animated dot) */}
            <div style={{
              background: "#eff6ff", color: "#1d4ed8", border: "1px solid #bfdbfe",
              borderRadius: 20, fontSize: 13, fontWeight: 600,
              fontFamily: "var(--font-mono, monospace)",
              padding: "3px 10px", display: "flex", alignItems: "center", gap: 5,
            }}>
              <span className={hasActiveCall ? "ws-blink-dot" : ""} style={{
                width: 7, height: 7, borderRadius: "50%",
                background: hasActiveCall ? "#3b82f6" : "#cbd5e1", display: "inline-block",
              }} />
              {hasActiveCall ? fmtDuration(elapsed) : "00:00"}
            </div>

            {/* recording mode badge */}
            <div title="当前录音模式" style={{
              display: "inline-flex", alignItems: "center", gap: 4,
              padding: "3px 9px", borderRadius: 20,
              fontSize: 11.5, fontWeight: 600,
              background: hasActiveCall ? "#f0fdf4" : "#f3f4f6",
              color: hasActiveCall ? "#057a55" : "#6b7280",
              border: `1px solid ${hasActiveCall ? "#bbf7d0" : "#e5e7eb"}`,
            }}>
              <span className={hasActiveCall ? "ws-blink-dot" : ""} style={{
                width: 7, height: 7, borderRadius: "50%",
                background: hasActiveCall ? "#059669" : "#9ca3af", display: "inline-block",
              }} />
              {hasActiveCall ? "实时推流" : "待机"}
            </div>

            {/* network badge */}
            <div title="网络质量" style={{
              display: "inline-flex", alignItems: "center", gap: 4,
              padding: "3px 9px", borderRadius: 20,
              fontSize: 11.5, border: "1px solid #e2e8f0", background: "#f8fafc",
            }}>
              <SignalBars quality={hasActiveCall ? "good" : "fair"} />
              <span style={{ fontSize: 11, color: hasActiveCall ? "#059669" : "#92400e", fontWeight: 600 }}>
                {hasActiveCall ? (wsStatus === "connected" ? "良好" : wsStatus) : "待机"}
              </span>
            </div>

            {/* actions — v1.6.9：通话中显示 静音/暂停/挂断；未通话显示「扫码到 App 拨号」大按钮 */}
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
              {hasActiveCall ? (
                <>
                  <button type="button" className="ws-ctrl-btn"
                    onClick={() => setMuted((v) => !v)}>
                    {muted ? <MicOff size={13} /> : <Mic size={13} />}
                    {muted ? "取消静音" : "静音"}
                  </button>
                  <button type="button" className="ws-ctrl-btn">
                    <PauseCircle size={13} /> 暂停
                  </button>
                  <button type="button" className="ws-hangup-btn">
                    <PhoneOff size={13} /> 挂断
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  data-testid="ws-dial-top"
                  onClick={() => selectedCaseId && requestQr(selectedCaseId)}
                  disabled={!selectedCaseId || (caseDetail?.owner.do_not_call ?? false)}
                  title={
                    !selectedCaseId
                      ? "请先选择业主"
                      : caseDetail?.owner.do_not_call
                        ? "业主已加入免打扰"
                        : "扫码到 App 拨号 → App 上完成通话，转写实时回传 PC"
                  }
                  style={{
                    padding: "8px 16px",
                    background: !selectedCaseId || (caseDetail?.owner.do_not_call ?? false)
                      ? "#e5e7eb"
                      : "var(--color-primary, #1A56DB)",
                    color: !selectedCaseId || (caseDetail?.owner.do_not_call ?? false)
                      ? "#9ca3af"
                      : "white",
                    border: "none",
                    borderRadius: 6,
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: !selectedCaseId || (caseDetail?.owner.do_not_call ?? false)
                      ? "not-allowed"
                      : "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <Phone size={14} />
                  {caseDetail?.owner.do_not_call ? "业主免打扰" : "扫码到 App 拨号"}
                </button>
              )}
            </div>
          </div>

          {/* transcript area */}
          <div style={{ flex: 1, overflowY: "auto", padding: 16,
            display: "flex", flexDirection: "column", gap: 12,
            background: hasActiveCall ? "white" : "#fcfcfd" }}>
            {!hasActiveCall && (
              <div style={{ textAlign: "center", marginBottom: 4 }}>
                <span style={{
                  fontSize: 11.5, color: "#9ca3af", background: "#f1f5f9",
                  padding: "3px 12px", borderRadius: 20, border: "1px solid #e2e8f0",
                }}>
                  📞 等待 App 拨号 · 以下为示例对话
                </span>
              </div>
            )}
            {hasActiveCall && displayBubbles.length === 0 && (
              <div style={{ textAlign: "center", marginBottom: 4 }}>
                <span style={{
                  fontSize: 11.5, color: "#9ca3af", background: "#f1f5f9",
                  padding: "3px 12px", borderRadius: 20, border: "1px solid #e2e8f0",
                }}>
                  通话开始 {fmtTime(activeCall?.started_at)}
                </span>
              </div>
            )}
            {displayBubbles.map((b, idx) => {
              const isAgent = b.speaker === "agent";
              return (
                <div key={idx} style={{
                  display: "flex", alignItems: "flex-end", gap: 8,
                  flexDirection: isAgent ? "row-reverse" : "row",
                }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: "50%",
                    background: isAgent ? "var(--color-primary, #1A56DB)" : "#94a3b8",
                    color: "white", fontSize: 11, fontWeight: 600,
                    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                  }}>
                    {isAgent ? "我" : (ownerName ?? "?").slice(0, 1)}
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 3,
                      textAlign: isAgent ? "right" : "left" }}>
                      {isAgent ? "催收员" : (ownerName ?? "业主")}
                    </div>
                    <div style={{
                      maxWidth: 480, padding: "10px 14px", borderRadius: 14,
                      fontSize: 14, lineHeight: 1.55, position: "relative",
                      background: isAgent ? "#EFF6FF" : "#F1F5F9",
                      border: isAgent ? "1px solid #BFDBFE" : "1px solid #E2E8F0",
                      color: isAgent ? "#1e3a5f" : "#334155",
                      borderBottomRightRadius: isAgent ? 4 : 14,
                      borderBottomLeftRadius: isAgent ? 14 : 4,
                    }}>
                      {b.text}
                    </div>
                    <div style={{ fontSize: 11.5, color: "#9ca3af", marginTop: 3,
                      fontFamily: "var(--font-mono, monospace)",
                      textAlign: isAgent ? "right" : "left" }}>
                      {b.time}
                    </div>
                  </div>
                </div>
              );
            })}

            {hasActiveCall && (
              <div style={{ display: "flex", alignItems: "center", gap: 8,
                padding: "8px 14px", background: "white", borderRadius: 14,
                border: "1px solid #e5e7eb", width: "fit-content",
                fontSize: 12.5, color: "#475569",
              }}>
                AI 正在分析...
                <div style={{ display: "flex", gap: 3 }}>
                  <span className="ws-typing-dot" />
                  <span className="ws-typing-dot" />
                  <span className="ws-typing-dot" />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ═══════════════════════════════════════════
            COL 4 — AI 实时建议
        ═══════════════════════════════════════════ */}
        <div style={{ display: "flex", flexDirection: "column",
          borderLeft: "1px solid #e2e8f0", background: "#f7f9fc", overflow: "hidden" }}>
          {/* ai scrollable body */}
          <div style={{ flex: 1, overflowY: "auto", padding: "14px 16px" }}>
            {/* AI Header */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
              <div style={{ fontSize: 13.5, fontWeight: 700, color: "#0f172a",
                display: "flex", alignItems: "center", gap: 6 }}>
                🤖 AI 实时建议
              </div>
              <div style={{
                display: "inline-flex", alignItems: "center", gap: 3,
                padding: "2px 8px", borderRadius: 20, fontSize: 11, fontWeight: 600,
                background: "#f0fdf4", color: "#057a55",
              }}>
                ● {hasActiveCall ? "高置信度" : "示例数据"}
              </div>
            </div>

            {/* call context */}
            <div style={{
              background: "#f0f9ff", borderRadius: 6, padding: "8px 12px", marginBottom: 12,
              fontSize: 12.5, color: "#0369a1", border: "1px solid #bfdbfe",
            }}>
              <div style={{ fontWeight: 600, marginBottom: 2 }}>📋 本次通话背景</div>
              <div>
                {ownerAmount > 0 ? `欠费 ¥${ownerAmount.toLocaleString()}` : "未选中案件"}
                {ownerMonths ? `（${ownerMonths} 个月）` : ""}
                {" · 历史通话 3 次 · 上次：04-20"}
              </div>
            </div>

            {/* L1 risk bar (demo or real) */}
            {hasActiveCall ? (
              displayRisks.slice(0, 2).map((r) => (
                <div key={r.risk_id} className={r.level === "L2" ? "ws-pulse" : ""}
                  style={{
                    borderRadius: 6, padding: "7px 10px", marginBottom: 8,
                    fontSize: 12.5, display: "flex", alignItems: "center", gap: 6,
                    background: r.level === "L2" ? "#fef2f2" : "#fffbeb",
                    border: `1px solid ${r.level === "L2" ? "#fca5a5" : "#fde68a"}`,
                    color: r.level === "L2" ? "#991b1b" : "#92400e",
                  }}>
                  <span>
                    {r.level === "L2" ? "🔴" : "⚠️"} {r.level} 检测到 "{r.matched_keywords.join("、")}"
                  </span>
                  <button
                    type="button"
                    onClick={() => setDismissedRisk((s) => new Set([...s, r.risk_id]))}
                    style={{ marginLeft: "auto", cursor: "pointer", opacity: 0.6,
                      fontSize: 15, lineHeight: 1, background: "none", border: "none", padding: "0 2px" }}
                  >×</button>
                </div>
              ))
            ) : (
              <div style={{
                borderRadius: 6, padding: "7px 10px", marginBottom: 8,
                fontSize: 12.5, display: "flex", alignItems: "center", gap: 6,
                background: "#fffbeb", border: "1px solid #fde68a", color: "#92400e",
              }}>
                <span>⚠️ L1 检测到"不想交"情绪词，建议平复情绪</span>
                <button type="button" style={{
                  marginLeft: "auto", cursor: "pointer", opacity: 0.6, fontSize: 15,
                  lineHeight: 1, background: "none", border: "none", padding: "0 2px",
                }}>×</button>
              </div>
            )}

            {/* suggestion cards */}
            {!hasActiveCall ? (
              demoSuggestionsFiltered.map((s) => (
                <SuggCard
                  key={s.id}
                  type={s.type}
                  typeLabel={s.typeLabel}
                  title={s.title}
                  body={s.body}
                  trigger={s.trigger}
                  confidence={s.confidence}
                  onAdopt={() => setDismissedSugg((set) => new Set([...set, s.id]))}
                  onDismiss={() => setDismissedSugg((set) => new Set([...set, s.id]))}
                />
              ))
            ) : realSuggestions.length === 0 ? (
              <div style={{ textAlign: "center", color: "#94a3b8", fontSize: 12, padding: 20 }}>
                AI 正在分析对话...
              </div>
            ) : (
              realSuggestions.map((s) => (
                <SuggCard
                  key={s.id}
                  type="script"
                  typeLabel={`📋 ${s.intent ?? "话术建议"}`}
                  title={s.intent ?? "AI 建议"}
                  body={s.text}
                  trigger=""
                  confidence={typeof s.confidence === "number" ? Math.round(s.confidence * 100) : 0}
                  onAdopt={() => { sendFeedback(s.id, "adopt"); setDismissedSugg((set) => new Set([...set, s.id])); }}
                  onDismiss={() => { sendFeedback(s.id, "ignore"); setDismissedSugg((set) => new Set([...set, s.id])); }}
                />
              ))
            )}
          </div>

          {/* quick actions bar — v1.6.9 扩到 6 按钮（加 申请减免 / 申请转法务）
              通话中 + 通话结束后均可点；selectedCaseId 控制 enable */}
          <div style={{
            flexShrink: 0, background: "white", borderTop: "1px solid #e2e8f0",
            padding: "10px 16px", minHeight: 52,
          }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 7 }}>
              <button
                type="button"
                className="ws-quick-btn"
                disabled={!selectedCaseId}
                data-testid="ws-send-payment-link"
                onClick={() => selectedCaseId && sendPaymentLink(selectedCaseId)}
                title="生成 H5 缴费短链 + 短信下发"
              >
                📱 发送缴费链接
              </button>
              <button
                type="button"
                className="ws-quick-btn"
                disabled={!selectedCaseId}
                onClick={() => selectedCaseId && handleCreateWorkOrder(selectedCaseId)}
              >
                🔧 创建工单
              </button>
              <button
                type="button"
                className="ws-quick-btn"
                disabled={!selectedCaseId}
                onClick={() => selectedCaseId && handleMarkPromised(selectedCaseId)}
              >
                ✅ 标记承诺缴费
              </button>
              <button
                type="button"
                className="ws-quick-btn"
                disabled={!selectedCaseId}
                data-testid="ws-discount-request"
                onClick={() => selectedCaseId && setDiscountForCaseId(selectedCaseId)}
                title="发起减免/分期/违约金减免，督导或 admin 审批"
              >
                💸 申请减免
              </button>
              <button
                type="button"
                className="ws-quick-btn"
                disabled={!selectedCaseId}
                data-testid="ws-transfer-legal"
                onClick={() => selectedCaseId && handleRequestTransferLegal(selectedCaseId)}
                title="申请转法务，督导/admin 审批后真正建单"
              >
                ⚖️ 申请转法务
              </button>
              <button
                type="button"
                className="ws-quick-btn danger"
                disabled={!selectedCaseId}
                onClick={() => selectedCaseId && handleEscalateSupervisor(selectedCaseId)}
              >
                🔺 升级督导
              </button>
            </div>
          </div>
        </div>
      </div>

      {qrState && (
        <QrDialDialog
          qrPayload={qrState.qrPayload}
          expiresAt={qrState.expiresAt}
          onClose={() => setQrState(null)}
          onRegenerate={() => requestQr(qrState.caseId)}
        />
      )}

      {discountForCaseId && (
        <DiscountRequestModal
          caseId={discountForCaseId}
          originalAmount={
            // 优先 active call 的金额；否则取选中案件
            ownerAmount > 0 ? ownerAmount : null
          }
          ownerName={ownerName}
          onClose={() => setDiscountForCaseId(null)}
          onSuccess={(offerId) => {
            setDiscountForCaseId(null);
            alert(`✓ 减免申请 #${offerId} 已提交，等待审批`);
          }}
        />
      )}
    </>
  );
}

// ── 子组件 ─────────────────────────────────
function KpiPill({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ textAlign: "center", padding: "0 8px", borderLeft: "1px solid #f1f5f9" }}>
      <div style={{ fontSize: 11, color: "#64748b" }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 700, color, fontFamily: "var(--font-mono, monospace)" }}>
        {value}
      </div>
    </div>
  );
}

function SignalBars({ quality }: { quality: "good" | "fair" | "poor" }) {
  const heights = [4, 7, 10, 13];
  const colors = quality === "good"
    ? ["#059669", "#059669", "#059669", "#059669"]
    : quality === "fair"
    ? ["#d97706", "#d97706", "#d1d5db", "#d1d5db"]
    : ["#dc2626", "#d1d5db", "#d1d5db", "#d1d5db"];
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 14 }}>
      {heights.map((h, i) => (
        <span key={i} style={{ width: 3, height: h, borderRadius: 1, background: colors[i] }} />
      ))}
    </div>
  );
}

function SuggCard({ type, typeLabel, title, body, trigger, confidence, onAdopt, onDismiss }: {
  type: "objection" | "script" | "risk";
  typeLabel: string;
  title: string;
  body: string;
  trigger: string;
  confidence: number;
  onAdopt: () => void;
  onDismiss: () => void;
}) {
  const cs = CARD_STYLE[type];
  return (
    <div style={{
      border: "1px solid #e2e8f0",
      borderLeft: `3px solid ${cs.border}`,
      background: cs.bg,
      borderRadius: 6, padding: 12, marginBottom: 10,
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 5 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: "#475569",
          textTransform: "uppercase", letterSpacing: "0.4px" }}>
          {typeLabel}
        </div>
        <span style={{
          background: "#eff6ff", color: "#1d4ed8",
          borderRadius: 20, padding: "1px 6px", fontSize: 11, fontWeight: 700,
        }}>
          置信度 {confidence}%
        </span>
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color: "#0f172a", marginBottom: 6 }}>{title}</div>
      <div style={{ fontSize: 12.5, color: "#374151", lineHeight: 1.6, marginBottom: 6 }}>{body}</div>
      {trigger && (
        <div style={{ marginBottom: 8 }}>
          <span style={{
            display: "inline-flex", alignItems: "center", gap: 3,
            background: "#fff7ed", color: "#c2410c", border: "1px solid #fed7aa",
            borderRadius: 4, fontSize: 11.5, padding: "2px 7px",
          }}>
            触发词："{trigger}"
          </span>
        </div>
      )}
      <div style={{ display: "flex", gap: 6 }}>
        <button type="button" className="ws-adopt-btn" onClick={onAdopt}>✓ 采纳</button>
        <button type="button" className="ws-dismiss-btn" onClick={onDismiss}>✗ 忽略</button>
      </div>
    </div>
  );
}
