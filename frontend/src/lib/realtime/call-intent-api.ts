// Sprint 16 — 通话动作意向 stub（转主管/发支付码/转法务）
export type CallIntentAction =
  | "transfer_supervisor"
  | "send_payment_code"
  | "transfer_legal";

export async function postCallIntent(
  callId: number,
  action: CallIntentAction,
  token: string,
  note?: string,
): Promise<void> {
  const resp = await fetch(`/api/v1/calls/${callId}/intent`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ action, ...(note ? { note } : {}) }),
  });
  if (!resp.ok) {
    throw new Error(`call intent ${action} failed: ${resp.status}`);
  }
}

export async function createCallWorkOrder(
  params: {
    callId: number;
    caseId: number | null;
    description: string;
    priority?: "low" | "normal" | "high";
  },
  token: string,
): Promise<{ id: number }> {
  const resp = await fetch(`/api/v1/workorders`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      call_id: params.callId,
      case_id: params.caseId,
      order_type: "call_followup",
      description: params.description,
      priority: params.priority ?? "normal",
    }),
  });
  if (!resp.ok) {
    throw new Error(`create work order failed: ${resp.status}`);
  }
  return (await resp.json()) as { id: number };
}
