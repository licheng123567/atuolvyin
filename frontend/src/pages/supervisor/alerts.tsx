import { AlertTriangle } from "lucide-react";
import { useSupervisorAlertStore } from "../../store/supervisor-alerts";
import { useGo } from "@refinedev/core";

const CAT_LABELS: Record<string, string> = {
  owner_abuse: "业主辱骂",
  owner_threat: "业主威胁",
  agent_violation: "催收员违规",
  agent_minor_misconduct: "轻微不当",
};

export function SupervisorAlertsPage() {
  const alerts = useSupervisorAlertStore((s) => s.alerts);
  const markRead = useSupervisorAlertStore((s) => s.markRead);
  const clearAll = useSupervisorAlertStore((s) => s.clearAll);
  const go = useGo();

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-red-600" />
          <h1 className="text-xl font-semibold text-neutral-900">风控告警列表</h1>
          <span className="text-sm text-neutral-400 ml-1">共 {alerts.length} 条</span>
        </div>
        {alerts.length > 0 && (
          <button
            type="button"
            onClick={clearAll}
            className="text-sm text-neutral-500 hover:text-red-600"
          >
            清空
          </button>
        )}
      </div>

      {alerts.length === 0 ? (
        <div className="text-center py-16 text-neutral-400">暂无风控告警</div>
      ) : (
        <div className="rounded-md border border-neutral-200 divide-y divide-neutral-100 bg-white">
          {alerts.map((a) => (
            <div
              key={a.risk_id}
              className={`flex items-start gap-3 px-4 py-3 cursor-pointer hover:bg-neutral-50 ${!a.read ? "bg-red-50" : ""}`}
              onClick={() => {
                markRead(a.risk_id);
                go({ to: `/calls/${a.call_id}` });
              }}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                      a.level === "L2"
                        ? "bg-red-100 text-red-700"
                        : "bg-orange-100 text-orange-700"
                    }`}
                  >
                    {a.level}
                  </span>
                  <span className="text-sm font-medium text-neutral-800">
                    {CAT_LABELS[a.category] ?? a.category}
                  </span>
                  <span className="text-xs text-neutral-400">
                    {a.agent_name} · 案件#{a.case_id}
                  </span>
                  {!a.read && (
                    <span className="ml-auto w-2 h-2 rounded-full bg-red-600 flex-shrink-0" />
                  )}
                </div>
                <p className="text-xs text-neutral-600 truncate">
                  触发方式：{a.trigger}
                  {a.llm_confidence > 0
                    ? ` · 置信度 ${(a.llm_confidence * 100).toFixed(0)}%`
                    : ""}
                </p>
                <p className="text-xs text-neutral-500 mt-0.5">「{a.text_snippet}」</p>
              </div>
              <span className="text-xs text-neutral-400 whitespace-nowrap flex-shrink-0">
                {new Date(a.ts).toLocaleTimeString("zh-CN")}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
