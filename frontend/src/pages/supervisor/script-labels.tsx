// frontend/src/pages/supervisor/script-labels.tsx
import { useList, useCreate } from "@refinedev/core";
import { useState } from "react";
import { X } from "lucide-react";
import { getLabelStatus } from "./helpers";

interface LabelItem {
  feedback_id: number;
  call_id: number;
  suggestion_text: string;
  supervisor_label: string | null;
  supervisor_note: string | null;
  script_template_id: number | null;
  created_at: string;
}

export function SupervisorScriptLabelsPage() {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [modalFb, setModalFb] = useState<LabelItem | null>(null);
  const [labelChoice, setLabelChoice] = useState<"good" | "bad">("good");
  const [note, setNote] = useState("");
  const [noteError, setNoteError] = useState("");

  const { query } = useList<LabelItem>({
    resource: "supervisor/script-labels",
    filters: unreadOnly ? [{ field: "unread_only", operator: "eq", value: true }] : [],
  });

  const items: LabelItem[] = (query.data?.data as unknown as LabelItem[]) ?? [];
  const { mutate: submitLabel, mutation: submitMut } = useCreate();

  const handleSubmit = () => {
    setNoteError("");
    if (labelChoice === "bad" && !note.trim()) {
      setNoteError("差话术标注必须填写点评");
      return;
    }
    if (!modalFb) return;
    submitLabel(
      {
        resource: `supervisor/script-labels/${modalFb.feedback_id}`,
        values: { label: labelChoice, note: note || null },
      },
      {
        onSuccess: () => { setModalFb(null); query.refetch(); },
        onError: () => setNoteError("提交失败，请重试"),
      },
    );
  };

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>话术标注</h2>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 14, cursor: "pointer" }}>
          <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} />
          仅看未标注
        </label>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #e5e7eb", background: "#f9fafb" }}>
            {["话术内容", "通话 ID", "时间", "坐席反馈", "督导标注"].map((h) => (
              <th key={h} style={{ padding: "10px 12px", textAlign: "left", fontWeight: 500 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const status = getLabelStatus(item.supervisor_label);
            return (
              <tr key={item.feedback_id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                <td style={{ padding: "10px 12px", maxWidth: 300 }}>
                  {item.suggestion_text.slice(0, 80)}{item.suggestion_text.length > 80 ? "…" : ""}
                </td>
                <td style={{ padding: "10px 12px" }}>{item.call_id}</td>
                <td style={{ padding: "10px 12px" }}>{item.created_at.slice(0, 10)}</td>
                <td style={{ padding: "10px 12px" }}>—</td>
                <td style={{ padding: "10px 12px" }}>
                  {status === "unlabeled" ? (
                    <div style={{ display: "flex", gap: 6 }}>
                      <button onClick={() => { setModalFb(item); setLabelChoice("good"); setNote(""); setNoteError(""); }}
                        style={{ padding: "4px 10px", background: "#dcfce7", color: "#15803d", border: "1px solid #bbf7d0", borderRadius: 4, cursor: "pointer", fontSize: 12 }}>好话术</button>
                      <button onClick={() => { setModalFb(item); setLabelChoice("bad"); setNote(""); setNoteError(""); }}
                        style={{ padding: "4px 10px", background: "#fee2e2", color: "#b91c1c", border: "1px solid #fecaca", borderRadius: 4, cursor: "pointer", fontSize: 12 }}>差话术</button>
                    </div>
                  ) : (
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{
                        padding: "2px 8px", borderRadius: 4, fontSize: 12,
                        background: status === "good" ? "#dcfce7" : "#fee2e2",
                        color: status === "good" ? "#15803d" : "#b91c1c",
                      }}>
                        {status === "good" ? "好话术" : "差话术"}
                      </span>
                      <button onClick={() => { setModalFb(item); setLabelChoice(item.supervisor_label as "good" | "bad"); setNote(item.supervisor_note ?? ""); setNoteError(""); }}
                        style={{ fontSize: 12, color: "#6b7280", background: "none", border: "none", cursor: "pointer" }}>修改</button>
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Label Modal */}
      {modalFb && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 60 }}>
          <div style={{ background: "#fff", borderRadius: 10, padding: 24, width: 400, maxWidth: "92vw" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <h3 style={{ margin: 0, fontSize: 16 }}>话术标注</h3>
              <button onClick={() => setModalFb(null)} style={{ background: "none", border: "none", cursor: "pointer" }}><X size={18} /></button>
            </div>
            <p style={{ fontSize: 13, color: "#374151", marginBottom: 12 }}>{modalFb.suggestion_text.slice(0, 120)}</p>

            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              {(["good", "bad"] as const).map((l) => (
                <button key={l} onClick={() => setLabelChoice(l)}
                  style={{
                    flex: 1, padding: "8px", borderRadius: 6, cursor: "pointer", fontSize: 14,
                    border: labelChoice === l ? "2px solid var(--color-primary)" : "1px solid #d1d5db",
                    background: labelChoice === l ? "var(--color-primary-light)" : "#fff",
                    fontWeight: labelChoice === l ? 600 : 400,
                  }}>
                  {l === "good" ? "好话术" : "差话术"}
                </button>
              ))}
            </div>

            {labelChoice === "bad" && (
              <div style={{ marginBottom: 12 }}>
                <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4 }}>点评（差话术必填）</label>
                <textarea value={note} onChange={(e) => setNote(e.target.value)}
                  rows={3} style={{ width: "100%", padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14, resize: "vertical" }} />
              </div>
            )}

            {noteError && <p style={{ color: "#ef4444", fontSize: 12, margin: "0 0 8px" }}>{noteError}</p>}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button onClick={() => setModalFb(null)}
                style={{ padding: "8px 16px", background: "#f9fafb", border: "1px solid #d1d5db", borderRadius: 6, cursor: "pointer" }}>取消</button>
              <button onClick={handleSubmit} disabled={submitMut.isPending}
                style={{ padding: "8px 16px", background: "var(--color-primary)", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer" }}>
                {submitMut.isPending ? "提交中…" : "提交"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
