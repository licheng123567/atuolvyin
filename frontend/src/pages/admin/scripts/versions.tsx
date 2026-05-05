// frontend/src/pages/admin/scripts/versions.tsx
import { useOne, useCreate, useGo } from "@refinedev/core";
import { useParams } from "react-router-dom";
import { useState } from "react";
import { ArrowLeft, RotateCcw, ChevronDown, ChevronUp } from "lucide-react";

interface VersionItem {
  version: number;
  title: string;
  trigger_intent: string;
  content: string;
  notes: string | null;
  edited_by: number | null;
  edited_at: string;
}

interface ScriptDetail {
  id: number;
  title: string;
  version: number;
}

export function ScriptVersionsPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();
  const scriptId = Number(id);
  const [expandedVersion, setExpandedVersion] = useState<number | null>(null);
  const [confirmVersion, setConfirmVersion] = useState<number | null>(null);
  const [rollbackError, setRollbackError] = useState("");

  const { query: scriptQuery } = useOne<ScriptDetail>({
    resource: "admin/scripts", id: scriptId,
  });
  const { query: versionsQuery } = useOne<VersionItem[]>({
    resource: `admin/scripts/${scriptId}`, id: "versions",
  });

  const { mutate: rollback, mutation: rollbackMut } = useCreate();
  const script = scriptQuery.data?.data;
  const versions: VersionItem[] = (versionsQuery.data?.data as unknown as VersionItem[]) ?? [];

  const handleRollback = (toVersion: number) => {
    setRollbackError("");
    rollback(
      { resource: `admin/scripts/${scriptId}/rollback`, values: { to_version: toVersion } },
      {
        onSuccess: () => { setConfirmVersion(null); go({ to: `/admin/scripts` }); },
        onError: () => setRollbackError("回滚失败，请重试"),
      },
    );
  };

  return (
    <div style={{ padding: 24, maxWidth: 800 }}>
      <button onClick={() => go({ to: "/admin/scripts" })}
        style={{ display: "flex", alignItems: "center", gap: 6, background: "none", border: "none", cursor: "pointer", color: "#6b7280", marginBottom: 16 }}>
        <ArrowLeft size={16} /> 返回话术库
      </button>

      <h2 style={{ margin: "0 0 4px", fontSize: 20, fontWeight: 600 }}>
        {script?.title ?? "…"} — 版本历史
      </h2>
      <p style={{ margin: "0 0 24px", color: "#6b7280", fontSize: 13 }}>
        当前版本：v{script?.version}
      </p>

      {versions.map((v) => (
        <div key={v.version} style={{
          border: "1px solid #e5e7eb", borderRadius: 8, marginBottom: 12, overflow: "hidden",
        }}>
          <div style={{
            display: "flex", alignItems: "center", padding: "12px 16px",
            background: "#f9fafb", cursor: "pointer",
          }} onClick={() => setExpandedVersion(expandedVersion === v.version ? null : v.version)}>
            <div style={{ flex: 1 }}>
              <span style={{ fontWeight: 600, marginRight: 12 }}>v{v.version}</span>
              <span style={{ color: "#6b7280", fontSize: 13 }}>{v.edited_at.slice(0, 10)}</span>
              <span style={{ marginLeft: 12, color: "#374151", fontSize: 14 }}>
                {v.content.slice(0, 80)}{v.content.length > 80 ? "…" : ""}
              </span>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {v.version !== script?.version && (
                <button
                  onClick={(e) => { e.stopPropagation(); setConfirmVersion(v.version); }}
                  style={{ fontSize: 12, padding: "4px 10px", background: "#fef3c7", color: "#92400e", border: "1px solid #fde68a", borderRadius: 4, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
                  <RotateCcw size={12} /> 回滚到此版本
                </button>
              )}
              {expandedVersion === v.version ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </div>
          </div>
          {expandedVersion === v.version && (
            <div style={{ padding: "16px", borderTop: "1px solid #e5e7eb", fontSize: 14 }}>
              <div style={{ marginBottom: 8 }}><strong>标题：</strong>{v.title}</div>
              <div style={{ marginBottom: 8 }}><strong>类型：</strong>{v.trigger_intent}</div>
              <div style={{ marginBottom: 8, whiteSpace: "pre-wrap" }}><strong>内容：</strong>{v.content}</div>
              {v.notes && <div><strong>说明：</strong>{v.notes}</div>}
            </div>
          )}
        </div>
      ))}

      {/* Rollback Confirm Dialog */}
      {confirmVersion !== null && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 60 }}>
          <div style={{ background: "#fff", borderRadius: 10, padding: 24, maxWidth: 400, width: "90%" }}>
            <h3 style={{ margin: "0 0 12px", fontSize: 16 }}>确认回滚</h3>
            <p style={{ margin: "0 0 16px", fontSize: 14, color: "#374151" }}>
              将覆盖当前 v{script?.version}，生成 v{(script?.version ?? 0) + 1}，确认继续？
            </p>
            {rollbackError && <p style={{ color: "#ef4444", fontSize: 13 }}>{rollbackError}</p>}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button onClick={() => setConfirmVersion(null)}
                style={{ padding: "8px 16px", background: "#f9fafb", border: "1px solid #d1d5db", borderRadius: 6, cursor: "pointer" }}>取消</button>
              <button onClick={() => handleRollback(confirmVersion)}
                disabled={rollbackMut.isPending}
                style={{ padding: "8px 16px", background: "#f59e0b", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer" }}>
                {rollbackMut.isPending ? "回滚中…" : "确认回滚"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
