// frontend/src/pages/admin/workstation/live.tsx
import { useParams } from "react-router-dom";
import { useOne } from "@refinedev/core";
import { RealtimeCallShell } from "../../../components/realtime/RealtimeCallShell";

export function AdminLiveWorkstationPage() {
  const { call_id } = useParams<{ call_id: string }>();
  const callId = Number(call_id);
  const token = localStorage.getItem("access_token") ?? "";

  const { query } = useOne<{ case_id: number; owner_name?: string }>({
    resource: "calls", id: callId, queryOptions: { enabled: !!callId },
  });
  const owner = query.data?.data ? { name: query.data.data.owner_name ?? "" } : null;

  if (!callId) return <div>缺少 call_id</div>;
  return <RealtimeCallShell callId={callId} role="observer" token={token} owner={owner} />;
}
