// frontend/src/pages/admin/scripts/ImportModal.tsx
import { useApiUrl } from "@refinedev/core";
import { useState, useRef } from "react";
import { X, Upload } from "lucide-react";

interface ImportResult {
  success: number;
  skipped: number;
  failed: number;
  errors: string[];
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function ImportModal({ open, onClose, onSuccess }: Props) {
  const apiUrl = useApiUrl();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  if (!open) return null;

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
      <div style={{ background: "#fff", borderRadius: 10, padding: 24, width: 480, maxWidth: "92vw" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>批量导入话术</h3>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer" }}><X size={18} /></button>
        </div>

        {!result ? (
          <>
            <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 12 }}>
              模板列顺序：话术标题 / 异议类型 / 话术内容 / 编写说明（可选）
            </p>
            <div
              onClick={() => inputRef.current?.click()}
              style={{
                border: "2px dashed #d1d5db", borderRadius: 8, padding: "32px 24px",
                textAlign: "center", cursor: "pointer", color: "#6b7280",
                background: file ? "#f0fdf4" : "#fafafa",
              }}>
              <Upload size={24} style={{ margin: "0 auto 8px", display: "block" }} />
              {file ? <span style={{ color: "#15803d" }}>{file.name}</span> : "点击或拖拽上传 .xlsx 文件"}
            </div>
            <input ref={inputRef} type="file" accept=".xlsx,.xls" style={{ display: "none" }}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)} />

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
