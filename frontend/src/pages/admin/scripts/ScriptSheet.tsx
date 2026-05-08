// frontend/src/pages/admin/scripts/ScriptSheet.tsx
import { useCreate, useList, useUpdate } from "@refinedev/core";
import { useReducer, useEffect } from "react";
import { X } from "lucide-react";
import type { PaginatedResponse } from "../../../types";
import { TRIGGER_INTENTS } from "./helpers";

interface ProjectOption {
  id: number;
  name: string;
}

type SceneKey = "opening" | "objection_handling" | "promise_confirm" | "closing";

const SCENE_OPTIONS: { value: SceneKey; label: string }[] = [
  { value: "opening", label: "开场白" },
  { value: "objection_handling", label: "异议处理" },
  { value: "promise_confirm", label: "承诺确认" },
  { value: "closing", label: "挂断收尾" },
];

interface ScriptItem {
  id: number;
  title: string;
  scene?: SceneKey;
  trigger_intent: string;
  content: string;
  notes: string | null;
  version: number;
  project_id?: number | null;
  project_name?: string | null;
}

interface Props {
  open: boolean;
  onClose: () => void;
  script: ScriptItem | null;
  onSuccess: () => void;
}

interface FormState {
  title: string;
  scene: SceneKey;
  intent: typeof TRIGGER_INTENTS[number];
  content: string;
  notes: string;
  projectId: number | "";
  error: string;
}

type FormAction =
  | { type: "RESET"; script: ScriptItem | null }
  | { type: "SET_TITLE"; value: string }
  | { type: "SET_SCENE"; value: SceneKey }
  | { type: "SET_INTENT"; value: typeof TRIGGER_INTENTS[number] }
  | { type: "SET_CONTENT"; value: string }
  | { type: "SET_NOTES"; value: string }
  | { type: "SET_PROJECT"; value: number | "" }
  | { type: "SET_ERROR"; value: string };

function formReducer(state: FormState, action: FormAction): FormState {
  switch (action.type) {
    case "RESET":
      return action.script && action.script.title
        ? {
            title: action.script.title,
            scene: (action.script.scene ?? "objection_handling") as SceneKey,
            intent: action.script.trigger_intent as typeof TRIGGER_INTENTS[number],
            content: action.script.content,
            notes: action.script.notes ?? "",
            projectId: action.script.project_id ?? "",
            error: "",
          }
        : {
            title: "",
            scene: (action.script?.scene ?? "objection_handling") as SceneKey,
            intent: TRIGGER_INTENTS[0],
            content: "",
            notes: "",
            projectId: "",
            error: "",
          };
    case "SET_TITLE":   return { ...state, title: action.value };
    case "SET_SCENE":   return { ...state, scene: action.value };
    case "SET_INTENT":  return { ...state, intent: action.value };
    case "SET_CONTENT": return { ...state, content: action.value };
    case "SET_NOTES":   return { ...state, notes: action.value };
    case "SET_PROJECT": return { ...state, projectId: action.value };
    case "SET_ERROR":   return { ...state, error: action.value };
  }
}

export function ScriptSheet({ open, onClose, script, onSuccess }: Props) {
  const [form, dispatch] = useReducer(formReducer, {
    title: "", scene: "objection_handling" as SceneKey, intent: TRIGGER_INTENTS[0], content: "", notes: "", projectId: "" as number | "", error: "",
  });

  // v1.5.7 — 拉本租户项目用于「生效范围」选择
  const { query: projectsQuery } = useList<ProjectOption>({
    resource: "admin/projects",
    pagination: { currentPage: 1, pageSize: 100 },
    queryOptions: { enabled: open },
  });
  const projectsRaw = projectsQuery.data?.data;
  const projects: ProjectOption[] =
    (projectsRaw as unknown as PaginatedResponse<ProjectOption>)?.items ??
    (projectsRaw as ProjectOption[] | undefined) ??
    [];

  const { mutate: create, mutation: createMut } = useCreate();
  const { mutate: update, mutation: updateMut } = useUpdate();
  const isPending = createMut.isPending || updateMut.isPending;

  useEffect(() => {
    dispatch({ type: "RESET", script });
  }, [script, open]);

  if (!open) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    dispatch({ type: "SET_ERROR", value: "" });
    if (!form.title.trim() || !form.content.trim()) {
      dispatch({ type: "SET_ERROR", value: "标题和话术内容为必填项" });
      return;
    }
    const values = {
      title: form.title,
      scene: form.scene,
      trigger_intent: form.scene === "objection_handling" ? form.intent : "其他",
      content: form.content,
      notes: form.notes || null,
      project_id: form.projectId === "" ? null : form.projectId,
    };
    if (script) {
      update(
        { resource: "admin/scripts", id: script.id, values },
        { onSuccess, onError: () => dispatch({ type: "SET_ERROR", value: "保存失败，请重试" }) },
      );
    } else {
      create(
        { resource: "admin/scripts", values },
        { onSuccess, onError: () => dispatch({ type: "SET_ERROR", value: "创建失败，请重试" }) },
      );
    }
  };

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 50,
      display: "flex", justifyContent: "flex-end",
    }}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.3)" }} onClick={onClose} />
      <div style={{
        position: "relative", width: 480, height: "100%",
        background: "#fff", boxShadow: "-4px 0 24px rgba(0,0,0,0.12)",
        display: "flex", flexDirection: "column",
      }}>
        <div style={{ padding: "20px 24px", borderBottom: "1px solid #e5e7eb", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>
            {script ? `编辑话术（当前 v${script.version}，保存后升为 v${script.version + 1}）` : "新增话术"}
          </h2>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer" }}><X size={20} /></button>
        </div>

        <form onSubmit={handleSubmit} style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4 }}>话术标题 *</label>
            <input value={form.title} onChange={(e) => dispatch({ type: "SET_TITLE", value: e.target.value })}
              maxLength={128}
              style={{ width: "100%", padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14 }} />
          </div>

          <div>
            <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4 }}>通话场景 *</label>
            <select value={form.scene} onChange={(e) => dispatch({ type: "SET_SCENE", value: e.target.value as SceneKey })}
              style={{ width: "100%", padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14 }}>
              {SCENE_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>

          {form.scene === "objection_handling" && (
            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4 }}>异议类型 *</label>
              <select value={form.intent} onChange={(e) => dispatch({ type: "SET_INTENT", value: e.target.value as typeof form.intent })}
                style={{ width: "100%", padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14 }}>
                {TRIGGER_INTENTS.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          )}

          <div>
            <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4 }}>话术内容 *</label>
            <textarea value={form.content} onChange={(e) => dispatch({ type: "SET_CONTENT", value: e.target.value })}
              rows={6}
              style={{ width: "100%", padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14, resize: "vertical" }} />
          </div>

          {/* v1.5.7 — 项目级生效范围 */}
          <div>
            <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4 }}>
              生效范围
            </label>
            <select
              value={form.projectId}
              onChange={(e) =>
                dispatch({ type: "SET_PROJECT", value: e.target.value === "" ? "" : Number(e.target.value) })
              }
              style={{ width: "100%", padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14 }}
            >
              <option value="">本物业全项目通用（默认）</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  仅 {p.name}
                </option>
              ))}
            </select>
            <p style={{ fontSize: 12, color: "#6b7280", marginTop: 4 }}>
              选「本物业全项目」此话术对所有项目可见；选具体项目仅在该项目内可见。
            </p>
          </div>

          <div>
            <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4 }}>编写说明（可选）</label>
            <textarea value={form.notes} onChange={(e) => dispatch({ type: "SET_NOTES", value: e.target.value })}
              rows={3}
              style={{ width: "100%", padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14, resize: "vertical" }} />
          </div>

          {form.error && <p style={{ color: "#ef4444", fontSize: 13, margin: 0 }}>{form.error}</p>}
        </form>

        <div style={{ padding: "16px 24px", borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button onClick={onClose} style={{ padding: "8px 16px", background: "#f9fafb", border: "1px solid #d1d5db", borderRadius: 6, cursor: "pointer" }}>取消</button>
          <button onClick={handleSubmit} disabled={isPending}
            style={{ padding: "8px 16px", background: "var(--color-primary)", color: "#fff", border: "none", borderRadius: 6, cursor: isPending ? "not-allowed" : "pointer" }}>
            {isPending ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
