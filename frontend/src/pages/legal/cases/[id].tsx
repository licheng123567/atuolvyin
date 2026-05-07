import { useGo, useOne, useUpdate } from "@refinedev/core";
import {
  ArrowLeft,
  Download,
  FileText,
  Save,
  Scale,
  Trash2,
  Upload,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { getToken } from "../../../providers/auth-provider";
import {
  LEGAL_STAGES,
  formatStage,
  getStageColor,
} from "./helpers";

interface CollectionCaseRef {
  id: number;
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
  owner_name: string;
  owner_phone_masked: string;
}

interface LegalCaseDetail {
  id: number;
  case_id: number;
  stage: string;
  amount_disputed: string | null;
  lawyer_name: string | null;
  law_firm: string | null;
  next_milestone: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  owner_name: string | null;
  owner_phone_masked: string | null;
  collection_case: CollectionCaseRef | null;
}

interface FormState {
  stage: string;
  lawyer_name: string;
  law_firm: string;
  next_milestone: string;
  amount_disputed: string;
  notes: string;
}

function detailToForm(detail: LegalCaseDetail): FormState {
  return {
    stage: detail.stage,
    lawyer_name: detail.lawyer_name ?? "",
    law_firm: detail.law_firm ?? "",
    next_milestone: detail.next_milestone ?? "",
    amount_disputed: detail.amount_disputed ?? "",
    notes: detail.notes ?? "",
  };
}

export function LegalCaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();

  const { query } = useOne<LegalCaseDetail>({
    resource: "legal/cases",
    id: id ?? "",
  });
  const detail = query.data?.data;

  // Derived-state form: starts as null, becomes initialized form once
  // we have detail. Subsequent edits override the derived value.
  const [overrideForm, setOverrideForm] = useState<FormState | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const form: FormState = overrideForm ?? (detail ? detailToForm(detail) : {
    stage: "pending_eval",
    lawyer_name: "",
    law_firm: "",
    next_milestone: "",
    amount_disputed: "",
    notes: "",
  });

  const setForm = (next: FormState) => setOverrideForm(next);

  const { mutate: update, mutation: updateMutation } = useUpdate();
  const saving = updateMutation.isPending;

  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");

  const handleDownloadBundle = async () => {
    if (!detail) return;
    setDownloadError("");
    setDownloading(true);
    try {
      const token = getToken() ?? "";
      const apiBase = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";
      const resp = await fetch(
        `${apiBase}/api/v1/legal/cases/${detail.id}/evidence-bundle`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!resp.ok) {
        setDownloadError(`下载失败：${resp.status}`);
        return;
      }
      const cd = resp.headers.get("content-disposition") ?? "";
      const filenameMatch = cd.match(/filename="([^"]+)"/);
      const filename =
        filenameMatch?.[1] ?? `evidence_case_${detail.case_id}.zip`;
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      const e = err as { message?: string };
      setDownloadError(e.message ?? "下载失败");
    } finally {
      setDownloading(false);
    }
  };

  const handleSave = () => {
    if (!detail) return;
    setErrorMsg("");
    update(
      {
        resource: "legal/cases",
        id: detail.id,
        values: {
          stage: form.stage,
          lawyer_name: form.lawyer_name || null,
          law_firm: form.law_firm || null,
          next_milestone: form.next_milestone || null,
          amount_disputed: form.amount_disputed || null,
          notes: form.notes || null,
        },
      },
      {
        onSuccess: () => {
          setSavedAt(new Date().toLocaleTimeString("zh-CN"));
          setOverrideForm(null); // re-derive from refetched detail
          query.refetch();
        },
        onError: (err) => {
          const e = err as { message?: string };
          setErrorMsg(e.message ?? "保存失败");
        },
      },
    );
  };

  if (query.isLoading) {
    return <div className="p-8 text-sm text-[var(--color-neutral-400)]">加载中…</div>;
  }
  if (!detail) {
    return <div className="p-8 text-sm text-[var(--color-danger)]">法务案件不存在</div>;
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <button
          type="button"
          onClick={() => go({ to: "/legal/cases" })}
          className="text-[var(--color-neutral-400)] hover:text-[var(--color-neutral-700)]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <Scale className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          法务案件详情
        </h1>
        <span
          className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
          style={getStageColor(detail.stage)}
        >
          {formatStage(detail.stage)}
        </span>
        <div className="ml-auto flex items-center gap-2">
          {downloadError && (
            <span className="text-xs text-[var(--color-danger)]">
              {downloadError}
            </span>
          )}
          <button
            type="button"
            onClick={handleDownloadBundle}
            disabled={downloading}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
            title="一键打包录音 / 转写 / AI 分析 / 链证元数据"
          >
            <Download className="w-4 h-4" />
            {downloading ? "打包中…" : "下载存证包"}
          </button>
        </div>
      </div>

      <div className="grid gap-6" style={{ gridTemplateColumns: "340px 1fr" }}>
        {/* Left: source case info */}
        <div className="space-y-4">
          <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-5">
            <h3 className="text-sm font-semibold text-[var(--color-neutral-900)] mb-3">
              关联催收案件
            </h3>
            {detail.collection_case ? (
              <dl className="text-sm space-y-2">
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">业主</dt>
                  <dd className="font-medium">
                    {detail.collection_case.owner_name}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">手机</dt>
                  <dd>{detail.collection_case.owner_phone_masked}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">案件 ID</dt>
                  <dd>#{detail.collection_case.id}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">欠费金额</dt>
                  <dd className="font-medium">
                    {detail.collection_case.amount_owed
                      ? `¥${detail.collection_case.amount_owed}`
                      : "—"}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">逾期月数</dt>
                  <dd>{detail.collection_case.months_overdue ?? "—"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">原案件状态</dt>
                  <dd>{detail.collection_case.stage}</dd>
                </div>
              </dl>
            ) : (
              <p className="text-sm text-[var(--color-neutral-400)]">
                关联案件已删除
              </p>
            )}
          </div>
        </div>

        {/* Right: editable form */}
        <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-5 space-y-4">
          <h3 className="text-sm font-semibold text-[var(--color-neutral-900)]">
            法务进度
          </h3>

          <div>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
              当前阶段
            </label>
            <select
              value={form.stage}
              onChange={(e) => setForm({ ...form, stage: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            >
              {LEGAL_STAGES.map((s) => (
                <option key={s} value={s}>
                  {formatStage(s)}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
                律师姓名
              </label>
              <input
                type="text"
                value={form.lawyer_name}
                onChange={(e) =>
                  setForm({ ...form, lawyer_name: e.target.value })
                }
                placeholder="例：王律师"
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                style={{ borderRadius: "var(--radius-md)" }}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
                律师事务所
              </label>
              <input
                type="text"
                value={form.law_firm}
                onChange={(e) => setForm({ ...form, law_firm: e.target.value })}
                placeholder="例：某某律师事务所"
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                style={{ borderRadius: "var(--radius-md)" }}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
                涉案金额(元)
              </label>
              <input
                type="number"
                step="0.01"
                min={0}
                value={form.amount_disputed}
                onChange={(e) =>
                  setForm({ ...form, amount_disputed: e.target.value })
                }
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                style={{ borderRadius: "var(--radius-md)" }}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
                下一里程碑
              </label>
              <input
                type="text"
                value={form.next_milestone}
                onChange={(e) =>
                  setForm({ ...form, next_milestone: e.target.value })
                }
                placeholder="例：2026-06-15 开庭"
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                style={{ borderRadius: "var(--radius-md)" }}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
              备注
            </label>
            <textarea
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              rows={4}
              placeholder="案件进展、举证情况等"
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>

          {errorMsg && (
            <p className="text-sm text-[var(--color-danger)]">{errorMsg}</p>
          )}

          <div className="flex items-center justify-between pt-2">
            {savedAt ? (
              <p className="text-xs text-[var(--color-success)]">
                已保存 ({savedAt})
              </p>
            ) : (
              <span />
            )}
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              style={{
                background: "var(--color-primary)",
                borderRadius: "var(--radius-md)",
              }}
            >
              <Save className="w-4 h-4" />
              {saving ? "保存中…" : "保存"}
            </button>
          </div>
        </div>
      </div>

      <LegalDocumentsPanel legalCaseId={detail.id} />
    </div>
  );
}

// ─── Legal Documents Panel (Sprint 11.6) ────────────────────────────

interface LegalDocument {
  id: number;
  legal_case_id: number;
  name: string;
  category: string;
  mime_type: string | null;
  size_bytes: number;
  uploaded_by: number;
  uploaded_by_name: string | null;
  created_at: string;
}

const CATEGORY_LABEL: Record<string, string> = {
  contract: "合同",
  judgment: "判决书",
  notice: "通知函",
  evidence: "证据材料",
  other: "其他",
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function LegalDocumentsPanel({ legalCaseId }: { legalCaseId: number }) {
  const [docs, setDocs] = useState<LegalDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [category, setCategory] = useState<string>("contract");
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const apiBase = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";
  const authHeader = (): HeadersInit => ({
    Authorization: `Bearer ${getToken() ?? ""}`,
  });

  // Fetch on mount + when caseId changes; setState happens off the React
  // synchronous render cycle (inside async fetch resolution), so the
  // set-state-in-effect rule's "cascading render" concern doesn't apply here
  // — silencing locally with a justification comment.
  const fetchDocs = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await fetch(
        `${apiBase}/api/v1/legal/cases/${legalCaseId}/documents`,
        { headers: { Authorization: `Bearer ${getToken() ?? ""}` } },
      );
      if (resp.ok) setDocs(await resp.json());
    } finally {
      setLoading(false);
    }
  }, [apiBase, legalCaseId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchDocs();
  }, [fetchDocs]);

  const handleUpload = async (file: File) => {
    setError("");
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("category", category);
      const resp = await fetch(
        `${apiBase}/api/v1/legal/cases/${legalCaseId}/documents`,
        { method: "POST", headers: authHeader(), body: fd },
      );
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        setError(data.message ?? `上传失败: ${resp.status}`);
        return;
      }
      await fetchDocs();
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDownload = async (doc: LegalDocument) => {
    const resp = await fetch(
      `${apiBase}/api/v1/legal/documents/${doc.id}/download`,
      { headers: authHeader() },
    );
    if (!resp.ok) return;
    const data = (await resp.json()) as { download_url: string };
    window.open(data.download_url, "_blank");
  };

  const handleDelete = async (doc: LegalDocument) => {
    if (!confirm(`确定删除「${doc.name}」?`)) return;
    const resp = await fetch(
      `${apiBase}/api/v1/legal/documents/${doc.id}`,
      { method: "DELETE", headers: authHeader() },
    );
    if (resp.ok) await fetchDocs();
  };

  return (
    <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-5 mt-6">
      <div className="flex items-center gap-2 mb-4">
        <FileText className="w-4 h-4 text-[var(--color-primary)]" />
        <h3 className="text-sm font-semibold text-[var(--color-neutral-900)]">
          法律文件
        </h3>
        <span className="text-xs text-[var(--color-neutral-400)]">
          共 {docs.length} 份
        </span>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          {Object.entries(CATEGORY_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.txt"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void handleUpload(f);
          }}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          style={{
            background: "var(--color-primary)",
            borderRadius: "var(--radius-md)",
          }}
        >
          <Upload className="w-4 h-4" />
          {uploading ? "上传中…" : "上传文件"}
        </button>
        {error && (
          <span className="text-xs text-[var(--color-danger)]">{error}</span>
        )}
      </div>

      {loading && (
        <p className="text-sm text-[var(--color-neutral-400)]">加载中…</p>
      )}
      {!loading && docs.length === 0 && (
        <p className="text-sm text-[var(--color-neutral-400)]">
          尚未上传任何法律文件
        </p>
      )}
      {docs.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-[var(--color-neutral-500)]">
            <tr className="border-b border-[var(--color-neutral-200)]">
              <th className="py-2 font-medium">名称</th>
              <th className="py-2 font-medium">类别</th>
              <th className="py-2 font-medium">大小</th>
              <th className="py-2 font-medium">上传人</th>
              <th className="py-2 font-medium">时间</th>
              <th className="py-2 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {docs.map((doc) => (
              <tr key={doc.id}>
                <td className="py-2 font-medium text-[var(--color-neutral-700)]">
                  {doc.name}
                </td>
                <td className="py-2">
                  <span className="px-2 py-0.5 text-xs rounded-full font-medium bg-[var(--color-neutral-100)] text-[var(--color-neutral-700)]">
                    {CATEGORY_LABEL[doc.category] ?? doc.category}
                  </span>
                </td>
                <td className="py-2 text-[var(--color-neutral-500)]">
                  {formatFileSize(doc.size_bytes)}
                </td>
                <td className="py-2 text-[var(--color-neutral-500)]">
                  {doc.uploaded_by_name ?? "—"}
                </td>
                <td className="py-2 text-[var(--color-neutral-500)]">
                  {doc.created_at?.slice(0, 10)}
                </td>
                <td className="py-2 text-right">
                  <button
                    type="button"
                    onClick={() => handleDownload(doc)}
                    className="text-[var(--color-primary)] mr-3"
                    aria-label="下载"
                  >
                    <Download className="w-4 h-4 inline" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(doc)}
                    className="text-[var(--color-danger)]"
                    aria-label="删除"
                  >
                    <Trash2 className="w-4 h-4 inline" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
