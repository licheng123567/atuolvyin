// v1.9.0 — admin 律师函/催告函模板管理
// v1.9.1 — UI 重构：.table-wrap + .table-toolbar 模式，新增搜索/类别筛选/状态徽章/预览模板
import { useCustom, useCustomMutation } from "@refinedev/core";
import { Eye, FileText, Pencil, Plus, Printer, RotateCcw, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { SearchInput } from "../../../components/ui/SearchInput";

interface TemplateVariable {
  name: string;
  label: string;
  type?: string;
  required?: boolean;
}

interface LetterTemplate {
  id: number;
  name: string;
  category: string;
  body_md: string;
  variables: TemplateVariable[] | null;
  is_active: boolean;
  created_at: string;
}

const CATEGORY_LABEL: Record<string, string> = {
  lawyer_letter: "律师函",
  notice: "催告函",
  reminder: "催缴提醒",
  other: "其他",
};

const CATEGORY_BADGE: Record<string, string> = {
  lawyer_letter: "ds-badge ds-badge-purple",
  notice: "ds-badge ds-badge-blue",
  reminder: "ds-badge ds-badge-orange",
  other: "ds-badge ds-badge-gray",
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

type CategoryFilter = "all" | "lawyer_letter" | "notice" | "reminder" | "other";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("zh-CN").replace(/\//g, "-");
}

/**
 * 用变量的展示标签（包在 [] 中）替换 body 中的 {{变量名}}。
 * 若没有定义变量，原样返回。
 */
function renderPreview(body: string, variables: TemplateVariable[] | null): string {
  if (!variables || variables.length === 0) return body;
  let out = body;
  for (const v of variables) {
    const re = new RegExp(`\\{\\{\\s*${v.name}\\s*\\}\\}`, "g");
    out = out.replace(re, `[${v.label}]`);
  }
  return out;
}

export function AdminInternalLetterTemplatesPage() {
  const { query, query: { refetch } } = useCustom<{ items: LetterTemplate[] }>({
    url: "admin/internal-letter-templates",
    method: "get",
    config: { query: { only_active: false, page_size: 100 } },
  });
  const items = useMemo(() => query.data?.data?.items ?? [], [query.data]);
  const isLoading = query.isLoading;

  const { mutate: create } = useCustomMutation();
  const { mutate: update } = useCustomMutation();
  const { mutate: del } = useCustomMutation();

  const [editingId, setEditingId] = useState<number | "new" | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [previewing, setPreviewing] = useState<LetterTemplate | null>(null);

  const [keyword, setKeyword] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("all");

  const filtered = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    return items.filter((t) => {
      if (categoryFilter !== "all" && t.category !== categoryFilter) return false;
      if (kw && !t.name.toLowerCase().includes(kw)) return false;
      return true;
    });
  }, [items, keyword, categoryFilter]);

  function resetFilters() {
    setKeyword("");
    setCategoryFilter("all");
  }

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
          <p className="page-subtitle">物业法务起草内部催告函或律师函时可选用模板。变量用 {`{{变量名}}`} 占位，签发时填入实际值。共 {items.length} 份。</p>
        </div>
        <button type="button" className="ds-btn ds-btn-primary" onClick={openNew}>
          <Plus className="w-3.5 h-3.5" /> 新增模板
        </button>
      </div>

      <div className="table-wrap">
        <div className="table-toolbar">
          <SearchInput
            value={keyword}
            onChange={setKeyword}
            placeholder="搜索模板名称"
            width={240}
          />
          <select
            className="form-control"
            style={{ width: 130 }}
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value as CategoryFilter)}
          >
            <option value="all">全部类别</option>
            <option value="lawyer_letter">律师函</option>
            <option value="notice">催告函</option>
            <option value="reminder">催缴提醒</option>
            <option value="other">其他</option>
          </select>
          <button
            type="button"
            className="ds-btn ds-btn-ghost ds-btn-sm"
            onClick={resetFilters}
            disabled={!keyword && categoryFilter === "all"}
          >
            <RotateCcw className="w-3.5 h-3.5" /> 重置
          </button>
        </div>

        <table>
          <thead>
            <tr>
              <th>模板名称</th>
              <th>类别</th>
              <th>变量数</th>
              <th>正文长度</th>
              <th>状态</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && filtered.length === 0 && (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: 40, color: "var(--color-neutral-400)" }}>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                    <FileText className="w-8 h-8" style={{ color: "var(--color-neutral-300)" }} />
                    <span>
                      {items.length === 0
                        ? "暂无模板，建议先建一份「律师函」+ 一份「催告函」"
                        : "无符合条件的模板，调整筛选条件后重试"}
                    </span>
                  </div>
                </td>
              </tr>
            )}
            {filtered.map((t) => (
              <tr key={t.id}>
                <td style={{ fontWeight: 600 }}>{t.name}</td>
                <td>
                  <span className={CATEGORY_BADGE[t.category] ?? "ds-badge ds-badge-gray"}>
                    {CATEGORY_LABEL[t.category] ?? t.category}
                  </span>
                </td>
                <td>{t.variables?.length ?? 0}</td>
                <td>{t.body_md.length} 字</td>
                <td>
                  {t.is_active ? (
                    <span className="ds-badge ds-badge-green">活跃</span>
                  ) : (
                    <span className="ds-badge ds-badge-gray">停用</span>
                  )}
                </td>
                <td style={{ fontSize: 11, color: "var(--color-neutral-500)" }}>
                  {formatDate(t.created_at)}
                </td>
                <td>
                  <button type="button" className="ds-btn ds-btn-ghost ds-btn-sm" onClick={() => setPreviewing(t)}>
                    <Eye className="w-3 h-3" /> 预览
                  </button>
                  <button type="button" className="ds-btn ds-btn-ghost ds-btn-sm" onClick={() => openEdit(t)}>
                    <Pencil className="w-3 h-3" /> 编辑
                  </button>
                  <button
                    type="button"
                    className="ds-btn ds-btn-ghost ds-btn-sm"
                    style={{ color: "var(--color-danger)" }}
                    onClick={() => handleDelete(t.id, t.name)}
                  >
                    <Trash2 className="w-3 h-3" /> 删除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 编辑/新增 Modal */}
      {editingId !== null && (
        <div className="modal-overlay" onClick={close}>
          <div className="ds-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 720 }}>
            <div className="modal-header">
              <span className="modal-title">{editingId === "new" ? "新增模板" : "编辑模板"}</span>
              <button type="button" className="modal-close" onClick={close}>×</button>
            </div>
            <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 12 }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">
                    模板名称<span className="req">*</span>
                  </label>
                  <input className="form-control" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">类别</label>
                  <select className="form-control" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                    <option value="lawyer_letter">律师函</option>
                    <option value="notice">催告函</option>
                    <option value="reminder">催缴提醒</option>
                    <option value="other">其他</option>
                  </select>
                </div>
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">
                  正文（用 {`{{变量名}}`} 占位）
                </label>
                <textarea
                  className="form-control"
                  style={{ height: 220, fontFamily: "var(--font-mono, monospace)", fontSize: 12 }}
                  value={form.body_md}
                  onChange={(e) => setForm({ ...form, body_md: e.target.value })}
                />
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">
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

      {/* 预览 Modal */}
      {previewing && (
        <div className="modal-overlay" onClick={() => setPreviewing(null)}>
          <div className="ds-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 720 }}>
            <div className="modal-header">
              <span className="modal-title">
                <Eye className="inline w-4 h-4 mr-1" />
                预览：{previewing.name}
                <span
                  className={CATEGORY_BADGE[previewing.category] ?? "ds-badge ds-badge-gray"}
                  style={{ marginLeft: 8 }}
                >
                  {CATEGORY_LABEL[previewing.category] ?? previewing.category}
                </span>
              </span>
              <button type="button" className="modal-close" onClick={() => setPreviewing(null)}>×</button>
            </div>
            <div className="modal-body">
              <div style={{ marginBottom: 12, fontSize: 12, color: "var(--color-neutral-500)" }}>
                变量已用 <code style={{ background: "var(--color-neutral-100)", padding: "1px 4px", borderRadius: 3 }}>[展示标签]</code> 形式占位，签发时会被实际值替换。
              </div>
              <pre
                id="letter-preview-content"
                style={{
                  background: "var(--color-neutral-50)",
                  border: "1px solid var(--color-neutral-200)",
                  borderRadius: "var(--radius-md, 6px)",
                  padding: "20px 24px",
                  fontSize: 13,
                  lineHeight: 1.8,
                  fontFamily: "var(--font-sans, system-ui, -apple-system, sans-serif)",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  margin: 0,
                  maxHeight: "60vh",
                  overflowY: "auto",
                  color: "var(--color-neutral-900)",
                }}
              >
                {renderPreview(previewing.body_md, previewing.variables)}
              </pre>
            </div>
            <div className="modal-footer">
              <button type="button" className="ds-btn ds-btn-secondary" onClick={() => setPreviewing(null)}>关闭</button>
              <button type="button" className="ds-btn ds-btn-primary" onClick={() => window.print()}>
                <Printer className="w-3.5 h-3.5" /> 打印 / 下载 PDF
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
