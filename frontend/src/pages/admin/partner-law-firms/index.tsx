// v1.9.0 — admin 合作律所管理（用于法务老周起草律师函时签发盖章方）
// v1.9.1 — UI 重构：.table-wrap + .table-toolbar 模式，新增搜索 / 状态筛选 / 状态徽章 / 使用次数列
import { useCustom, useCustomMutation } from "@refinedev/core";
import { Building2, Pencil, Plus, RotateCcw, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { SearchInput } from "../../../components/ui/SearchInput";

interface PartnerLawFirm {
  id: number;
  name: string;
  contact_name: string | null;
  contact_phone_masked: string | null;
  contact_email: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  // 后端将在后续 PR 增补该字段；目前可能为 undefined
  usage_count?: number;
}

interface FormState {
  name: string;
  contact_name: string;
  contact_phone: string;
  contact_email: string;
  notes: string;
}

const EMPTY_FORM: FormState = { name: "", contact_name: "", contact_phone: "", contact_email: "", notes: "" };

type StatusFilter = "all" | "active" | "inactive";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("zh-CN").replace(/\//g, "-");
}

export function AdminPartnerLawFirmsPage() {
  const { query, query: { refetch } } = useCustom<{ items: PartnerLawFirm[]; total: number }>({
    url: "admin/partner-law-firms",
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

  const [keyword, setKeyword] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const filtered = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    return items.filter((f) => {
      if (statusFilter === "active" && !f.is_active) return false;
      if (statusFilter === "inactive" && f.is_active) return false;
      if (kw) {
        const inName = f.name.toLowerCase().includes(kw);
        const inContact = (f.contact_name ?? "").toLowerCase().includes(kw);
        if (!inName && !inContact) return false;
      }
      return true;
    });
  }, [items, keyword, statusFilter]);

  function resetFilters() {
    setKeyword("");
    setStatusFilter("all");
  }

  function openNew() {
    setForm(EMPTY_FORM);
    setEditingId("new");
  }
  function openEdit(f: PartnerLawFirm) {
    setForm({
      name: f.name,
      contact_name: f.contact_name ?? "",
      contact_phone: "",  // 脱敏不能回填，留空
      contact_email: f.contact_email ?? "",
      notes: f.notes ?? "",
    });
    setEditingId(f.id);
  }
  function close() { setEditingId(null); setForm(EMPTY_FORM); }

  function submit() {
    const values: Record<string, string | undefined> = {
      name: form.name,
      contact_name: form.contact_name || undefined,
      contact_phone: form.contact_phone || undefined,
      contact_email: form.contact_email || undefined,
      notes: form.notes || undefined,
    };
    const onSuccess = () => { close(); void refetch(); };
    const onError = (err: { message?: string }) => alert(`保存失败：${err.message ?? "未知错误"}`);
    if (editingId === "new") {
      create({ url: "admin/partner-law-firms", method: "post", values }, { onSuccess, onError });
    } else if (editingId !== null) {
      update({ url: `admin/partner-law-firms/${editingId}`, method: "patch", values }, { onSuccess, onError });
    }
  }

  function handleDelete(id: number, name: string) {
    if (!confirm(`确认删除合作律所「${name}」？（软删，已关联的处理记录不受影响）`)) return;
    del({ url: `admin/partner-law-firms/${id}`, method: "delete", values: {} }, {
      onSuccess: () => void refetch(),
      onError: (err: { message?: string }) => alert(`删除失败：${err.message ?? "未知错误"}`),
    });
  }

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 className="page-title">合作律所</h1>
          <p className="page-subtitle">物业法务起草律师函时可选择合作律所作为盖章方。共 {items.length} 家。</p>
        </div>
        <button type="button" className="ds-btn ds-btn-primary" onClick={openNew}>
          <Plus className="w-3.5 h-3.5" /> 新增律所
        </button>
      </div>

      <div className="table-wrap">
        <div className="table-toolbar">
          <SearchInput
            value={keyword}
            onChange={setKeyword}
            placeholder="搜索律所名称 / 联系人"
            width={240}
          />
          <select
            className="form-control"
            style={{ width: 130 }}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
          >
            <option value="all">全部状态</option>
            <option value="active">活跃</option>
            <option value="inactive">停用</option>
          </select>
          <button
            type="button"
            className="ds-btn ds-btn-ghost ds-btn-sm"
            onClick={resetFilters}
            disabled={!keyword && statusFilter === "all"}
          >
            <RotateCcw className="w-3.5 h-3.5" /> 重置
          </button>
        </div>

        <table>
          <thead>
            <tr>
              <th>律所名称</th>
              <th>联系人</th>
              <th>联系电话</th>
              <th>邮箱</th>
              <th>使用次数</th>
              <th>状态</th>
              <th>备注</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={9} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && filtered.length === 0 && (
              <tr>
                <td colSpan={9} style={{ textAlign: "center", padding: 40, color: "var(--color-neutral-400)" }}>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                    <Building2 className="w-8 h-8" style={{ color: "var(--color-neutral-300)" }} />
                    <span>
                      {items.length === 0
                        ? "暂无合作律所，点击右上角「新增律所」"
                        : "无符合条件的律所，调整筛选条件后重试"}
                    </span>
                  </div>
                </td>
              </tr>
            )}
            {filtered.map((f) => (
              <tr key={f.id}>
                <td style={{ fontWeight: 600 }}>{f.name}</td>
                <td>{f.contact_name || <span className="text-muted">—</span>}</td>
                <td style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 12 }}>
                  {f.contact_phone_masked || <span className="text-muted">—</span>}
                </td>
                <td>{f.contact_email || <span className="text-muted">—</span>}</td>
                <td>
                  {f.usage_count != null ? `${f.usage_count} 封` : <span className="text-muted">—</span>}
                </td>
                <td>
                  {f.is_active ? (
                    <span className="ds-badge ds-badge-green">活跃</span>
                  ) : (
                    <span className="ds-badge ds-badge-gray">停用</span>
                  )}
                </td>
                <td style={{ fontSize: 12, color: "var(--color-neutral-600)", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={f.notes ?? undefined}>
                  {f.notes || <span className="text-muted">—</span>}
                </td>
                <td style={{ fontSize: 11, color: "var(--color-neutral-500)" }}>
                  {formatDate(f.created_at)}
                </td>
                <td>
                  <button type="button" className="ds-btn ds-btn-ghost ds-btn-sm" onClick={() => openEdit(f)}>
                    <Pencil className="w-3 h-3" /> 编辑
                  </button>
                  <button
                    type="button"
                    className="ds-btn ds-btn-ghost ds-btn-sm"
                    style={{ color: "var(--color-danger)" }}
                    onClick={() => handleDelete(f.id, f.name)}
                  >
                    <Trash2 className="w-3 h-3" /> 删除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editingId !== null && (
        <div className="modal-overlay" onClick={close}>
          <div className="ds-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 520 }}>
            <div className="modal-header">
              <span className="modal-title">{editingId === "new" ? "新增合作律所" : "编辑合作律所"}</span>
              <button type="button" className="modal-close" onClick={close}>×</button>
            </div>
            <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <Field label="律所名称" required value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
              <Field label="联系人" value={form.contact_name} onChange={(v) => setForm({ ...form, contact_name: v })} />
              <Field
                label={editingId === "new" ? "联系电话（11 位）" : "联系电话（留空保持不变）"}
                value={form.contact_phone}
                onChange={(v) => setForm({ ...form, contact_phone: v })}
                placeholder="13800000000"
              />
              <Field label="邮箱" value={form.contact_email} onChange={(v) => setForm({ ...form, contact_email: v })} type="email" />
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">备注</label>
                <textarea
                  className="form-control"
                  style={{ height: 80 }}
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  placeholder="如：擅长房产纠纷 / 收费标准 / 合作年限..."
                />
              </div>
            </div>
            <div className="modal-footer">
              <button type="button" className="ds-btn ds-btn-secondary" onClick={close}>取消</button>
              <button type="button" className="ds-btn ds-btn-primary" onClick={submit} disabled={!form.name.trim()}>
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, value, onChange, placeholder, type = "text", required = false }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  required?: boolean;
}) {
  return (
    <div className="form-group" style={{ marginBottom: 0 }}>
      <label className="form-label">
        {label}
        {required && <span className="req">*</span>}
      </label>
      <input
        type={type}
        className="form-control"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  );
}
