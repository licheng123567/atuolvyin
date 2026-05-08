// v1.5.5 D2 — 服务商端：到期 30 天内的项目只读历史报表（聚合数据，不可下钻）
import { useCustom } from "@refinedev/core";
import { Archive } from "lucide-react";

interface HistoricalItem {
  project_id: number;
  project_name: string;
  plan_start: string | null;
  plan_end: string | null;
  closed_at: string;
  case_count: number;
  total_owed: number;
  total_recovered: number;
}

interface HistoricalResponse {
  items: HistoricalItem[];
  retention_days: number;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return iso.slice(0, 10);
}

function formatMoney(n: number): string {
  return `¥${n.toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`;
}

export function ProviderHistoricalReportsPage() {
  const { query } = useCustom<HistoricalResponse>({
    url: "provider/historical-reports",
    method: "get",
  });
  const data = query.data?.data;
  const items = data?.items ?? [];
  const retention = data?.retention_days ?? 30;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            <Archive className="inline w-4 h-4 mr-1" style={{ verticalAlign: "-3px" }} />
            历史报表
          </h1>
          <div className="page-subtitle">
            到期项目保留 {retention} 天只读窗口；仅展示聚合数据，不可查看具体案件
          </div>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>项目名称</th>
              <th>服务期</th>
              <th>关闭时间</th>
              <th>案件数</th>
              <th>累计欠费</th>
              <th>已回款</th>
              <th>回款率</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading && (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!query.isLoading && items.length === 0 && (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  最近 {retention} 天内无到期项目
                </td>
              </tr>
            )}
            {items.map((it) => {
              const rate = it.total_owed > 0 ? (it.total_recovered / it.total_owed) * 100 : 0;
              return (
                <tr key={it.project_id}>
                  <td>
                    <strong>{it.project_name}</strong>
                  </td>
                  <td style={{ fontSize: 12, color: "#6b7280" }}>
                    {formatDate(it.plan_start)} → {formatDate(it.plan_end)}
                  </td>
                  <td style={{ fontSize: 12, color: "#6b7280" }}>
                    {formatDate(it.closed_at)}
                  </td>
                  <td>{it.case_count}</td>
                  <td>{formatMoney(it.total_owed)}</td>
                  <td style={{ color: "#057a55", fontWeight: 600 }}>
                    {formatMoney(it.total_recovered)}
                  </td>
                  <td>
                    <span
                      className={
                        rate >= 70
                          ? "ds-badge ds-badge-green"
                          : rate >= 40
                            ? "ds-badge ds-badge-orange"
                            : "ds-badge ds-badge-gray"
                      }
                    >
                      {rate.toFixed(1)}%
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
