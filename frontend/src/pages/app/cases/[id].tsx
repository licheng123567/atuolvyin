// v2.0 Task 4 — Screen 6：案件详情（Android WebView）
// 1:1 对齐 ui/app-agent.html#app-case-detail
// 数据源：GET /api/v1/agent/cases/{id}
import { useOne } from "@refinedev/core";
import { useNavigate, useParams } from "react-router-dom";
import { ChevronLeft, FileText, Phone } from "lucide-react";
import { dialCase } from "./_dial";
import { stageBadgeClass, stageLabel, resultTagBadge } from "../../../lib/caseStage";
import {
  formatDurationChinese,
  formatShortDateTime,
  relativeTimeChinese,
} from "../../../lib/datetime";
import { MobileTimelineCard } from "../../../components/mobile/MobileTimelineCard";

interface OwnerInfo {
  id: number;
  name: string;
  phone?: string | null;
  phone_masked: string;
  building: string | null;
  room: string | null;
  do_not_call: boolean;
}

interface CaseCallItem {
  id: number;
  started_at: string | null;
  duration_sec: number | null;
  status: string;
  transcript_preview: string | null;
  result_tag: string | null;
  confidence: number | null;
  agent_name: string | null;
  recording_url?: string | null;
}

interface TimelineEvent {
  type: string;
  ts: string;
  actor: string | null;
  note: string | null;
  target_id?: number | null;
  target_type?: string | null;
}

interface CaseDetail {
  id: number;
  tenant_id: number;
  project_id: number | null;
  project_name: string | null;
  owner: OwnerInfo;
  assigned_to: number | null;
  pool_type: string;
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
  priority_score: number;
  last_contact_at: string | null;
  monthly_contact_count: number;
  promise_count: number;
  workorder_count: number;
  status: string;
  created_at: string;
  updated_at: string;
  calls: CaseCallItem[];
  timeline_events: TimelineEvent[];
}

function formatYuan(value: string | null | undefined): string {
  if (!value) return "¥0";
  const n = Number(value);
  if (!Number.isFinite(n)) return `¥${value}`;
  return `¥${n.toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`;
}

export function MobileCaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const caseId = id ? Number(id) : NaN;

  const { query } = useOne<CaseDetail>({
    resource: "agent/cases",
    id: id ?? "",
    queryOptions: { enabled: !!id && Number.isFinite(caseId) },
  });
  const detail = query.data?.data;
  const isLoading = query.isLoading;

  const handleBack = () => {
    // Bridge 暂未支持 finish；浏览器和 Android WebView 都先走 history.back()
    // TODO Task 8: Bridge.closeWebViewPush() 关闭独立 push WebView
    if (window.history.length > 1) {
      window.history.back();
    } else {
      navigate("/app/cases");
    }
  };

  const handleDial = () => {
    if (!detail) return;
    dialCase(detail);
  };

  const handleAddNote = () => {
    if (!detail) return;
    // TODO Task 6+: 接 POST /api/v1/agent/cases/{id}/notes（暂未实现）
    const note = window.prompt(`为「${detail.owner.name}」添加跟进备注：`, "");
    if (note && note.trim().length > 0) {
      window.alert("✓ 已记录（PoC：暂存本地，未上送服务端）");
    }
  };

  if (isLoading) {
    return (
      <div className="detail-screen">
        <div style={{ padding: 32, textAlign: "center", color: "#9ca3af" }}>
          加载中…
        </div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="detail-screen">
        <div className="detail-top-bar">
          <span className="back-btn" onClick={handleBack}>
            <ChevronLeft size={20} aria-hidden />
          </span>
          <div className="detail-owner-name">案件不存在</div>
        </div>
        <div style={{ padding: 32, textAlign: "center", color: "#E02424", fontSize: 13 }}>
          案件不存在或无权访问
        </div>
      </div>
    );
  }

  // 通话按时间倒序
  const sortedCalls: CaseCallItem[] = [...detail.calls].sort((a, b) => {
    const ta = a.started_at ? new Date(a.started_at).getTime() : 0;
    const tb = b.started_at ? new Date(b.started_at).getTime() : 0;
    return tb - ta;
  });

  return (
    <div className="detail-screen">
      {/* ── 顶部 bar ── */}
      <div className="detail-top-bar">
        <span
          className="back-btn"
          onClick={handleBack}
          style={{ display: "inline-flex", alignItems: "center" }}
        >
          <ChevronLeft size={20} aria-hidden />
        </span>
        <div className="detail-owner-name">{detail.owner.name}</div>
        <span
          className={stageBadgeClass(detail.stage)}
          style={{ marginLeft: "auto" }}
        >
          {stageLabel(detail.stage)}
        </span>
      </div>

      {/* ── 3 列信息卡（颜色对齐原型：欠费红 / 月数橙 / 联系灰小字） ── */}
      <div className="detail-info-cards">
        <div className="detail-info-card">
          <div className="detail-info-card-value">
            {formatYuan(detail.amount_owed)}
          </div>
          <div className="detail-info-card-label">欠费金额</div>
        </div>
        <div className="detail-info-card">
          <div
            className="detail-info-card-value"
            style={{ fontSize: 16, color: "#D97706" }}
          >
            {detail.months_overdue ? `${detail.months_overdue}个月` : "—"}
          </div>
          <div className="detail-info-card-label">欠费月数</div>
        </div>
        <div className="detail-info-card">
          <div
            className="detail-info-card-value"
            style={{ fontSize: 13, color: "#374151", fontWeight: 600 }}
          >
            {relativeTimeChinese(detail.last_contact_at)}
          </div>
          <div className="detail-info-card-label">最近联系</div>
        </div>
      </div>

      {/* ── 通话记录时间线 ── */}
      <div className="timeline-wrap">
        <div className="app-section-title" style={{ marginBottom: 10 }}>
          通话记录
        </div>
        {sortedCalls.length === 0 && (
          <div
            style={{
              background: "white",
              padding: 16,
              borderRadius: 10,
              textAlign: "center",
              color: "#9ca3af",
              fontSize: 13,
            }}
          >
            暂无通话记录
          </div>
        )}
        {sortedCalls.map((call) => (
          <MobileTimelineCard
            key={call.id}
            date={formatShortDateTime(call.started_at)}
            durationText={formatDurationChinese(call.duration_sec)}
            resultBadge={resultTagBadge(call.result_tag)}
            // backend CaseCallItem 没有 summary 字段；用 transcript_preview 代替
            aiSummary={call.transcript_preview}
          />
        ))}
      </div>

      {/* ── 底部固定按钮区 ── */}
      <div style={{ padding: 16, paddingBottom: 86 /* 留 70 给 tab bar + 16 间距 */ }}>
        <button
          type="button"
          className="big-btn"
          style={{
            margin: "0 0 8px",
            width: "100%",
            borderRadius: 10,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
          }}
          onClick={handleDial}
          disabled={detail.owner.do_not_call}
          title={detail.owner.do_not_call ? "业主已加入免打扰" : "发起外呼"}
        >
          <Phone size={16} strokeWidth={2} aria-hidden />
          {detail.owner.do_not_call ? "业主免打扰" : "发起外呼"}
        </button>
        <button
          type="button"
          onClick={handleAddNote}
          style={{
            width: "100%",
            padding: 12,
            border: "1px solid #d1d5db",
            borderRadius: 10,
            background: "white",
            fontSize: 14,
            color: "#374151",
            cursor: "pointer",
            fontFamily: "var(--font-sans)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
          }}
        >
          <FileText size={16} strokeWidth={2} aria-hidden />
          添加备注
        </button>
      </div>
    </div>
  );
}

export default MobileCaseDetailPage;
