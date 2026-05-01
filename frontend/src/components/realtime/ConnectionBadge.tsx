// frontend/src/components/realtime/ConnectionBadge.tsx
import type { CallSocketStatus } from "../../lib/realtime/types";

const LABELS: Record<CallSocketStatus, { text: string; cls: string }> = {
  connecting: { text: "连接中…", cls: "text-slate-500" },
  connected: { text: "🟢 实时", cls: "text-emerald-600" },
  reconnecting: { text: "🟡 重连中", cls: "text-amber-600" },
  failed: { text: "🔴 失联", cls: "text-red-600" },
  call_ended: { text: "通话结束", cls: "text-slate-400" },
};

export function ConnectionBadge({ status }: { status: CallSocketStatus }) {
  const { text, cls } = LABELS[status];
  return <span className={`text-sm font-medium ${cls}`}>{text}</span>;
}
