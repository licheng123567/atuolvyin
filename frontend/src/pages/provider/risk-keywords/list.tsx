// v1.0.0 — 服务商风控关键词列表(对齐 admin/risk-keywords/list.tsx)。
import { useDelete, useGo, useList } from "@refinedev/core";
import { Pencil, Plus, Shield, Trash2 } from "lucide-react";
import { useState } from "react";
import { HelpPanel } from "../../../components/ui/HelpPanel";
import type { PaginatedResponse } from "../../../types";
import { isPlatformPreset, type RiskKeywordItem } from "./helpers";

const CAT_LABELS: Record<string, string> = {
  owner_abuse: "业主辱骂 (L1)",
  owner_threat: "业主威胁 (L2)",
  agent_violation: "催收员违规 (L2)",
  agent_minor_misconduct: "轻微不当 (L1)",
};

const SPEAKER_LABELS: Record<string, string> = {
  customer: "业主端",
  owner: "业主端",
  agent: "催收员端",
};

export function ProviderRiskKeywordListPage() {
  const go = useGo();
  const { mutate: deleteKw } = useDelete();
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const { query } = useList<RiskKeywordItem>({
    resource: "provider/risk-keywords",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
  });

  const rawData = query.data?.data;
  const items: RiskKeywordItem[] =
    (rawData as unknown as PaginatedResponse<RiskKeywordItem>)?.items ??
    (rawData as RiskKeywordItem[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;
  const isLoading = query.isLoading;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  const handleDelete = (item: RiskKeywordItem) => {
    if (!confirm(`确认删除关键词「${item.keyword}」?`)) return;
    deleteKw({ resource: "provider/risk-keywords", id: item.id });
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-[var(--color-danger)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            风控关键词(服务商)
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {total} 条
          </span>
        </div>
        <button
          type="button"
          onClick={() => go({ to: "/provider/risk-keywords/new" })}
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white transition-colors"
          style={{ background: "var(--color-danger)", borderRadius: "var(--radius-md)" }}
        >
          <Plus className="w-4 h-4" />
          新增关键词
        </button>
      </div>

      <HelpPanel
        tone="danger"
        dismissKey="/provider/risk-keywords"
        title="服务商风控关键词作用"
        bullets={[
          <><strong>实时检测</strong>:本服务商内催收员通话上传后,ASR 识别文本扫描这些关键词;触发后立即产生风控事件推给本服务商督导</>,
          <><strong>scope 隔离</strong>:本列表仅显示<strong>本服务商私有</strong>关键词 +
            <strong>平台预置</strong>;不可见其他服务商或物业租户的关键词</>,
          <><strong>分级处置</strong>:
            <span className="ds-badge ds-badge-orange" style={{ fontSize: 11 }}>L1</span> AI 自动弹屏提醒;
            <span className="ds-badge ds-badge-red" style={{ fontSize: 11 }}>L2</span> 立即通知督导接管</>,
          <><strong>不能删平台预置</strong>:平台预置词只能由平台超管维护,本服务商可加自己的特殊关注词</>,
        ]}
      />

      {isLoading ? (
        <div className="text-center py-10 text-[var(--color-neutral-400)]">加载中...</div>
      ) : (
        <>
          <div
            className="rounded-lg border overflow-hidden bg-white"
            style={{ borderColor: "var(--color-neutral-200)" }}
          >
            <table className="w-full text-sm">
              <thead
                className="border-b"
                style={{ background: "var(--color-neutral-50)", borderColor: "var(--color-neutral-200)" }}
              >
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">关键词</th>
                  <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">场景</th>
                  <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">说话人</th>
                  <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">来源</th>
                  <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">状态</th>
                  <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-neutral-100)]">
                {items.map((item) => {
                  const isPreset = isPlatformPreset(item);
                  const canEdit = !isPreset;
                  return (
                    <tr key={item.id} className="hover:bg-[var(--color-neutral-50)]">
                      <td className="px-4 py-3 font-mono font-medium text-[var(--color-neutral-900)]">
                        {item.keyword}
                      </td>
                      <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                        {CAT_LABELS[item.category] ?? item.category}
                      </td>
                      <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                        {SPEAKER_LABELS[item.speaker] ?? item.speaker}
                      </td>
                      <td className="px-4 py-3">
                        {isPreset ? (
                          <span
                            className="text-xs px-1.5 py-0.5 rounded"
                            style={{ background: "var(--color-info-light)", color: "var(--color-info)" }}
                          >
                            平台预置
                          </span>
                        ) : (
                          <span
                            className="text-xs px-1.5 py-0.5 rounded"
                            style={{ background: "var(--color-neutral-100)", color: "var(--color-neutral-600)" }}
                          >
                            服务商自定义
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className="text-xs px-1.5 py-0.5 rounded"
                          style={
                            item.is_active
                              ? { background: "var(--color-success-light)", color: "var(--color-success)" }
                              : { background: "var(--color-neutral-100)", color: "var(--color-neutral-400)", textDecoration: "line-through" }
                          }
                        >
                          {item.is_active ? "启用" : "已停用"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            type="button"
                            disabled={!canEdit}
                            onClick={() => alert("编辑功能待实现(level / is_active 可改)")}
                            className="p-1 rounded hover:bg-[var(--color-neutral-100)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                            title={canEdit ? "编辑" : "平台预置词条仅平台超管可编辑"}
                          >
                            <Pencil className="w-4 h-4 text-[var(--color-neutral-500)]" />
                          </button>
                          <button
                            type="button"
                            disabled={!canEdit}
                            onClick={() => handleDelete(item)}
                            className="p-1 rounded hover:bg-[var(--color-neutral-100)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                            title={canEdit ? "删除(标记停用)" : "平台预置词条仅平台超管可操作"}
                          >
                            <Trash2 className="w-4 h-4 text-[var(--color-danger)]" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                      暂无关键词
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-end gap-2 mt-4">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="px-3 py-1.5 text-sm border rounded disabled:opacity-40 transition-colors"
                style={{ borderColor: "var(--color-neutral-200)", borderRadius: "var(--radius-md)" }}
              >
                上一页
              </button>
              <span className="text-sm text-[var(--color-neutral-600)]">{page} / {totalPages}</span>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
                className="px-3 py-1.5 text-sm border rounded disabled:opacity-40 transition-colors"
                style={{ borderColor: "var(--color-neutral-200)", borderRadius: "var(--radius-md)" }}
              >
                下一页
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
