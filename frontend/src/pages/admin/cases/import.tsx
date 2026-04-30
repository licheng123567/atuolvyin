import { useCreate, useGo } from "@refinedev/core";
import { ArrowLeft, Upload } from "lucide-react";
import { useState } from "react";

interface ImportRow {
  name: string;
  phone: string;
  building: string;
  room: string;
  amount_owed: string;
  months_overdue: string;
}

const EMPTY_ROW: ImportRow = {
  name: "",
  phone: "",
  building: "",
  room: "",
  amount_owed: "",
  months_overdue: "",
};

export function CaseImportPage() {
  const go = useGo();
  const [rows, setRows] = useState<ImportRow[]>([{ ...EMPTY_ROW }]);
  const [result, setResult] = useState<{
    imported: number;
    skipped: number;
    errors: string[];
  } | null>(null);

  const { mutate: importCases, mutation: importMutation } = useCreate();
  const isPending = importMutation.isPending;

  function updateRow(idx: number, field: keyof ImportRow, value: string) {
    setRows((prev) =>
      prev.map((r, i) => (i === idx ? { ...r, [field]: value } : r))
    );
  }

  function addRow() {
    setRows((prev) => [...prev, { ...EMPTY_ROW }]);
  }

  function removeRow(idx: number) {
    setRows((prev) => prev.filter((_, i) => i !== idx));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload = rows
      .filter((r) => r.name && r.phone)
      .map((r) => ({
        name: r.name.trim(),
        phone: r.phone.trim(),
        building: r.building.trim() || null,
        room: r.room.trim() || null,
        amount_owed: r.amount_owed ? r.amount_owed.trim() : null,
        months_overdue: r.months_overdue
          ? (parseInt(r.months_overdue, 10) || null)
          : null,
      }));

    importCases(
      {
        resource: "admin/cases/import",
        values: { rows: payload },
      },
      {
        onSuccess: (data) => {
          const d = data.data as {
            imported: number;
            skipped: number;
            errors: string[];
          };
          setResult(d);
        },
      }
    );
  }

  if (result) {
    return (
      <div className="max-w-lg">
        <div
          className="p-6 bg-white border border-[var(--color-neutral-200)]"
          style={{ borderRadius: "var(--radius-lg)" }}
        >
          <h2 className="text-lg font-semibold text-[var(--color-neutral-900)] mb-4">
            导入完成
          </h2>
          <div className="space-y-2 mb-6">
            <div className="flex justify-between text-sm">
              <span className="text-[var(--color-neutral-600)]">成功导入</span>
              <span
                className="font-medium"
                style={{ color: "var(--color-success)" }}
              >
                {result.imported} 件
              </span>
            </div>
            {result.skipped > 0 && (
              <div className="flex justify-between text-sm">
                <span className="text-[var(--color-neutral-600)]">跳过</span>
                <span
                  className="font-medium"
                  style={{ color: "var(--color-warning)" }}
                >
                  {result.skipped} 件
                </span>
              </div>
            )}
            {result.errors.length > 0 && (
              <div className="mt-3">
                <p
                  className="text-sm font-medium mb-1"
                  style={{ color: "var(--color-danger)" }}
                >
                  错误详情：
                </p>
                <ul className="text-xs space-y-0.5 text-[var(--color-neutral-600)]">
                  {result.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => {
                setResult(null);
                setRows([{ ...EMPTY_ROW }]);
              }}
              className="px-4 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            >
              继续导入
            </button>
            <button
              type="button"
              onClick={() => go({ to: "/admin/cases" })}
              className="px-4 py-2 text-sm font-medium text-white"
              style={{
                background: "var(--color-primary)",
                borderRadius: "var(--radius-md)",
              }}
            >
              查看案件列表
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <button
          type="button"
          onClick={() => go({ to: "/admin/cases" })}
          className="text-[var(--color-neutral-400)] hover:text-[var(--color-neutral-700)]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex items-center gap-2">
          <Upload className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            批量导入案件
          </h1>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="bg-white border border-[var(--color-neutral-200)] overflow-hidden mb-4">
          <table className="w-full text-sm">
            <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                  姓名 *
                </th>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                  手机号 *
                </th>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                  楼栋
                </th>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                  房间
                </th>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                  欠费金额
                </th>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                  逾期月数
                </th>
                <th className="px-3 py-2 w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-neutral-100)]">
              {rows.map((row, idx) => (
                <tr key={idx}>
                  {(
                    [
                      "name",
                      "phone",
                      "building",
                      "room",
                      "amount_owed",
                      "months_overdue",
                    ] as (keyof ImportRow)[]
                  ).map((field) => (
                    <td key={field} className="px-3 py-2">
                      <input
                        type={
                          field === "amount_owed" || field === "months_overdue"
                            ? "number"
                            : "text"
                        }
                        value={row[field]}
                        onChange={(e) => updateRow(idx, field, e.target.value)}
                        className="w-full px-2 py-1 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                        style={{ borderRadius: "var(--radius-sm)" }}
                        placeholder={
                          field === "name"
                            ? "张三"
                            : field === "phone"
                              ? "138xxxx"
                              : ""
                        }
                      />
                    </td>
                  ))}
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      onClick={() => removeRow(idx)}
                      disabled={rows.length === 1}
                      className="text-[var(--color-danger)] disabled:opacity-30 text-xs"
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={addRow}
            className="text-sm text-[var(--color-primary)] hover:underline"
          >
            + 添加一行
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => go({ to: "/admin/cases" })}
              className="px-4 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            >
              取消
            </button>
            <button
              type="submit"
              disabled={isPending || rows.filter((r) => r.name && r.phone).length === 0}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
              style={{
                background: "var(--color-primary)",
                borderRadius: "var(--radius-md)",
              }}
            >
              {isPending ? "导入中…" : `导入 ${rows.filter((r) => r.name && r.phone).length} 条`}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
