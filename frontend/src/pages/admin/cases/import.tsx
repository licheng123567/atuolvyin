// 1:1 还原 ui/admin.html#a-import 业主名单导入
// v0.6.0 — 修复「点击选择文件」无反应:加 ref input + 拖拽 + CSV 解析填表格
import { useCreate, useGo, useList } from "@refinedev/core";
import { CheckCircle, Download, Upload as UploadIcon } from "lucide-react";
import { useRef, useState } from "react";
import type { PaginatedResponse } from "../../../types";

interface ImportRow {
  name: string;
  phone: string;
  building: string;
  room: string;
  // v1.6.3 — 账单字段（不再自动按月推算）
  bill_period_start: string;  // 欠费开始日期 YYYY-MM-DD
  bill_period_end: string;    // 欠费截止日期 YYYY-MM-DD
  principal_amount: string;   // 物业费（本金）
  late_fee_amount: string;    // 违约金 / 滞纳金
  amount_owed: string;        // 欠费总额（= 物业费 + 违约金，可手填或自动算）
  arrears_reason: string;     // 欠费理由
  notes: string;
}

const EMPTY_ROW: ImportRow = {
  name: "",
  phone: "",
  building: "",
  room: "",
  bill_period_start: "",
  bill_period_end: "",
  principal_amount: "",
  late_fee_amount: "",
  amount_owed: "",
  arrears_reason: "",
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

// v0.6.0 — CSV 表头顺序(与「下载导入模板」配套)
const CSV_HEADER_ORDER: (keyof ImportRow)[] = [
  "name", "phone", "building", "room",
  "bill_period_start", "bill_period_end",
  "principal_amount", "late_fee_amount", "amount_owed",
  "arrears_reason", "notes",
];

// 浏览器原生 CSV 解析 — 不引入额外依赖
function parseCsv(text: string): ImportRow[] {
  // 去除 UTF-8 BOM(Excel 另存 CSV 常带)
  const cleaned = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
  const lines = cleaned
    .split(/\r?\n/)
    .filter((l) => l.trim());
  if (lines.length < 2) return [];
  // 跳过表头行(第一行)
  return lines.slice(1).map((line) => {
    const cells = line.match(/(?:[^,"]|"(?:[^"]|"")*")+/g) ?? [];
    const clean = cells.map((c) => c.replace(/^"|"$/g, "").replace(/""/g, '"').trim());
    const row: ImportRow = { ...EMPTY_ROW };
    CSV_HEADER_ORDER.forEach((field, idx) => {
      row[field] = clean[idx] ?? "";
    });
    return row;
  });
}

export function CaseImportPage() {
  const go = useGo();
  const [rows, setRows] = useState<ImportRow[]>([{ ...EMPTY_ROW }]);
  const [lastImport, setLastImport] = useState<LastImportSummary | null>(null);
  const [projectId, setProjectId] = useState<number | "">("");
  const [error, setError] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [draggingOver, setDraggingOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleFile(f: File | null) {
    setFileError(null);
    if (!f) return;
    const name = f.name.toLowerCase();
    if (name.endsWith(".xlsx") || name.endsWith(".xls")) {
      setFileError(
        ".xlsx 暂不支持浏览器直接解析 — 请把表另存为 .csv(UTF-8)后再上传,或用「手工录入」表格逐行录入。",
      );
      return;
    }
    if (!name.endsWith(".csv")) {
      setFileError("仅支持 .csv / .xlsx 文件");
      return;
    }
    try {
      const text = await f.text();
      const parsed = parseCsv(text);
      if (parsed.length === 0) {
        setFileError("CSV 内容为空或仅含表头");
        return;
      }
      // 至少一行有姓名 + 手机才填到表格
      const filtered = parsed.filter((r) => r.name && r.phone);
      if (filtered.length === 0) {
        setFileError("未找到有效数据行(姓名 + 手机号必填)");
        return;
      }
      setRows(filtered);
    } catch (e) {
      setFileError(`解析失败:${(e as Error).message}`);
    }
  }

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
      .map((r) => {
        const principal = r.principal_amount ? Number(r.principal_amount.trim()) : 0;
        const lateFee = r.late_fee_amount ? Number(r.late_fee_amount.trim()) : 0;
        // 欠费总额：手填优先，否则自动 = 物业费 + 违约金
        const totalManual = r.amount_owed ? r.amount_owed.trim() : "";
        const total = totalManual !== "" ? totalManual : String(principal + lateFee);
        // 月数：根据账单起止自动算（仅传给后端做参考；不影响展示）
        let months: number | null = null;
        if (r.bill_period_start && r.bill_period_end) {
          const s = new Date(r.bill_period_start);
          const e = new Date(r.bill_period_end);
          if (!Number.isNaN(s.getTime()) && !Number.isNaN(e.getTime())) {
            months = Math.max(1, Math.round((e.getFullYear() - s.getFullYear()) * 12 + (e.getMonth() - s.getMonth())) + 1);
          }
        }
        return {
          name: r.name.trim(),
          phone: r.phone.trim(),
          building: r.building.trim() || null,
          room: r.room.trim() || null,
          // v1.6.3 — 账单字段（导入时录入，不再按月自动推算）
          bill_period_start: r.bill_period_start || null,
          bill_period_end: r.bill_period_end || null,
          principal_amount: r.principal_amount ? r.principal_amount.trim() : null,
          late_fee_amount: r.late_fee_amount ? r.late_fee_amount.trim() : null,
          amount_owed: total || null,
          arrears_reason: r.arrears_reason.trim() || null,
          months_overdue: months,
          notes: r.notes.trim() || null,
        };
      });

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

      {/* v0.6.0 — Upload zone:支持点击 + 拖拽,CSV 浏览器解析 → 填表格 */}
      <div className="ds-card section-gap">
        <div className="card-body">
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              void handleFile(f);
              if (e.target) e.target.value = "";  // 允许重复选同一文件
            }}
          />
          <div
            className="upload-zone"
            style={{
              cursor: "pointer",
              border: `2px dashed ${draggingOver ? "#1A56DB" : "#cbd5e1"}`,
              background: draggingOver ? "#eff6ff" : "transparent",
              transition: "all 120ms ease",
            }}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDraggingOver(true);
            }}
            onDragLeave={() => setDraggingOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDraggingOver(false);
              const f = e.dataTransfer.files?.[0] ?? null;
              void handleFile(f);
            }}
          >
            <UploadIcon
              size={48}
              strokeWidth={1.5}
              color="#9ca3af"
              style={{ margin: "0 auto 12px", display: "block" }}
            />
            <div style={{ fontSize: 15, fontWeight: 600, color: "#374151", marginBottom: 6 }}>
              拖拽 Excel / CSV 文件到此区域
            </div>
            <div style={{ fontSize: 13, color: "#9ca3af" }}>
              或 <span style={{ color: "#1A56DB" }}>点击选择文件</span>
            </div>
            <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 8 }}>
              支持 .csv (UTF-8) · 最大 100MB · 必须包含:姓名、手机号、楼栋、欠费开始日期、欠费截止日期、物业费、违约金、欠费总额(= 物业费 + 违约金)
            </div>
            {fileError && (
              <div
                style={{
                  marginTop: 10,
                  padding: "6px 10px",
                  background: "#fef2f2",
                  color: "#dc2626",
                  borderRadius: 6,
                  fontSize: 12,
                }}
              >
                {fileError}
              </div>
            )}
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
                    <th>房号（坐落）</th>
                    <th>欠费开始日期</th>
                    <th>欠费截止日期</th>
                    <th>物业费 ¥</th>
                    <th>违约金 ¥</th>
                    <th>欠费总额 ¥</th>
                    <th>欠费理由</th>
                    <th>备注</th>
                    <th style={{ width: 60 }} />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, idx) => {
                    const fieldList: { name: keyof ImportRow; type: "text" | "number" | "date" | "select"; placeholder?: string; minWidth?: number }[] = [
                      { name: "name", type: "text", placeholder: "张三" },
                      { name: "phone", type: "text", placeholder: "138xxxx" },
                      { name: "building", type: "text", placeholder: "1栋" },
                      { name: "room", type: "text", placeholder: "101" },
                      { name: "bill_period_start", type: "date" },
                      { name: "bill_period_end", type: "date" },
                      { name: "principal_amount", type: "number", placeholder: "本金" },
                      { name: "late_fee_amount", type: "number", placeholder: "违约金" },
                      { name: "amount_owed", type: "number", placeholder: "自动 = 本金+违约金" },
                      { name: "arrears_reason", type: "select" },
                      { name: "notes", type: "text", placeholder: "失联/拒缴等", minWidth: 140 },
                    ];
                    return (
                      <tr key={idx}>
                        {fieldList.map((f) => (
                          <td key={f.name}>
                            {f.type === "select" ? (
                              <select
                                value={row[f.name]}
                                onChange={(e) => updateRow(idx, f.name, e.target.value)}
                                className="form-control"
                                style={{ padding: "6px 8px", fontSize: 13, minWidth: 110 }}
                              >
                                <option value="">— 选择 —</option>
                                <option value="经济困难">经济困难</option>
                                <option value="服务质量异议">服务质量异议</option>
                                <option value="房屋空置">房屋空置</option>
                                <option value="租客拖欠">租客拖欠</option>
                                <option value="其他">其他</option>
                              </select>
                            ) : (
                              <input
                                type={f.type}
                                value={row[f.name]}
                                onChange={(e) => updateRow(idx, f.name, e.target.value)}
                                className="form-control"
                                style={{ padding: "6px 10px", fontSize: 13, minWidth: f.minWidth }}
                                placeholder={f.placeholder}
                              />
                            )}
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
                    );
                  })}
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
