// frontend/src/lib/realtime/feedback-api.ts
export async function postSuggestionFeedback(
  callId: number,
  suggestionId: string,
  action: "adopt" | "ignore",
  token: string,
): Promise<void> {
  const resp = await fetch(
    `/api/v1/calls/${callId}/suggestions/${encodeURIComponent(suggestionId)}/feedback`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ action }),
    },
  );
  if (!resp.ok) {
    throw new Error(`feedback failed: ${resp.status}`);
  }
}
