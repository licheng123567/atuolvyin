// v1.9.0 — admin 律师函/催告函模板管理
import { useCustom, useCustomMutation } from "@refinedev/core";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

interface LetterTemplate {
  id: number;
  name: string;
  category: string;
  body_md: string;
  variables: { name: string; label: string; type?: string; required?: boolean }[] | null;
  is_active: boolean;
  created_at: string;
}

const CATEGORY_LABEL: Record<string, string> = {
  lawyer_letter: "律师函",
  notice: "催告函",
  reminder: "催缴提醒",
  other: "其他",
};

interface FormState {
  name: string;
  category: string;
  body_md: string;
  variables_text: string;  // 简化：每行一个变量「变量名|展示标签」
}

const EMPTY_FORM: FormState = {
  name: "",
  category: "lawyer_letter",
  body_md: "致 {{owner_name}} 先生/女士：\n\n您所有的房产位于 {{building}}{{room}}，截至 {{notice_date}} 累计欠物业费 ¥{{amount_owed}}（共 {{months}} 个月）。\n\n请于 7 日内一次性结清，否则我方将依法采取诉讼追偿。\n\n签发律师：{{lawyer_name}}\n签发律所：{{law_firm_name}}\n日期：{{notice_date}}",
  variables_text: "owner_name|业主姓名\nbuilding|楼栋\nroom|房号\nnotice_date|发函日期\namount_owed|欠费金额\nmonths|欠费月数\nlawyer_name|律师姓名\nlaw_firm_name|律所名称",
};

export function AdminInternalLetterTemplatesPage() {
  const { query, query: { refetch } } = useCustom<{ items: LetterTemplate[] }>({
    url: "admin/internal-letter-templates",
    method: "get",
    config: { query: { only_active: true, page_size: 100 } },
  });
  const items = query.data?.data?.items ?? [];

  const { mutate: create } = useCustomMutation();
  const { mutate: update } = useCustomMutation();
  const { mutate: del } = useCustomMutation();

  const [editingId, setEditingId] = useState<number | "new" | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  function openNew() { setForm(EMPTY_FORM); setEditingId("new"); }
  function openEdit(t: LetterTemplate) {
    setForm({
      name: t.name,
      category: t.category,
      body_md: t.body_md,
      variables_text: (t.variables ?? []).map((v) => `${v.name}|${v.label}`).join("\n"),
    });
    setEditingId(t.id);
  }
  function close() { setEditingId(null); setForm(EMPTY_FORM); }

  function parseVariables(text: string): { name: string; label: string; type: string; required: boolean }[] {
    return text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [name, label] = line.split("|").map((s) => s.trim());
        return { name: name || "", label: label || name || "", type: "string", required: true };
      })
      .filter((v) => v.name);
  }

  function submit() {
    const values = {
      name: form.name,
      category: form.category,
      body_md: form.body_md,
      variables: parseVariables(form.variables_text),
    };
    const onSuccess = () => { close(); void refetch(); };
    const onError = (err: { message?: string }) => alert(`保存失败：${err.message ?? "未知错误"}`);
    if (editingId === "new") {
      create({ url: "admin/internal-letter-templates", method: "post", values }, { onSuccess, onError });
    } else if (editingId !== null) {
      update({ url: `admin/internal-letter-templates/${editingId}`, method: "patch", values }, { onSuccess, onError });
    }
  }

  function handleDelete(id: number, name: string) {
    if (!confirm(`确认删除模板「${name}」？（软删，已使用过的模板历史记录不受影响）`)) return;
    del({ url: `admin/internal-letter-templates/${id}`, method: "delete", values: {} }, {
      onSuccess: () => void refetch(),
      onError: (err: { message?: string }) => alert(`删除失败：${err.message ?? "未知错误"}`),
    });
  }

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 className="page-title">律师函 / 催告函模板</h1>
          <p className="page-subtitle">物业法务起草内部催告函或律师函时可选用模板。变量用 {`{{变量名}}`} 占位，签发时填入实际值。</p>
        </div>
        <button type="button" className="ds-btn ds-btn-primary" onClick={openNew}>
          <Plus className="w-3.5 h-3.5" /> 新增模板
        </button>
      </div>

      <div className="ds-card">
        <div className="card-body" style={{ padding: 0 }}>
          {items.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--color-neutral-400)" }}>
              暂无模板，点击右上角新增（建议先建一份「律师函」+ 一份「催告函」）
            </div>
          ) : (
            <table className="ds-table" style={{ width: "100%" }}>
              <thead>
                <tr>
                  <th>模板名称</th>
                  <th>类别</th>
                  <th>变量数</th>
                  <th>正文长度</th>
                  <th>创建时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((t) => (
                  <tr key={t.id}>
                    <td style={{ fontWeight: 600 }}>{t.name}</td>
                    <td><span className="ds-badge ds-badge-blue">{CATEGORY_LABEL[t.category] ?? t.category}</span></td>
                    <td>{t.variables?.length ?? 0}</td>
                    <td>{t.body_md.length} 字</td>
                    <td style={{ fontSize: 11, color: "var(--color-neutral-500)" }}>
                      {new Date(t.created_at).toLocaleDateString("zh-CN")}
                    </td>
                    <td>
                      <button type="button" className="ds-btn ds-btn-ghost ds-btn-sm" onClick={() => openEdit(t)}>
                        <Pencil className="w-3 h-3" /> 编辑
                      </button>
                      <button type="button" className="ds-btn ds-btn-ghost ds-btn-sm" style={{ color: "var(--color-danger)" }} onClick={() => handleDelete(t.id, t.name)}>
                        <Trash2 className="w-3 h-3" /> 删除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {editingId !== null && (
        <div className="modal-overlay" onClick={close}>
          <div className="ds-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 720 }}>
            <div className="modal-header">
              <span className="modal-title">{editingId === "new" ? "新增模板" : "编辑模板"}</span>
              <button type="button" className="modal-close" onClick={close}>×</button>
            </div>
            <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 500, color: "#374151", display: "block", marginBottom: 4 }}>模板名称 *</label>
                  <input className="form-control" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 500, color: "#374151", display: "block", marginBottom: 4 }}>类别</label>
                  <select className="form-control" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                    <option value="lawyer_letter">律师函</option>
                    <option value="notice">催告函</option>
                    <option value="reminder">催缴提醒</option>
                    <option value="other">其他</option>
                  </select>
                </div>
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 500, color: "#374151", display: "block", marginBottom: 4 }}>
                  正文（用 {`{{变量名}}`} 占位）
                </label>
                <textarea
                  className="form-control"
                  style={{ height: 220, fontFamily: "var(--font-mono, monospace)", fontSize: 12 }}
                  value={form.body_md}
                  onChange={(e) => setForm({ ...form, body_md: e.target.value })}
                />
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 500, color: "#374151", display: "block", marginBottom: 4 }}>
                  变量列表（每行一个：变量名|展示标签）
                </label>
                <textarea
                  className="form-control"
                  style={{ height: 100, fontFamily: "var(--font-mono, monospace)", fontSize: 12 }}
                  value={form.variables_text}
                  onChange={(e) => setForm({ ...form, variables_text: e.target.value })}
                  placeholder="owner_name|业主姓名"
                />
              </div>
            </div>
            <div className="modal-footer">
              <button type="button" className="ds-btn ds-btn-secondary" onClick={close}>取消</button>
              <button type="button" className="ds-btn ds-btn-primary" onClick={submit} disabled={!form.name.trim() || !form.body_md.trim()}>
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
