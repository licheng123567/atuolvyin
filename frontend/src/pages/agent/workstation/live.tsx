// frontend/src/pages/agent/workstation/live.tsx
import { useParams } from "react-router-dom";
import { useOne } from "@refinedev/core";
import { RealtimeCallShell } from "../../../components/realtime/RealtimeCallShell";

export function AgentLiveWorkstationPage() {
  const { call_id } = useParams<{ call_id: string }>();
  const callId = Number(call_id);
  const token = localStorage.getItem("access_token") ?? "";

  // Fetch owner info via the call detail endpoint (which references the case)
  const { query: callQuery } = useOne<{ case_id: number }>({
    resource: "calls", id: callId, queryOptions: { enabled: !!callId },
  });
  const caseId = callQuery.data?.data?.case_id;
  const { query: caseQuery } = useOne<{ owner_name?: string; owner_building?: string; owner_room?: string; amount_owed?: string }>({
    resource: "agent/cases", id: caseId ?? 0, queryOptions: { enabled: !!caseId },
  });
  const owner = caseQuery.data?.data
    ? {
        name: caseQuery.data.data.owner_name ?? "未知业主",
        building: caseQuery.data.data.owner_building,
        room: caseQuery.data.data.owner_room,
        amount_owed: caseQuery.data.data.amount_owed,
      }
    : null;

  if (!callId) return <div>缺少 call_id</div>;
  return <RealtimeCallShell callId={callId} role="agent" token={token} owner={owner} />;
}
