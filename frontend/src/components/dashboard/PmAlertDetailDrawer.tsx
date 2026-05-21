// v0.9.0 — PM Dashboard 运营提醒明细 Drawer
//
// 改造前:PmAlertsSection 卡片点击直接跳 detail_path(管理页)— 用户要自己理解
//   筛选参数,且离开 dashboard 上下文。
// 改造后:卡片点击 → 右侧 Drawer 展示该类别明细列表(申请人/时间/金额/天数等),
//   每行「处理 →」一键跳处理详情;不离开 dashboard。
//
// 后端:GET /api/v1/pm/dashboard/alerts/{alert_key}/details
//   返回 { alert_key, total, items: AlertDetailItem[] }
import { useCustom } from "@refinedev/core";
import { ArrowUpRight, BellRing, Loader2 } from "lucide-react";
import { RightDrawer } from "../ui/RightDrawer";

interface AlertDetailItem {
  id: number;
  detail_path: string;
  title: string | null;
  subtitle: string | null;
  amount: string | null;
  timestamp: string | null;
  days: number | null;
  tag: string | null;
}

interface AlertDetailsResp {
  alert_key: string;
  total: number;
  items: AlertDetailItem[];
}

interface Props {
  alertKey: string;
  alertLabel: string;
  onClose: () => void;
}

// 不同 tag 不同颜色(轻量提示)
const TAG_COLORS: Record<string, string> = {
  discount: "#7e3af2",
  legal: "#2563eb",
  promise: "#c2410c",
  agent: "#0891b2",
  cost: "#dc2626",
  new: "#6b7280",
  in_progress: "#1A56DB",
  promised: "#c2410c",
  escalated: "#dc2626",
};

export function PmAlertDetailDrawer({ alertKey, alertLabel, onClose }: Props) {
  const { query } = useCustom<AlertDetailsResp>({
    url: `pm/dashboard/alerts/${alertKey}/details`,
    method: "get",
    config: { query: { limit: 50 } },
  });
  const data = query.data?.data;

  return (
    <RightDrawer
      open
      onClose={onClose}
      drawerKey="pm-alert-detail"
      defaultWidth={620}
      title={
        <span className="flex items-center gap-2">
          <BellRing className="w-5 h-5 text-[var(--color-warning)]" />
          {alertLabel}
          {data && (
            <span className="text-sm font-normal text-[var(--color-neutral-500)]">
              · 共 {data.total} 项
            </span>
          )}
        </span>
      }
      footer={
        <button
          type="button"
          onClick={onClose}
          className="px-3 py-1.5 text-sm rounded border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-50)]"
        >
          关闭
        </button>
      }
    >
      <div className="space-y-2">
        {query.isLoading && (
          <div className="flex items-center gap-2 text-sm text-[var(--color-neutral-500)] p-4">
            <Loader2 className="w-4 h-4 animate-spin" /> 加载明细…
          </div>
        )}

        {!query.isLoading && data && data.items.length === 0 && (
          <div className="text-sm text-[var(--color-neutral-500)] p-6 text-center">
            该类别暂无明细
          </div>
        )}

        {!query.isLoading &&
          data?.items.map((it) => {
            const tagColor = TAG_COLORS[it.tag ?? ""] ?? "#6b7280";
            return (
              <div
                key={`${it.tag}-${it.id}`}
                className="border border-[var(--color-neutral-200)] rounded p-3 hover:bg-[var(--color-neutral-50)]"
              >
                <div className="flex items-start justify-between gap-3">
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-[var(--color-neutral-900)]">
                        {it.title ?? `#${it.id}`}
                      </span>
                      {it.tag && (
                        <span
                          className="text-xs px-1.5 py-0.5 rounded"
                          style={{
                            background: `${tagColor}20`,
                            color: tagColor,
                          }}
                        >
                          {it.tag}
                        </span>
                      )}
                      {it.amount && (
                        <span className="text-xs text-[var(--color-danger)] font-mono">
                          ¥{Number(it.amount).toLocaleString("zh-CN")}
                        </span>
                      )}
                    </div>
                    {it.subtitle && (
                      <div className="text-xs text-[var(--color-neutral-600)] mt-0.5">
                        {it.subtitle}
                      </div>
                    )}
                    {it.timestamp && (
                      <div className="text-xs text-[var(--color-neutral-400)] mt-0.5 font-mono">
                        {new Date(it.timestamp).toLocaleString("zh-CN", {
                          year: "numeric",
                          month: "2-digit",
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                        {it.days !== null &&
                          it.days !== undefined &&
                          ` · 已 ${it.days} 天`}
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      // 用 detail_path(可能含 query)— refine useGo 不易处理 query,直接 location.href
                      window.location.href = it.detail_path;
                    }}
                    className="ds-btn ds-btn-secondary ds-btn-sm flex-shrink-0"
                    title="跳转处理"
                  >
                    处理 <ArrowUpRight className="w-3 h-3" />
                  </button>
                </div>
              </div>
            );
          })}
      </div>
    </RightDrawer>
  );
}

export default PmAlertDetailDrawer;
