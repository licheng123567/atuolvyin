// frontend/src/pages/admin/scripts/versions.tsx
// v1.5.7 — 1:1 还原 ui/admin.html#modal-script-versions：当前版本 badge + 编辑者元数据
import { useCreate, useGo, useList, useOne } from "@refinedev/core";
import { useParams } from "react-router-dom";
import { useState } from "react";
import { ArrowLeft, ChevronDown, ChevronUp, RotateCcw } from "lucide-react";
import type { PaginatedResponse } from "../../../types";

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

interface UserItem {
  id: number;
  name: string;
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

  // 拉本租户用户用于编辑者名映射
  const { query: usersQuery } = useList<UserItem>({
    resource: "admin/users",
    pagination: { currentPage: 1, pageSize: 200 },
  });
  const usersRaw = usersQuery.data?.data;
  const allUsers: UserItem[] =
    (usersRaw as unknown as PaginatedResponse<UserItem>)?.items ??
    (usersRaw as UserItem[] | undefined) ??
    [];
  const userNameById = (id: number | null): string => {
    if (id === null) return "—";
    const u = allUsers.find((x) => x.id === id);
    return u ? u.name : `用户#${id}`;
  };

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

      {versions.map((v) => {
        const isCurrent = v.version === script?.version;
        const editor = userNameById(v.edited_by);
        const editedDate = new Date(v.edited_at).toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
        return (
        <div key={v.version} style={{
          border: isCurrent ? "1px solid var(--color-primary)" : "1px solid #e5e7eb",
          borderRadius: 8,
          marginBottom: 12,
          overflow: "hidden",
          background: isCurrent ? "var(--color-primary-light, #eff6ff)" : "white",
        }}>
          <div style={{
            display: "flex", alignItems: "center", padding: "12px 16px",
            background: isCurrent ? "transparent" : "#f9fafb",
            cursor: "pointer",
          }} onClick={() => setExpandedVersion(expandedVersion === v.version ? null : v.version)}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ fontWeight: 600 }}>v{v.version}</span>
                {isCurrent && (
                  <span className="ds-badge ds-badge-blue" style={{ fontSize: 11 }}>
                    当前版本
                  </span>
                )}
                <span style={{ color: "var(--color-neutral-500)", fontSize: 12 }}>
                  {editor} · {editedDate}
                </span>
              </div>
              <div style={{ color: "#374151", fontSize: 13.5, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {v.content.slice(0, 80)}{v.content.length > 80 ? "…" : ""}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexShrink: 0, marginLeft: 12 }}>
              {!isCurrent && (
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
            <div style={{ padding: "16px", borderTop: "1px solid #e5e7eb", fontSize: 14, background: "white" }}>
              <div style={{ marginBottom: 8 }}><strong>标题：</strong>{v.title}</div>
              <div style={{ marginBottom: 8 }}><strong>类型：</strong>{v.trigger_intent}</div>
              <div style={{ marginBottom: 8, whiteSpace: "pre-wrap" }}><strong>内容：</strong>{v.content}</div>
              {v.notes && <div><strong>说明：</strong>{v.notes}</div>}
            </div>
          )}
        </div>
      )})}

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
