// Sprint 14.2 — 实时通话墙 (PRD §11.6)
// supervisor / admin / project_manager_property 角色看到所有正在通话的坐席
import { useCustom, useGo } from "@refinedev/core";
import {
  Activity,
  AlertTriangle,
  Headphones,
  PhoneCall,
  RadioTower,
  User2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useLiveCallStore, type LiveCall } from "../../../store/live-calls";

interface LiveCallsResp {
  items: LiveCall[];
}

export function SupervisorLiveWallPage() {
  const go = useGo();
  const calls = useLiveCallStore((s) => s.calls);
  const setInitial = useLiveCallStore((s) => s.setInitial);
  const [now, setNow] = useState(() => Date.now());

  // Initial fetch via REST (WS pushes deltas thereafter — wired in useSupervisorAlerts)
  const { query } = useCustom<LiveCallsResp>({
    url: "supervisor/live-calls",
    method: "get",
  });

  useEffect(() => {
    if (query.data?.data?.items) {
      setInitial(query.data.data.items);
    }
  }, [query.data, setInitial]);

  // Refresh duration ticker every 1s
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const sorted = useMemo(
    () =>
      [...calls].sort((a, b) => {
        // 风控告警的优先靠前；然后按 started_at 倒序
        if (a.risk_flagged !== b.risk_flagged) return a.risk_flagged ? -1 : 1;
        const at = a.started_at ? Date.parse(a.started_at) : 0;
        const bt = b.started_at ? Date.parse(b.started_at) : 0;
        return bt - at;
      }),
    [calls],
  );

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-2">
        <RadioTower className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          实时通话墙
        </h1>
        <span className="text-sm text-[var(--color-neutral-500)]">
          当前进行中：{sorted.length} 通
        </span>
        <div className="ml-auto flex items-center gap-1.5 text-xs text-[var(--color-neutral-500)]">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          实时同步中
        </div>
      </div>

      {sorted.length === 0 && !query.isLoading && (
        <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-12 text-center">
          <PhoneCall className="w-10 h-10 text-[var(--color-neutral-300)] mx-auto mb-3" />
          <p className="text-sm text-[var(--color-neutral-500)]">
            当前无坐席通话中。坐席在 App 内点「拨打」后，本页会自动显示。
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {sorted.map((c) => (
          <CallCard
            key={c.call_id}
            call={c}
            now={now}
            onClick={() => go({ to: `/admin/workstation/${c.call_id}` })}
          />
        ))}
      </div>
    </div>
  );
}

function CallCard({
  call,
  now,
  onClick,
}: {
  call: LiveCall;
  now: number;
  onClick: () => void;
}) {
  const startedMs = call.started_at ? Date.parse(call.started_at) : now;
  const elapsed = Math.max(0, Math.floor((now - startedMs) / 1000));
  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");

  const modeColor = call.recording_mode === "live" ? "text-blue-600" : "text-gray-500";
  const modeBg = call.recording_mode === "live" ? "bg-blue-50" : "bg-gray-100";
  const statusColor = call.status === "live" ? "text-green-600" : "text-amber-600";

  return (
    <button
      type="button"
      onClick={onClick}
      className={`text-left bg-white p-4 border rounded-lg shadow-sm hover:shadow-md transition cursor-pointer ${
        call.risk_flagged
          ? "border-red-300 ring-2 ring-red-200"
          : "border-[var(--color-neutral-200)]"
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <User2 className="w-4 h-4 text-[var(--color-neutral-500)]" />
          <span className="font-semibold text-[var(--color-neutral-900)]">
            {call.caller_name}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {call.risk_flagged && (
            <AlertTriangle className="w-4 h-4 text-red-500" aria-label="风控告警" />
          )}
          <span className={`text-xs px-2 py-0.5 rounded ${modeBg} ${modeColor}`}>
            {call.recording_mode === "live" ? "实时" : "事后"}
          </span>
        </div>
      </div>

      <div className="text-sm text-[var(--color-neutral-700)] space-y-0.5">
        {call.owner_name && (
          <div>
            业主：{call.owner_name}
            {call.owner_phone_masked ? ` · ${call.owner_phone_masked}` : ""}
          </div>
        )}
        {call.case_id && (
          <div className="text-xs text-[var(--color-neutral-500)]">
            案件 #{call.case_id}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mt-3 pt-2 border-t border-[var(--color-neutral-100)]">
        <div className="flex items-center gap-1.5 text-sm">
          <Activity className={`w-4 h-4 ${statusColor}`} />
          <span className={statusColor}>
            {call.status === "live" ? "通话中" : "拨号中"}
          </span>
        </div>
        <div className="font-mono text-sm text-[var(--color-neutral-700)]">
          {mm}:{ss}
        </div>
      </div>

      <div className="mt-2 flex items-center gap-1 text-xs text-[var(--color-primary)]">
        <Headphones className="w-3 h-3" />
        点击进入实时跟单
      </div>
    </button>
  );
}
