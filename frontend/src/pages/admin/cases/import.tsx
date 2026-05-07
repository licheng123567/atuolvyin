// 1:1 还原 ui/admin.html#a-import 业主名单导入
import { useCreate, useGo, useList } from "@refinedev/core";
import { CheckCircle, Download, Upload as UploadIcon } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";

interface ImportRow {
  name: string;
  phone: string;
  building: string;
  room: string;
  amount_owed: string;
  months_overdue: string;
  notes: string;
}

const EMPTY_ROW: ImportRow = {
  name: "",
  phone: "",
  building: "",
  room: "",
  amount_owed: "",
  months_overdue: "",
  notes: "",
};

interface LastImportSummary {
  added: number;
  updated: number;
  skipped: number;
  total: number;
  preview: { name: string; room: string; phone: string; amount: string; status: "added" | "updated" | "skipped" }[];
}

interface ProjectOption {
  id: number;
  name: string;
  case_count: number;
}

export function CaseImportPage() {
  const go = useGo();
  const [rows, setRows] = useState<ImportRow[]>([{ ...EMPTY_ROW }]);
  const [lastImport, setLastImport] = useState<LastImportSummary | null>(null);
  const [projectId, setProjectId] = useState<number | "">("");
  const [error, setError] = useState<string | null>(null);

  const { query: projectQuery } = useList<ProjectOption>({
    resource: "admin/projects",
    pagination: { currentPage: 1, pageSize: 100 },
  });
  const projectsRaw = projectQuery.data?.data;
  const projects: ProjectOption[] =
    (projectsRaw as unknown as PaginatedResponse<ProjectOption>)?.items ??
    (projectsRaw as ProjectOption[] | undefined) ??
    [];

  const { mutate: importCases, mutation: importMutation } = useCreate();
  const isPending = importMutation.isPending;

  function updateRow(idx: number, field: keyof ImportRow, value: string) {
    setRows((prev) =>
      prev.map((r, i) => (i === idx ? { ...r, [field]: value } : r)),
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
    setError(null);
    if (projectId === "") {
      setError("请先选择导入到哪个项目");
      return;
    }
    const payload = rows
      .filter((r) => r.name && r.phone)
      .map((r) => ({
        name: r.name.trim(),
        phone: r.phone.trim(),
        building: r.building.trim() || null,
        room: r.room.trim() || null,
        amount_owed: r.amount_owed ? r.amount_owed.trim() : null,
        months_overdue: r.months_overdue
          ? parseInt(r.months_overdue, 10) || null
          : null,
        notes: r.notes.trim() || null,
      }));

    importCases(
      {
        resource: "admin/cases/import",
        values: { project_id: projectId, rows: payload },
      },
      {
        onSuccess: (data) => {
          const d = data.data as {
            imported?: number;
            updated?: number;
            skipped?: number;
            errors?: string[];
          };
          const total = (d.imported ?? 0) + (d.updated ?? 0) + (d.skipped ?? 0);
          setLastImport({
            added: d.imported ?? 0,
            updated: d.updated ?? 0,
            skipped: d.skipped ?? 0,
            total,
            preview: payload.slice(0, 5).map((r, i) => ({
              name: r.name,
              room:
                r.building && r.room
                  ? `${r.building}-${r.room}`
                  : r.building ?? r.room ?? "—",
              phone: r.phone.replace(/(\d{3})\d{4}(\d{4})/, "$1****$2"),
              amount: r.amount_owed ? `¥${Number(r.amount_owed).toLocaleString()}` : "—",
              status: i < (d.imported ?? 0) ? "added" : "updated",
            })),
          });
          setRows([{ ...EMPTY_ROW }]);
        },
      },
    );
  }

  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">业主名单导入</h1>
          <div className="page-subtitle">支持手工逐行录入，或批量导入 Excel/CSV</div>
        </div>
        <button type="button" className="ds-btn ds-btn-secondary">
          <Download className="w-3.5 h-3.5" />
          下载导入模板
        </button>
      </div>

      {/* 项目选择器（v1.4 — 案件归属项目） */}
      <div className="ds-card section-gap">
        <div className="card-body" style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <label className="form-label" style={{ marginBottom: 0 }}>
            导入到项目<span className="req">*</span>
          </label>
          <select
            className="form-control"
            style={{ width: 320 }}
            value={projectId}
            onChange={(e) =>
              setProjectId(e.target.value === "" ? "" : Number(e.target.value))
            }
          >
            <option value="">— 选择项目 —</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}（已有 {p.case_count} 个案件）
              </option>
            ))}
          </select>
          <button
            type="button"
            className="ds-btn ds-btn-ghost"
            onClick={() => go({ to: "/admin/projects" })}
          >
            管理项目
          </button>
          {projects.length === 0 && (
            <span style={{ fontSize: 13, color: "#d97706" }}>
              ⚠ 还没有项目，请先去「项目管理」创建
            </span>
          )}
        </div>
      </div>

      {/* Upload zone (visual; v1.x 接 Excel 解析) */}
      <div className="ds-card section-gap">
        <div className="card-body">
          <div className="upload-zone">
            <UploadIcon
              size={48}
              strokeWidth={1.5}
              color="#9ca3af"
              style={{ margin: "0 auto 12px", display: "block" }}
            />
            <div
              style={{
                fontSize: 15,
                fontWeight: 600,
                color: "#374151",
                marginBottom: 6,
              }}
            >
              拖拽 Excel / CSV 文件到此区域
            </div>
            <div style={{ fontSize: 13, color: "#9ca3af" }}>
              或 <span style={{ color: "#1A56DB", cursor: "pointer" }}>点击选择文件</span>
            </div>
            <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 8 }}>
              支持 .xlsx / .csv · 最大 100MB · 必须包含：姓名、房号、手机号、欠费金额
            </div>
          </div>
        </div>
      </div>

      {/* 手工逐行录入 */}
      <div className="ds-card section-gap">
        <div className="card-header">
          <span className="card-title">或手工录入</span>
          <span className="text-sm text-muted">
            已填 {rows.filter((r) => r.name && r.phone).length} 条
          </span>
        </div>
        <div className="card-body">
          <form onSubmit={handleSubmit}>
            <div className="table-wrap" style={{ marginBottom: 16 }}>
              <table>
                <thead>
                  <tr>
                    <th>姓名*</th>
                    <th>手机号*</th>
                    <th>楼栋*</th>
                    <th>房间</th>
                    <th>欠费金额</th>
                    <th>逾期月数</th>
                    <th>欠费情况说明</th>
                    <th style={{ width: 60 }} />
                  </tr>
                </thead>
                <tbody>
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
                          "notes",
                        ] as (keyof ImportRow)[]
                      ).map((field) => (
                        <td key={field}>
                          <input
                            type={
                              field === "amount_owed" || field === "months_overdue"
                                ? "number"
                                : "text"
                            }
                            value={row[field]}
                            onChange={(e) =>
                              updateRow(idx, field, e.target.value)
                            }
                            className="form-control"
                            style={{
                              padding: "6px 10px",
                              fontSize: 13,
                              minWidth: field === "notes" ? 180 : undefined,
                            }}
                            placeholder={
                              field === "name"
                                ? "张三"
                                : field === "phone"
                                  ? "138xxxx"
                                  : field === "building"
                                    ? "1栋"
                                    : field === "notes"
                                      ? "如：经济困难/失联/拒缴"
                                      : ""
                            }
                          />
                        </td>
                      ))}
                      <td>
                        <button
                          type="button"
                          onClick={() => removeRow(idx)}
                          disabled={rows.length === 1}
                          className="ds-btn ds-btn-ghost ds-btn-sm"
                          style={{ color: "#e02424" }}
                        >
                          删除
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {error && (
              <div
                style={{
                  background: "var(--color-danger-light)",
                  color: "var(--color-danger)",
                  padding: "8px 12px",
                  borderRadius: 6,
                  fontSize: 13,
                  marginBottom: 12,
                }}
              >
                {error}
              </div>
            )}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <button
                type="button"
                onClick={addRow}
                className="ds-btn ds-btn-ghost"
              >
                + 添加一行
              </button>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="button"
                  onClick={() => go({ to: "/admin/cases" })}
                  className="ds-btn ds-btn-secondary"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={
                    isPending ||
                    rows.filter((r) => r.name && r.phone).length === 0
                  }
                  className="ds-btn ds-btn-primary"
                >
                  {isPending
                    ? "导入中…"
                    : `导入 ${rows.filter((r) => r.name && r.phone).length} 条`}
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>

      {/* 上次导入结果 */}
      {lastImport && (
        <div className="ds-card">
          <div className="card-header">
            <span className="card-title">上次导入结果</span>
            <span className="ds-badge ds-badge-green">
              <CheckCircle className="w-3 h-3" />
              导入成功
            </span>
          </div>
          <div className="card-body">
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(4,1fr)",
                gap: 12,
                marginBottom: 20,
              }}
            >
              <ImportStat label="新增" value={lastImport.added} bg="#f0fdf4" color="#057a55" />
              <ImportStat label="更新" value={lastImport.updated} bg="#eff6ff" color="#1A56DB" />
              <ImportStat
                label="跳过重复"
                value={lastImport.skipped}
                bg="#fffbeb"
                color="#d97706"
              />
              <ImportStat label="总计" value={lastImport.total} bg="#f3f4f6" color="#374151" />
            </div>

            {lastImport.preview.length > 0 && (
              <>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
                  数据预览（前 {lastImport.preview.length} 条）
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>姓名</th>
                        <th>房号</th>
                        <th>手机号</th>
                        <th>欠费金额</th>
                        <th>状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lastImport.preview.map((r, i) => (
                        <tr key={i}>
                          <td>{r.name}</td>
                          <td>{r.room}</td>
                          <td>{r.phone}</td>
                          <td>{r.amount}</td>
                          <td>
                            <span
                              className={
                                r.status === "added"
                                  ? "ds-badge ds-badge-green"
                                  : r.status === "updated"
                                    ? "ds-badge ds-badge-blue"
                                    : "ds-badge ds-badge-gray"
                              }
                            >
                              {r.status === "added"
                                ? "新增"
                                : r.status === "updated"
                                  ? "更新"
                                  : "跳过"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ImportStat({
  label,
  value,
  bg,
  color,
}: {
  label: string;
  value: number;
  bg: string;
  color: string;
}) {
  return (
    <div
      style={{
        textAlign: "center",
        padding: 12,
        background: bg,
        borderRadius: 8,
      }}
    >
      <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 12, color: "#6b7280" }}>{label}</div>
    </div>
  );
}
