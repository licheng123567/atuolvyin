// Sprint 16.2 — 律所池管理（PRD §20.4）— ops 角色
import { useCustom, useCustomMutation } from "@refinedev/core";
import { Building2, Plus, Search, Star, Trash2, Users } from "lucide-react";
import { useState } from "react";

interface Lawyer {
  id: number;
  name: string;
  license_no: string | null;
  phone: string | null;
  is_active: boolean;
}

interface LawFirm {
  id: number;
  name: string;
  license_no: string | null;
  region: string | null;
  contact_name: string | null;
  contact_phone: string | null;
  enabled: boolean;
  accepting_orders: boolean;
  rating_avg: string;
  completed_orders: number;
  specialties: string[] | null;
  lawyers: Lawyer[];
}

interface ListResp {
  items: LawFirm[];
  total: number;
}

export function OpsLawFirmsPage() {
  const [q, setQ] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const { query, refetch } = useCustom<ListResp>({
    url: "ops/law-firms",
    method: "get",
    config: { query: { q: q || undefined, page: 1, page_size: 50 } },
  });

  const { mutate: deleteFirm } = useCustomMutation();

  const items = query.data?.data?.items ?? [];
  const total = query.data?.data?.total ?? 0;

  const onDelete = (id: number) => {
    if (!confirm("确认停用该律所？将不再分配新订单。")) return;
    deleteFirm(
      { url: `ops/law-firms/${id}`, method: "delete", values: {} },
      { onSuccess: () => refetch() },
    );
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <Building2 className="w-6 h-6 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          律所池管理
        </h1>
        <span className="text-sm text-[var(--color-neutral-500)]">
          共 {total} 家
        </span>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          className="ml-auto flex items-center gap-1 px-3 py-1.5 text-sm bg-[var(--color-primary)] text-white rounded hover:opacity-90"
        >
          <Plus className="w-4 h-4" /> 新增律所
        </button>
      </div>

      <div className="flex items-center gap-2 bg-white border border-[var(--color-neutral-200)] rounded-lg px-4 py-3">
        <Search className="w-4 h-4 text-[var(--color-neutral-400)]" />
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="搜索律所名称或执业证号"
          className="flex-1 text-sm outline-none"
        />
      </div>

      <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg overflow-hidden">
        {query.isLoading && (
          <div className="p-12 text-center text-sm text-[var(--color-neutral-500)]">
            加载中…
          </div>
        )}
        {!query.isLoading && items.length === 0 && (
          <div className="p-12 text-center text-sm text-[var(--color-neutral-500)]">
            暂无律所
          </div>
        )}
        {items.map((firm) => (
          <div
            key={firm.id}
            className="border-b border-[var(--color-neutral-100)] last:border-0"
          >
            <div className="px-4 py-3 flex items-start gap-3">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium">{firm.name}</span>
                  {firm.enabled ? (
                    firm.accepting_orders ? (
                      <span className="text-xs px-2 py-0.5 rounded bg-green-100 text-green-700">
                        接单中
                      </span>
                    ) : (
                      <span className="text-xs px-2 py-0.5 rounded bg-amber-100 text-amber-700">
                        暂停接单
                      </span>
                    )
                  ) : (
                    <span className="text-xs px-2 py-0.5 rounded bg-red-50 text-red-600">
                      已停用
                    </span>
                  )}
                  <div className="flex items-center gap-0.5 ml-2">
                    <Star className="w-3 h-3 text-amber-400 fill-amber-400" />
                    <span className="text-xs text-[var(--color-neutral-600)]">
                      {firm.rating_avg}
                    </span>
                  </div>
                </div>
                <div className="text-xs text-[var(--color-neutral-500)] flex flex-wrap gap-3">
                  {firm.region && <span>📍 {firm.region}</span>}
                  {firm.license_no && <span>证号 {firm.license_no}</span>}
                  {firm.contact_name && <span>{firm.contact_name}</span>}
                  {firm.contact_phone && <span>{firm.contact_phone}</span>}
                  <span>已完成 {firm.completed_orders} 单</span>
                </div>
                {firm.specialties && firm.specialties.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {firm.specialties.map((s) => (
                      <span
                        key={s}
                        className="text-[11px] px-1.5 py-0.5 bg-[var(--color-neutral-100)] text-[var(--color-neutral-700)] rounded"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={() =>
                  setExpandedId(expandedId === firm.id ? null : firm.id)
                }
                className="flex items-center gap-1 px-2 py-1 text-xs text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-50)] rounded"
              >
                <Users className="w-3.5 h-3.5" />
                {firm.lawyers.filter((l) => l.is_active).length} 位律师
              </button>
              <button
                type="button"
                onClick={() => onDelete(firm.id)}
                disabled={!firm.enabled}
                className="text-red-500 hover:bg-red-50 p-1.5 rounded disabled:opacity-30"
                title="停用"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
            {expandedId === firm.id && (
              <div className="bg-[var(--color-neutral-50)] px-6 py-3">
                <h4 className="text-xs font-semibold text-[var(--color-neutral-600)] mb-2">
                  执业律师
                </h4>
                {firm.lawyers.length === 0 && (
                  <div className="text-xs text-[var(--color-neutral-400)]">
                    暂无律师
                  </div>
                )}
                <ul className="space-y-1">
                  {firm.lawyers.map((l) => (
                    <li
                      key={l.id}
                      className={`text-xs flex items-center gap-2 ${
                        l.is_active ? "" : "opacity-50"
                      }`}
                    >
                      <span className="font-medium">{l.name}</span>
                      {l.license_no && (
                        <span className="text-[var(--color-neutral-500)]">
                          证号 {l.license_no}
                        </span>
                      )}
                      {l.phone && (
                        <span className="text-[var(--color-neutral-500)]">
                          {l.phone}
                        </span>
                      )}
                      {!l.is_active && (
                        <span className="text-red-500">已停用</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>

      {createOpen && (
        <CreateLawFirmModal
          onClose={() => setCreateOpen(false)}
          onSuccess={() => {
            setCreateOpen(false);
            refetch();
          }}
        />
      )}
    </div>
  );
}

function CreateLawFirmModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [name, setName] = useState("");
  const [licenseNo, setLicenseNo] = useState("");
  const [region, setRegion] = useState("");
  const [contactName, setContactName] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const { mutate, mutation } = useCustomMutation();

  const submit = () => {
    if (name.trim().length < 2) {
      alert("律所名称至少 2 个字");
      return;
    }
    mutate(
      {
        url: "ops/law-firms",
        method: "post",
        values: {
          name: name.trim(),
          license_no: licenseNo.trim() || undefined,
          region: region.trim() || undefined,
          contact_name: contactName.trim() || undefined,
          contact_phone: contactPhone.trim() || undefined,
        },
      },
      {
        onSuccess,
        onError: (err) => alert(`创建失败：${(err as { message?: string }).message ?? "请重试"}`),
      },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-md p-6">
        <h3 className="text-base font-semibold mb-4">新增律所</h3>
        <div className="space-y-3">
          <Field label="律所名称 *" value={name} onChange={setName} />
          <Field label="执业证号" value={licenseNo} onChange={setLicenseNo} />
          <Field label="所在地区" value={region} onChange={setRegion} />
          <Field label="联系人" value={contactName} onChange={setContactName} />
          <Field label="联系电话" value={contactPhone} onChange={setContactPhone} />
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-300)] rounded"
          >
            取消
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={mutation.isPending}
            className="px-4 py-1.5 text-sm bg-[var(--color-primary)] text-white rounded disabled:opacity-50"
          >
            {mutation.isPending ? "提交中…" : "创建"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label, value, onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-xs text-[var(--color-neutral-600)]">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full mt-1 px-3 py-1.5 text-sm border border-[var(--color-neutral-300)] rounded"
      />
    </label>
  );
}
