import { useDelete, useGetIdentity, useGo, useList } from "@refinedev/core";
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
  // v1.6.5 — 兼容后端可能下发的简短分类
  complaint: "投诉",
  threat: "威胁",
  abuse: "辱骂",
  violation: "违规",
  none: "无",
};

const SPEAKER_LABELS: Record<string, string> = {
  customer: "业主端",
  owner: "业主端",
  agent: "催收员端",
  admin: "管理员端",
};

export function RiskKeywordListPage() {
  const go = useGo();
  const { mutate: deleteKw } = useDelete();
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const { data: identity } = useGetIdentity<{ role: string }>();
  const isPlatformSuper = identity?.role === "platform_super";

  const { query } = useList<RiskKeywordItem>({
    resource: "admin/risk-keywords",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
  });

  const rawData = query.data?.data;
  const items: RiskKeywordItem[] =
    (rawData as unknown as PaginatedResponse<RiskKeywordItem>)?.items ??
    (rawData as RiskKeywordItem[] | undefined) ?? [];
  const total = query.data?.total ?? 0;
  const isLoading = query.isLoading;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  const handleDelete = (item: RiskKeywordItem) => {
    if (!confirm(`确认删除关键词「${item.keyword}」？`)) return;
    deleteKw({ resource: "admin/risk-keywords", id: item.id });
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-[var(--color-danger)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            风控关键词
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">共 {total} 条</span>
        </div>
        <button
          type="button"
          onClick={() => go({ to: "/admin/risk-keywords/new" })}
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white transition-colors"
          style={{
            background: "var(--color-danger)",
            borderRadius: "var(--radius-md)",
          }}
        >
          <Plus className="w-4 h-4" />
          新增关键词
        </button>
      </div>

      <HelpPanel
        tone="danger"
        dismissKey="/admin/risk-keywords"
        title="风控关键词的作用"
        bullets={[
          <><strong>实时检测</strong>：催收员通话上传后，ASR 识别出文本，系统实时扫描这些关键词命中情况，触发后立刻产生「风控事件」并推送给督导</>,
          <><strong>双向监控</strong>：
            <span style={{ color: "#9a3412", fontWeight: 600 }}>业主端</span>词（如「不想交」「你们这是骚扰」「投诉」）= 业主负面情绪/投诉风险；
            <span style={{ color: "#9a3412", fontWeight: 600 }}>催收员端</span>词（如「起诉」「逼你」语气强硬）= 催收员违规话术
          </>,
          <><strong>分级处置</strong>：
            <span className="ds-badge ds-badge-orange" style={{ fontSize: 11 }}>L1 提醒</span> AI 自动给催收员弹屏提醒；
            <span className="ds-badge ds-badge-red" style={{ fontSize: 11 }}>L2 高危</span> 立即通知督导，督导可在「实时通话墙」监听 / 强制接管 / 强制结束
          </>,
          <><strong>词库分层</strong>：
            <strong>平台预置</strong>（灰 badge，平台超管维护，全租户共享）+
            <strong>本物业自定义</strong>（蓝 badge，仅本物业生效）。本物业不能删平台预置词，可加自己的特殊关注词
          </>,
          <><strong>查看触发记录</strong>：被触发后的所有事件 → 督导端「风控事件」页查看 + 处置（介入 / 关闭 / 转法务）</>,
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
                  <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                    关键词
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                    场景
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                    说话人
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                    来源
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                    状态
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-neutral-100)]">
                {items.map((item) => {
                  const isPreset = isPlatformPreset(item);
                  const canEdit = isPlatformSuper || !isPreset;
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
                            style={{
                              background: "var(--color-info-light)",
                              color: "var(--color-info)",
                            }}
                          >
                            平台预置
                          </span>
                        ) : (
                          <span
                            className="text-xs px-1.5 py-0.5 rounded"
                            style={{
                              background: "var(--color-neutral-100)",
                              color: "var(--color-neutral-600)",
                            }}
                          >
                            租户自定义
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className="text-xs px-1.5 py-0.5 rounded"
                          style={
                            item.is_active
                              ? {
                                  background: "var(--color-success-light)",
                                  color: "var(--color-success)",
                                }
                              : {
                                  background: "var(--color-neutral-100)",
                                  color: "var(--color-neutral-400)",
                                  textDecoration: "line-through",
                                }
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
                            onClick={() => go({ to: `/admin/risk-keywords/${item.id}/edit` })}
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
                            title={canEdit ? "删除" : "平台预置词条仅平台超管可删除"}
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
