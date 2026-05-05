import { Bell } from "lucide-react";
import { useState } from "react";
import { useGo } from "@refinedev/core";
import { useSupervisorAlertStore } from "../../store/supervisor-alerts";

export function AlertNotificationCenter() {
  const unreadCount = useSupervisorAlertStore((s) => s.unreadCount);
  const alerts = useSupervisorAlertStore((s) => s.alerts);
  const markRead = useSupervisorAlertStore((s) => s.markRead);
  const [open, setOpen] = useState(false);
  const go = useGo();

  const catLabel = (cat: string) =>
    ({
      owner_abuse: "业主辱骂",
      owner_threat: "业主威胁",
      agent_violation: "催收员违规",
      agent_minor_misconduct: "轻微不当",
    }[cat] ?? cat);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="relative p-2 rounded-md hover:bg-neutral-100"
        aria-label="风控告警"
      >
        <Bell className="w-5 h-5 text-neutral-600" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-600 text-[10px] font-bold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-80 rounded-md border border-neutral-200 bg-white shadow-lg z-50">
          <div className="flex items-center justify-between px-3 py-2 border-b border-neutral-100">
            <span className="text-sm font-semibold text-neutral-700">风控告警</span>
            <button
              type="button"
              className="text-xs text-blue-600 hover:underline"
              onClick={() => {
                setOpen(false);
                go({ to: "/supervisor/alerts" });
              }}
            >
              查看全部
            </button>
          </div>
          <ul className="max-h-72 overflow-y-auto divide-y divide-neutral-100">
            {alerts.slice(0, 5).map((a) => (
              <li
                key={a.risk_id}
                className={`px-3 py-2 cursor-pointer hover:bg-neutral-50 ${!a.read ? "bg-red-50" : ""}`}
                onClick={() => {
                  markRead(a.risk_id);
                  go({ to: `/calls/${a.call_id}` });
                }}
              >
                <div className="flex items-center gap-1 text-xs font-medium text-red-700">
                  <span>{a.level}</span>
                  <span>·</span>
                  <span>{catLabel(a.category)}</span>
                  {!a.read && (
                    <span className="ml-auto w-2 h-2 rounded-full bg-red-600" />
                  )}
                </div>
                <p className="text-xs text-neutral-600 truncate mt-0.5">
                  {a.agent_name} · 「{a.text_snippet}」
                </p>
              </li>
            ))}
            {alerts.length === 0 && (
              <li className="px-3 py-4 text-center text-xs text-neutral-400">
                暂无告警
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
