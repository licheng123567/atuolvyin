// frontend/src/pages/admin/scripts/ImportModal.tsx
// v1.5.7 — 1:1 还原 ui/admin.html 导入弹窗：下载模板 + 上传后预览前 5 行
import { useApiUrl } from "@refinedev/core";
import { useRef, useState } from "react";
import { Download, Upload, X } from "lucide-react";
import { exportToCsv } from "../../../lib/csv";

interface ImportResult {
  success: number;
  skipped: number;
  failed: number;
  errors: string[];
}

type PreviewKey = "title" | "intent" | "content" | "notes";
interface PreviewRow extends Record<string, unknown> {
  title: string;
  intent: string;
  content: string;
  notes: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const TEMPLATE_HEADER: { key: PreviewKey; label: string }[] = [
  { key: "title", label: "话术标题" },
  { key: "intent", label: "异议类型" },
  { key: "content", label: "话术内容" },
  { key: "notes", label: "编写说明" },
];

const TEMPLATE_SAMPLE: PreviewRow[] = [
  { title: "经济困难·分期方案", intent: "经济困难", content: "理解您的困难，我们可以为您申请 3 个月分期缴费方案，每月只需还 ¥820...", notes: "适用于明确表达经济困难的业主" },
  { title: "破冰·标准开场", intent: "破冰", content: "您好，我是 XX 物业的客服，今天联系您是想跟您核对一下您当前的物业费缴纳情况...", notes: "首次电话标准开场" },
];

function downloadTemplate() {
  exportToCsv("话术导入模板.csv", TEMPLATE_HEADER, TEMPLATE_SAMPLE);
}

async function parsePreview(file: File): Promise<PreviewRow[]> {
  // 简易 CSV 解析（生产可换 xlsx，这里 mock 模板与最常见 CSV 兼容）
  const isCsv = file.name.toLowerCase().endsWith(".csv");
  if (!isCsv) {
    // xlsx：浏览器无内置解析；保留占位提示，仍可上传
    return [];
  }
  const text = await file.text();
  const lines = text.replace(/^\uFEFF/, "").split(/\r?\n/).filter((l) => l.trim());
  const rows = lines.slice(1, 6).map((line) => {
    // 简易：不处理 quoted-comma（与 exportToCsv 输出兼容即可）
    const cells = line.match(/(?:[^,"]|"(?:[^"]|"")*")+/g) ?? [];
    const clean = cells.map((c) => c.replace(/^"|"$/g, "").replace(/""/g, '"'));
    return {
      title: clean[0] ?? "",
      intent: clean[1] ?? "",
      content: clean[2] ?? "",
      notes: clean[3] ?? "",
    };
  });
  return rows;
}

export function ImportModal({ open, onClose, onSuccess }: Props) {
  const apiUrl = useApiUrl();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PreviewRow[]>([]);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  if (!open) return null;

  async function handleFileSelect(f: File | null) {
    setFile(f);
    setPreview([]);
    setError("");
    if (f) {
      try {
        const rows = await parsePreview(f);
        setPreview(rows);
      } catch {
        setPreview([]);
      }
    }
  }

  const handleImport = async () => {
    if (!file) return;
    setError("");
    setLoading(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const token = localStorage.getItem("autoluyin_token") ?? "";
      const resp = await fetch(`${apiUrl}/admin/scripts/import`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      const body = await resp.json() as Record<string, unknown>;
      if (!resp.ok) {
        const detail = body?.detail as { message?: string } | undefined;
        setError(detail?.message ?? "导入失败");
      } else {
        const importResult = body as unknown as ImportResult;
        setResult(importResult);
        if (importResult.success > 0) onSuccess();
      }
    } catch {
      setError("网络错误，请重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 60 }}>
      <div style={{ background: "#fff", borderRadius: 10, padding: 24, width: 560, maxWidth: "92vw", maxHeight: "90vh", overflowY: "auto" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>批量导入话术</h3>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer" }}><X size={18} /></button>
        </div>

        {!result ? (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, fontSize: 13, color: "#6b7280" }}>
              <span>模板列顺序：话术标题 / 异议类型 / 话术内容 / 编写说明（可选）</span>
              <button
                type="button"
                onClick={downloadTemplate}
                style={{
                  display: "inline-flex", alignItems: "center", gap: 4,
                  padding: "4px 10px", fontSize: 12,
                  background: "var(--color-primary-light, #eff6ff)", color: "var(--color-primary)",
                  border: "1px solid var(--color-primary-light, #dbeafe)", borderRadius: 4, cursor: "pointer",
                }}
              >
                <Download size={12} /> 下载模板
              </button>
            </div>
            <div
              onClick={() => inputRef.current?.click()}
              style={{
                border: "2px dashed #d1d5db", borderRadius: 8, padding: "32px 24px",
                textAlign: "center", cursor: "pointer", color: "#6b7280",
                background: file ? "#f0fdf4" : "#fafafa",
              }}>
              <Upload size={24} style={{ margin: "0 auto 8px", display: "block" }} />
              {file ? <span style={{ color: "#15803d" }}>{file.name}</span> : "点击或拖拽上传 .xlsx / .csv 文件"}
            </div>
            <input ref={inputRef} type="file" accept=".xlsx,.xls,.csv" style={{ display: "none" }}
              onChange={(e) => void handleFileSelect(e.target.files?.[0] ?? null)} />

            {/* 预览前 5 行 — 仅 CSV 可解析；xlsx 提示直接上传 */}
            {file && preview.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 6 }}>
                  预览前 {preview.length} 行（共上传文件按服务端为准）：
                </div>
                <div style={{ border: "1px solid #e5e7eb", borderRadius: 6, overflow: "hidden", maxHeight: 200, overflowY: "auto" }}>
                  <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
                    <thead style={{ background: "#f9fafb" }}>
                      <tr>
                        {TEMPLATE_HEADER.map((h) => (
                          <th key={h.key} style={{ padding: "6px 8px", textAlign: "left", fontWeight: 500, color: "#6b7280", borderBottom: "1px solid #e5e7eb" }}>
                            {h.label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {preview.map((row, i) => (
                        <tr key={i} style={{ borderTop: i > 0 ? "1px solid #f3f4f6" : "none" }}>
                          {TEMPLATE_HEADER.map((h) => (
                            <td key={h.key} style={{ padding: "6px 8px", color: "#374151", verticalAlign: "top", maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={String(row[h.key] ?? "")}>
                              {String(row[h.key] ?? "") || "—"}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            {file && preview.length === 0 && file.name.toLowerCase().endsWith(".xlsx") && (
              <p style={{ fontSize: 12, color: "#6b7280", marginTop: 8 }}>
                .xlsx 文件无法在浏览器预览；点「确认导入」由服务端解析后展示结果。
              </p>
            )}

            {error && <p style={{ color: "#ef4444", fontSize: 13, marginTop: 8 }}>{error}</p>}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
              <button onClick={onClose}
                style={{ padding: "8px 16px", background: "#f9fafb", border: "1px solid #d1d5db", borderRadius: 6, cursor: "pointer" }}>取消</button>
              <button onClick={handleImport} disabled={!file || loading}
                style={{ padding: "8px 16px", background: "var(--color-primary)", color: "#fff", border: "none", borderRadius: 6, cursor: (!file || loading) ? "not-allowed" : "pointer" }}>
                {loading ? "导入中…" : "确认导入"}
              </button>
            </div>
          </>
        ) : (
          <>
            <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: 16, marginBottom: 12 }}>
              <div style={{ color: "#15803d", fontWeight: 600, marginBottom: 4 }}>导入完成</div>
              <div style={{ fontSize: 14, color: "#374151" }}>
                成功：{result.success} 条 &nbsp;|&nbsp; 跳过：{result.skipped} 条 &nbsp;|&nbsp; 失败：{result.failed} 条
              </div>
            </div>
            {result.errors.length > 0 && (
              <ul style={{ fontSize: 12, color: "#ef4444", paddingLeft: 16, margin: "0 0 12px" }}>
                {result.errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            )}
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button onClick={onClose}
                style={{ padding: "8px 16px", background: "var(--color-primary)", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer" }}>关闭</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
