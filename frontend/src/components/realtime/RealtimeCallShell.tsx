// frontend/src/components/realtime/RealtimeCallShell.tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, ClipboardList, CreditCard, Headphones, X } from "lucide-react";
import { useCallSocket } from "../../hooks/useCallSocket";
import type { RiskEvent } from "../../lib/realtime/types";
import { postSuggestionFeedback } from "../../lib/realtime/feedback-api";
import { ConnectionBadge } from "./ConnectionBadge";
import { TranscriptStream } from "./TranscriptStream";
import { SuggestionCardStack } from "./SuggestionCardStack";

const CAT_LABELS: Record<string, string> = {
  owner_abuse: "业主辱骂",
  owner_threat: "业主威胁",
  agent_violation: "催收员违规",
  agent_minor_misconduct: "轻微不当",
};

interface RiskBannerProps {
  risk: RiskEvent;
  onDismiss: (id: string) => void;
}

function RiskBanner({ risk, onDismiss }: RiskBannerProps) {
  const isL2 = risk.level === "L2";
  return (
    <div
      className={`flex items-start gap-2 rounded-md border px-3 py-2 text-sm ${
        isL2
          ? "bg-red-50 border-red-200 text-red-700"
          : "bg-yellow-50 border-yellow-200 text-yellow-700"
      }`}
    >
      <AlertTriangle className={`w-4 h-4 mt-0.5 shrink-0 ${isL2 ? "text-red-500" : "text-yellow-500"}`} />
      <div className="flex-1 min-w-0">
        <div className={`font-semibold ${isL2 ? "" : "font-medium"}`}>
          {isL2 ? "⛔ 高风险" : "⚠ 轻微提示"} · {CAT_LABELS[risk.category] ?? risk.category}
        </div>
        {risk.matched_keywords.length > 0 && (
          <div className="text-xs mt-0.5 opacity-80">
            关键词：{risk.matched_keywords.join("、")}
          </div>
        )}
        <button
          type="button"
          className="text-xs underline mt-0.5 opacity-70 hover:opacity-100"
          onClick={() => console.log("查看详情 — v1.1 上线", risk.risk_id)}
        >
          查看详情
        </button>
      </div>
      <button
        type="button"
        aria-label="关闭"
        onClick={() => onDismiss(risk.risk_id)}
        className="shrink-0 opacity-60 hover:opacity-100"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

interface OwnerSummary {
  name: string;
  building?: string;
  room?: string;
  amount_owed?: string;
}

interface Props {
  callId: number;
  role: "agent" | "observer";
  token: string;
  owner: OwnerSummary | null;
}

export function RealtimeCallShell({ callId, role, token, owner }: Props) {
  const navigate = useNavigate();
  const { status, transcript, suggestions, tag, risks, sendFeedback } = useCallSocket({ callId, role, token });
  const [elapsed, setElapsed] = useState(0);
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());

  const visibleRisks = risks.filter((r) => !dismissedIds.has(r.risk_id)).slice(-3);

  const handleDismiss = (id: string) => {
    setDismissedIds((prev) => new Set([...prev, id]));
  };

  useEffect(() => {
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (tag !== null) {
      // Server confirmed final analysis — jump to call detail
      const timeout = setTimeout(() => navigate(`/calls/${callId}`), 800);
      return () => clearTimeout(timeout);
    }
  }, [tag, callId, navigate]);

  const handleFeedback = (id: string, action: "adopt" | "ignore") => {
    sendFeedback(id, action);  // WS ack for instant UX
    void postSuggestionFeedback(callId, id, action, token);  // durable
  };

  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <header className="flex items-center justify-between rounded-lg bg-white px-4 py-2 shadow-sm">
        <div className="font-mono text-lg text-slate-700">通话 {mm}:{ss}</div>
        <ConnectionBadge status={status} />
        {role === "observer" ? (
          <span className="text-sm text-slate-500">正在旁听</span>
        ) : (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => alert("建工单功能将在 v1.1 上线")}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-md border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors"
            >
              <ClipboardList className="w-3.5 h-3.5" />
              建工单
            </button>
            <button
              type="button"
              onClick={() => alert("发支付码功能将在 v1.1 上线")}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-md border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors"
            >
              <CreditCard className="w-3.5 h-3.5" />
              发支付码
            </button>
            <button
              type="button"
              onClick={() => alert("转接督导功能将在 v1.1 上线")}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-md border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors"
            >
              <Headphones className="w-3.5 h-3.5" />
              转接督导
            </button>
          </div>
        )}
      </header>

      {/* 列宽对齐 ui/agent-pc.html 4 栏 grid（240 1fr 340 — AppLayout sidebar 充当第 1 栏 280px） */}
      <div className="grid flex-1 gap-4" style={{ gridTemplateColumns: "240px 1fr 340px" }}>
        <aside className="rounded-lg bg-white p-4 shadow-sm">
          {owner ? (
            <>
              <div className="text-xl font-semibold">{owner.name}</div>
              <div className="mt-1 text-sm text-slate-500">
                {owner.building} {owner.room}
              </div>
              {owner.amount_owed && (
                <div className="mt-3 text-base text-rose-600">
                  欠费 ¥{owner.amount_owed}
                </div>
              )}
            </>
          ) : (
            <div className="text-sm text-slate-400">加载业主信息中…</div>
          )}
        </aside>

        <TranscriptStream chunks={transcript} />

        <aside className="flex flex-col gap-3">
          <SuggestionCardStack
            suggestions={suggestions}
            onFeedback={handleFeedback}
            readOnly={role === "observer"}
          />
          {visibleRisks.length > 0 && (
            <div className="space-y-2">
              {visibleRisks.map((r) => (
                <RiskBanner key={r.risk_id} risk={r} onDismiss={handleDismiss} />
              ))}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
