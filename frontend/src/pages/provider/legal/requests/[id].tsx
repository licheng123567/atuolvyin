// §9 — 服务商法务·转化请求详情页 + 补充材料上传/下载
import { ArrowLeft, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useGo } from "@refinedev/core";
import {
  useProviderLegalRequest,
  uploadRequestMaterial,
  getMaterialDownloadUrl,
  type ProviderLegalRequestMaterial,
} from "../api";
import { STATUS_META, UNKNOWN_STATUS_META } from "./status-meta";

// ─── 文件大小上限 ─────────────────────────────────────────────────────────────
const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024; // 20 MB

// ─── 工具函数 ─────────────────────────────────────────────────────────────────
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 13.5 }}>{value}</div>
    </div>
  );
}

// ─── 主页面 ───────────────────────────────────────────────────────────────────
export function ProviderLegalRequestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const requestId = Number(id);
  const go = useGo();
  const { detail, isLoading, isError, refetch } = useProviderLegalRequest(requestId);

  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (isLoading) {
    return (
      <div style={{ padding: 24, color: "var(--color-neutral-400)" }}>加载中…</div>
    );
  }

  if (isError || !detail) {
    return (
      <div style={{ padding: 24 }}>
        <button
          type="button"
          className="ds-btn ds-btn-ghost"
          style={{ fontSize: 13, display: "inline-flex", alignItems: "center", gap: 4, marginBottom: 12 }}
          onClick={() => go({ to: "/provider/legal/requests" })}
        >
          <ArrowLeft size={14} /> 返回转化请求
        </button>
        <div className="ds-card">
          <div style={{ padding: 32, textAlign: "center", color: "var(--color-neutral-400)" }}>
            未找到请求
          </div>
        </div>
      </div>
    );
  }

  const statusMeta = STATUS_META[detail.status];

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > MAX_FILE_SIZE_BYTES) {
      alert("文件超过 20MB 上限");
      e.target.value = "";
      return;
    }

    setUploading(true);
    try {
      await uploadRequestMaterial(requestId, file);
      await refetch();
    } catch (err) {
      const uploadErr = err as { message?: string };
      alert(uploadErr.message ?? "上传失败");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDownload = async (m: ProviderLegalRequestMaterial) => {
    try {
      const url = await getMaterialDownloadUrl(requestId, m.id);
      window.open(url, "_blank");
    } catch (err) {
      const downloadErr = err as { message?: string };
      alert(downloadErr.message ?? "获取下载链接失败");
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 860 }}>
      {/* 返回链接 */}
      <button
        type="button"
        className="ds-btn ds-btn-ghost"
        style={{ fontSize: 13, display: "inline-flex", alignItems: "center", gap: 4, marginBottom: 12 }}
        onClick={() => go({ to: "/provider/legal/requests" })}
      >
        <ArrowLeft size={14} /> 返回转化请求
      </button>

      {/* 顶部标题行 */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>转化请求详情</h1>
        {/* 审批状态 Badge */}
        {statusMeta ? (
          <span
            className="ds-badge"
            style={{ background: statusMeta.background, color: statusMeta.color }}
          >
            {statusMeta.label}
          </span>
        ) : (
          <span
            className="ds-badge"
            style={{ background: UNKNOWN_STATUS_META.background, color: UNKNOWN_STATUS_META.color }}
          >
            {detail.status}
          </span>
        )}
        {/* 订单状态 Badge */}
        <span className="ds-badge ds-badge-blue">
          {detail.order_status ?? "未生成"}
        </span>
      </div>

      {/* 请求信息卡 */}
      <div className="ds-card" style={{ marginBottom: 16 }}>
        <div style={{ padding: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>请求信息</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px 24px" }}>
            <Field
              label="案件"
              value={`${detail.owner_name ?? "—"} · ${detail.project_name ?? "—"}`}
            />
            <Field
              label="欠费金额"
              value={detail.amount_owed ? `¥${detail.amount_owed}` : "—"}
            />
            <Field
              label="提交时间"
              value={detail.created_at.slice(0, 10)}
            />
          </div>
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 2 }}>申请理由</div>
            <div style={{ fontSize: 13.5, whiteSpace: "pre-wrap" }}>
              {detail.reason ?? "—"}
            </div>
          </div>
          {detail.reviewer_note && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 2 }}>审批意见</div>
              <div style={{ fontSize: 13.5, whiteSpace: "pre-wrap" }}>{detail.reviewer_note}</div>
            </div>
          )}
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 2 }}>订单高阶状态</div>
            <div style={{ fontSize: 13.5 }}>
              {detail.order_status ?? "未生成（物业审批通过后由物业法务生成）"}
            </div>
          </div>
        </div>
      </div>

      {/* 补充材料卡 */}
      <div className="ds-card">
        <div style={{ padding: 16 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>补充材料</div>
            <button
              type="button"
              className="ds-btn ds-btn-primary ds-btn-sm"
              disabled={uploading}
              onClick={handleUploadClick}
              style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
            >
              <Upload size={14} />
              {uploading ? "上传中…" : "上传材料"}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept=".pdf,.png,.jpg,.jpeg"
              style={{ display: "none" }}
              onChange={(e) => { void handleFileChange(e); }}
            />
          </div>

          {detail.materials.length === 0 ? (
            <div
              style={{
                border: "2px dashed var(--color-neutral-300, #D1D5DB)",
                borderRadius: 8,
                padding: "32px 24px",
                textAlign: "center",
                color: "var(--color-neutral-400)",
                fontSize: 13,
              }}
            >
              点击右上角『上传材料』按钮上传（PDF / 图片，单文件 ≤ 20MB）
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>文件名</th>
                    <th>大小</th>
                    <th>上传时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.materials.map((m) => (
                    <tr key={m.id}>
                      <td>{m.filename}</td>
                      <td>
                        {m.size_bytes != null ? formatFileSize(m.size_bytes) : "—"}
                      </td>
                      <td>{m.created_at.slice(0, 10)}</td>
                      <td>
                        <button
                          type="button"
                          className="ds-btn ds-btn-ghost ds-btn-sm"
                          onClick={() => { void handleDownload(m); }}
                        >
                          下载
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
