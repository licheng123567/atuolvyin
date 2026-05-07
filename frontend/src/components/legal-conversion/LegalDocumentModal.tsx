// Sprint 16.4 — 订单文书查看 / 重新生成 modal（PRD §20.4）
import { useCustom, useCustomMutation } from "@refinedev/core";
import { Copy, FileText, Loader2, RefreshCw, X } from "lucide-react";
import { useState } from "react";

interface DocRender {
  id: number;
  order_id: number;
  template_id: number;
  title: string;
  body_md: string;
  rendered_at: string;
  version: number;
}

export function LegalDocumentModal({
  orderId,
  onClose,
}: {
  orderId: number;
  onClose: () => void;
}) {
  const [refreshKey, setRefreshKey] = useState(0);

  const { query } = useCustom<DocRender>({
    url: `admin/legal-conversion-orders/${orderId}/document`,
    method: "get",
    queryOptions: { retry: false },
    config: { query: { _r: refreshKey } },
  });

  const { mutate: doRender, mutation } = useCustomMutation();

  const onRegenerate = () => {
    doRender(
      {
        url: `admin/legal-conversion-orders/${orderId}/document`,
        method: "post",
        values: {},
      },
      {
        onSuccess: () => setRefreshKey((k) => k + 1),
        onError: (err) => alert(`生成失败：${(err as { message?: string }).message ?? "请重试"}`),
      },
    );
  };

  const onCopy = () => {
    if (!doc) return;
    navigator.clipboard.writeText(doc.body_md);
    alert("已复制到剪贴板");
  };

  const doc = query.data?.data;
  const notFound =
    query.isError &&
    (query.error as { statusCode?: number } | undefined)?.statusCode === 404;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--color-neutral-200)]">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-[var(--color-primary)]" />
            <h2 className="text-base font-semibold">
              法律文书 · 订单 #{orderId}
              {doc && (
                <span className="ml-2 text-xs text-[var(--color-neutral-500)]">
                  v{doc.version}
                </span>
              )}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--color-neutral-400)] hover:text-[var(--color-neutral-700)]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-5">
          {query.isLoading && (
            <div className="flex items-center gap-2 text-sm text-[var(--color-neutral-500)]">
              <Loader2 className="w-4 h-4 animate-spin" /> 加载中…
            </div>
          )}
          {notFound && (
            <div className="text-center py-12">
              <FileText className="w-10 h-10 mx-auto text-[var(--color-neutral-300)] mb-3" />
              <p className="text-sm text-[var(--color-neutral-500)] mb-4">
                此订单尚未生成文书
              </p>
              <button
                type="button"
                onClick={onRegenerate}
                disabled={mutation.isPending}
                className="px-4 py-1.5 text-sm bg-[var(--color-primary)] text-white rounded hover:opacity-90 disabled:opacity-50 inline-flex items-center gap-1.5"
              >
                {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                生成文书
              </button>
            </div>
          )}
          {doc && (
            <>
              <div className="text-base font-semibold text-[var(--color-neutral-900)] mb-2">
                {doc.title}
              </div>
              <div className="text-xs text-[var(--color-neutral-500)] mb-4">
                生成于 {new Date(doc.rendered_at).toLocaleString("zh-CN")}
              </div>
              <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-[var(--color-neutral-800)] bg-[var(--color-neutral-50)] border border-[var(--color-neutral-200)] rounded p-4">
                {doc.body_md}
              </pre>
            </>
          )}
        </div>

        {doc && (
          <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-[var(--color-neutral-200)]">
            <button
              type="button"
              onClick={onCopy}
              className="flex items-center gap-1 px-3 py-1.5 text-sm border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] rounded hover:bg-[var(--color-neutral-50)]"
            >
              <Copy className="w-3.5 h-3.5" /> 复制
            </button>
            <button
              type="button"
              onClick={onRegenerate}
              disabled={mutation.isPending}
              className="flex items-center gap-1 px-3 py-1.5 text-sm border border-[var(--color-primary)] text-[var(--color-primary)] rounded hover:bg-[var(--color-primary-light)] disabled:opacity-50"
            >
              {mutation.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <RefreshCw className="w-3.5 h-3.5" />
              )}
              重新生成
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
