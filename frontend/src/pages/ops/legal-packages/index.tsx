// v0.5.5 — OPS 服务包目录后台 (PRD §20.4 「服务包定价归属」)
// 4 档平台级服务包(tenant_id IS NULL)在线改价 / 改服务内容 / 改抽成 / 启停。
// 守卫:后端 require_roles("ops","superadmin")。
import { useCustom, useCustomMutation } from "@refinedev/core";
import { Briefcase, Pencil, Save, X } from "lucide-react";
import { useState } from "react";

interface PackageItem {
  id: number;
  slug: string;
  package_type: string;
  name: string;
  description: string | null;
  price: string;
  platform_fee_rate: string;
  enabled: boolean;
  sort_order: number;
}

const TYPE_LABEL: Record<string, string> = {
  lawyer_letter: "律师函",
  mediation: "诉前调解",
  small_claims: "小额诉讼",
  full_agency: "完整代理",
};

export function OpsLegalPackagesPage() {
  const { query } = useCustom<PackageItem[]>({
    url: "ops/legal-packages",
    method: "get",
  });
  const refetch = query.refetch;
  const items = query.data?.data ?? [];

  const [editingId, setEditingId] = useState<number | null>(null);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <Briefcase className="w-6 h-6 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          法务服务包目录
        </h1>
        <span className="text-sm text-[var(--color-neutral-500)]">
          共 {items.length} 包 · 全平台共享
        </span>
      </div>

      <div
        style={{
          background: "var(--color-neutral-50)",
          border: "1px solid var(--color-neutral-200)",
          borderRadius: 6,
          padding: "10px 14px",
          fontSize: 12.5,
          color: "var(--color-neutral-600)",
          lineHeight: 1.7,
        }}
      >
        💡 <strong>服务包定价归属(PRD §20.4)</strong>:服务包是平台级目录(tenant_id IS NULL),
        所有物业租户看到的是同一份目录。定价 = 律所提交承接价 → OPS 在此后台维护 →
        全租户公开同价。<strong>不允许单租户专属价</strong>(如未来开放需走数据迁移)。
        改动会立即对所有租户生效,已下单订单的 price_quoted 不受影响(已冻结)。
      </div>

      <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg overflow-hidden">
        {query.isLoading && (
          <div className="p-12 text-center text-sm text-[var(--color-neutral-500)]">
            加载中…
          </div>
        )}
        {!query.isLoading && items.length === 0 && (
          <div className="p-12 text-center text-sm text-[var(--color-neutral-500)]">
            目录为空(请先运行 seed_demo.py)
          </div>
        )}
        {items.length > 0 && (
          <table className="w-full text-sm">
            <thead className="bg-[var(--color-neutral-50)] text-[var(--color-neutral-600)] text-xs uppercase">
              <tr>
                <th className="px-4 py-3 text-left">类型 / 名称</th>
                <th className="px-4 py-3 text-left">报价</th>
                <th className="px-4 py-3 text-left">平台抽成</th>
                <th className="px-4 py-3 text-left">状态</th>
                <th className="px-4 py-3 text-left">排序</th>
                <th className="px-4 py-3 text-left">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-neutral-100)]">
              {items.map((p) => (
                <tr key={p.id}>
                  <td className="px-4 py-3">
                    <div className="text-sm font-medium text-[var(--color-neutral-900)]">
                      {p.name}
                    </div>
                    <div className="text-xs text-[var(--color-neutral-400)] font-mono">
                      {TYPE_LABEL[p.package_type] ?? p.package_type} · {p.slug}
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono">¥{p.price}</td>
                  <td className="px-4 py-3">{(Number(p.platform_fee_rate) * 100).toFixed(0)}%</td>
                  <td className="px-4 py-3">
                    {p.enabled ? (
                      <span className="px-2 py-0.5 text-xs rounded bg-green-100 text-green-700">
                        启用
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 text-xs rounded bg-gray-100 text-gray-500">
                        停用
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">{p.sort_order}</td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => setEditingId(p.id)}
                      className="flex items-center gap-1 text-xs px-2 py-1 border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] rounded hover:bg-[var(--color-neutral-50)]"
                    >
                      <Pencil className="w-3 h-3" /> 编辑
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {editingId !== null &&
        (() => {
          const editingPkg = items.find((p) => p.id === editingId);
          if (!editingPkg) return null;
          return (
            <EditPackageModal
              pkg={editingPkg}
              onClose={() => setEditingId(null)}
              onSaved={() => {
                setEditingId(null);
                refetch();
              }}
            />
          );
        })()}
    </div>
  );
}

function EditPackageModal({
  pkg,
  onClose,
  onSaved,
}: {
  pkg: PackageItem;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(pkg.name);
  const [price, setPrice] = useState(pkg.price);
  const [feeRate, setFeeRate] = useState(pkg.platform_fee_rate);
  const [description, setDescription] = useState(pkg.description ?? "");
  const [enabled, setEnabled] = useState(pkg.enabled);
  const [sortOrder, setSortOrder] = useState(pkg.sort_order);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { mutate } = useCustomMutation();

  const handleSubmit = () => {
    setSubmitting(true);
    setError(null);
    mutate(
      {
        url: `ops/legal-packages/${pkg.id}`,
        method: "patch",
        values: {
          name,
          price,
          platform_fee_rate: feeRate,
          description: description || null,
          enabled,
          sort_order: sortOrder,
        },
      },
      {
        onSuccess: () => {
          setSubmitting(false);
          onSaved();
        },
        onError: (err: { message?: string }) => {
          setSubmitting(false);
          setError(err?.message ?? "保存失败");
        },
      },
    );
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.4)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 50,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "white",
          borderRadius: 10,
          width: 560,
          maxHeight: "90vh",
          overflow: "auto",
          padding: 24,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>编辑服务包</h2>
          <button type="button" onClick={onClose} style={{ border: "none", background: "transparent", cursor: "pointer" }}>
            <X className="w-5 h-5 text-[var(--color-neutral-500)]" />
          </button>
        </div>

        <div style={{ display: "grid", gap: 14 }}>
          <Field label="名称">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="ds-input"
              style={{ width: "100%" }}
            />
          </Field>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <Field label="报价(元)">
              <input
                type="number"
                step="0.01"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                className="ds-input"
                style={{ width: "100%" }}
              />
            </Field>
            <Field label="平台抽成率(0–1)">
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={feeRate}
                onChange={(e) => setFeeRate(e.target.value)}
                className="ds-input"
                style={{ width: "100%" }}
              />
            </Field>
          </div>

          <Field label="服务内容描述(支持换行)">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={8}
              className="ds-input"
              style={{ width: "100%", fontFamily: "inherit", lineHeight: 1.6 }}
              placeholder="说明服务流程、含什么、时效..."
            />
          </Field>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <Field label="启用">
              <label style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(e) => setEnabled(e.target.checked)}
                />
                <span style={{ fontSize: 13 }}>{enabled ? "对租户可见" : "暂时停用"}</span>
              </label>
            </Field>
            <Field label="排序(数字小靠前)">
              <input
                type="number"
                min="0"
                value={sortOrder}
                onChange={(e) => setSortOrder(Number(e.target.value))}
                className="ds-input"
                style={{ width: "100%" }}
              />
            </Field>
          </div>

          {error && (
            <div style={{ color: "var(--color-danger)", fontSize: 13 }}>{error}</div>
          )}

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8 }}>
            <button type="button" className="ds-btn ds-btn-secondary" onClick={onClose}>
              取消
            </button>
            <button
              type="button"
              className="ds-btn ds-btn-primary"
              onClick={handleSubmit}
              disabled={submitting}
            >
              <Save className="w-4 h-4" /> {submitting ? "保存中…" : "保存"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 4 }}>
        {label}
      </div>
      {children}
    </div>
  );
}

export default OpsLegalPackagesPage;
