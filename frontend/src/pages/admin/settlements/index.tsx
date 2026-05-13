// 结算管理 — v1.5.7：3 tab（应付服务商 / 应发员工提成 / 成本汇总）
import { useCustom, useGo, useList } from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { BarChart3, Briefcase, Download, X } from "lucide-react";
import { useMemo, useState } from "react";
import { SearchableSelect } from "../../../components/ui/SearchableSelect";
import { exportToCsv } from "../../../lib/csv";
import type { PaginatedResponse } from "../../../types";
import {
  formatAmount,
  formatPeriod,
  recentYearMonths,
  STATUS_LABELS,
  type SettlementStatus,
} from "./helpers";

// ─── Tab 类型 ──────────────────────────────────────────────────
type TabKey = "providers" | "agents" | "summary";

// ─── 「应付服务商」类型 ──────────────────────────────────────
interface SettlementItem {
  id: number;
  contract_id: number;
  provider_id: number | null;
  provider_name: string | null;
  period_start: string;
  period_end: string;
  total_amount: string;
  status: SettlementStatus;
  payment_proof_url: string | null;
  confirmed_at: string | null;
  paid_at: string | null;
  billing_method?: string | null;
}

const STATUS_BADGE_CLASS: Record<SettlementStatus, string> = {
  DRAFT: "ds-badge ds-badge-gray",
  CONFIRMED: "ds-badge ds-badge-green",
  PAID: "ds-badge ds-badge-blue",
  DISPUTED: "ds-badge ds-badge-red",
};

// ─── 「应发员工提成」类型 ───────────────────────────────────
interface AgentCommissionItem {
  user_id: number;
  name: string;
  phone_masked: string;
  year_month: string;
  commission_rate: number;
  base_amount: string;
  paid_case_count: number;
  commission: string;
}

interface AgentCommissionListResp {
  year_month: string;
  total_base: string;
  total_commission: string;
  items: AgentCommissionItem[];
}

interface AgentCommissionLineItem {
  case_id: number;
  owner_name: string;
  paid_amount: string;
  paid_at: string;
}

interface AgentCommissionDetailResp {
  user_id: number;
  name: string;
  year_month: string;
  commission_rate: number;
  base_amount: string;
  commission: string;
  items: AgentCommissionLineItem[];
}

// ═══════════════════════════════════════════════════════════════
// 主页 — tab 容器
// ═══════════════════════════════════════════════════════════════

export function AdminSettlementListPage() {
  const [tab, setTab] = useState<TabKey>("providers");

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">结算管理</h1>
          <div className="page-subtitle">
            {tab === "providers" && "应付服务商：B2B 月度结算"}
            {tab === "agents" && "应发员工提成：物业内部催收员工资视图"}
            {tab === "summary" && "成本汇总：综合视图（即将上线）"}
          </div>
        </div>
      </div>

      {/* tabs */}
      <div className="ds-tabs">
        <div
          className={`ds-tab${tab === "providers" ? " active" : ""}`}
          onClick={() => setTab("providers")}
        >
          <Briefcase className="inline w-3.5 h-3.5" style={{ verticalAlign: "-3px", marginRight: 4 }} />
          应付服务商
        </div>
        <div
          className={`ds-tab${tab === "agents" ? " active" : ""}`}
          onClick={() => setTab("agents")}
        >
          应发员工提成
        </div>
        <div
          className={`ds-tab${tab === "summary" ? " active" : ""}`}
          onClick={() => setTab("summary")}
        >
          <BarChart3 className="inline w-3.5 h-3.5" style={{ verticalAlign: "-3px", marginRight: 4 }} />
          成本汇总
        </div>
      </div>

      {tab === "providers" && <ProvidersTab />}
      {tab === "agents" && <AgentsTab />}
      {tab === "summary" && <SummaryTab />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// Tab 1 — 应付服务商（保留原有逻辑）
// ═══════════════════════════════════════════════════════════════

function ProvidersTab() {
  const go = useGo();
  const [yearMonth, setYearMonth] = useState("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const yearMonthOptions = useMemo(() => recentYearMonths(6), []);

  const filters: CrudFilter[] = [];
  if (yearMonth) {
    filters.push({ field: "year_month", operator: "eq", value: yearMonth });
  }

  const { query } = useList<SettlementItem>({
    resource: "admin/settlements",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });

  const rawData = query.data?.data;
  const items: SettlementItem[] =
    (rawData as unknown as PaginatedResponse<SettlementItem>)?.items ??
    (rawData as SettlementItem[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: "var(--color-neutral-600)" }}>账期：</span>
        <SearchableSelect
          style={{ width: 140 }}
          value={yearMonth}
          placeholder="全部月份"
          onChange={(v) => {
            setYearMonth(String(v));
            setPage(1);
          }}
          options={yearMonthOptions.map((ym) => ({ value: ym, label: ym }))}
        />
        <span style={{ marginLeft: 12, fontSize: 12, color: "#9ca3af" }}>
          共 {total} 张结算单
        </span>
        <button
          type="button"
          className="ds-btn ds-btn-secondary ds-btn-sm"
          style={{ marginLeft: "auto" }}
          disabled={items.length === 0}
          onClick={() =>
            exportToCsv(
              `provider-settlements-${new Date().toISOString().slice(0, 10)}.csv`,
              [
                { key: "id", label: "ID" },
                { key: "provider_name", label: "服务商" },
                { key: "period", label: "账期" },
                { key: "billing_method", label: "计费方式" },
                { key: "total_amount", label: "应付金额" },
                { key: "status", label: "状态" },
                { key: "confirmed_at", label: "确认时间" },
                { key: "paid_at", label: "支付时间" },
              ],
              items.map((s) => ({
                id: s.id,
                provider_name: s.provider_name ?? "",
                period: `${s.period_start.slice(0, 10)} ~ ${s.period_end.slice(0, 10)}`,
                billing_method: s.billing_method ?? "",
                total_amount: s.total_amount,
                status: s.status,
                confirmed_at: s.confirmed_at ?? "",
                paid_at: s.paid_at ?? "",
              })),
            )
          }
        >
          <Download className="w-3.5 h-3.5" />
          导出
        </button>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>服务商</th>
              <th>账期</th>
              <th>计费方式</th>
              <th>应付金额</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading && (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!query.isLoading && items.length === 0 && (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  暂无结算单
                </td>
              </tr>
            )}
            {items.map((s) => {
              const period = formatPeriod(s.period_start, s.period_end);
              return (
                <tr key={s.id}>
                  <td>
                    <strong>{s.provider_name ?? "—"}</strong>
                  </td>
                  <td>{period}</td>
                  <td>{s.billing_method ?? "—"}</td>
                  <td style={{ fontWeight: 700 }}>{formatAmount(s.total_amount)}</td>
                  <td>
                    <span className={STATUS_BADGE_CLASS[s.status] ?? "ds-badge ds-badge-gray"}>
                      {STATUS_LABELS[s.status] ?? s.status}
                    </span>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="ds-btn ds-btn-ghost ds-btn-sm"
                      onClick={() => go({ to: `/admin/settlements/${s.id}` })}
                    >
                      查看明细
                    </button>
                    {s.status === "DRAFT" && (
                      <button type="button" className="ds-btn ds-btn-primary ds-btn-sm" style={{ marginLeft: 4 }}>
                        确认结算单
                      </button>
                    )}
                    {s.status === "CONFIRMED" && (
                      <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" style={{ marginLeft: 4 }}>
                        上传凭证
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {totalPages > 1 && (
          <div className="ds-pagination">
            <span className="pagination-info">
              共 {total} 条，第 {page}/{totalPages} 页
            </span>
            <div className="pagination-pages">
              {page > 1 && (
                <div className="page-btn" onClick={() => setPage((p) => p - 1)}>
                  ‹
                </div>
              )}
              <div className="page-btn active">{page}</div>
              {page < totalPages && (
                <div className="page-btn" onClick={() => setPage((p) => p + 1)}>
                  ›
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════
// Tab 2 — 应发员工提成
// ═══════════════════════════════════════════════════════════════

function AgentsTab() {
  // 默认本月（YYYY-MM）
  const [yearMonth, setYearMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const yearMonthOptions = useMemo(() => recentYearMonths(6), []);
  const [detailFor, setDetailFor] = useState<AgentCommissionItem | null>(null);

  const { query } = useCustom<AgentCommissionListResp>({
    url: "admin/agent-commissions",
    method: "get",
    config: { query: { year_month: yearMonth } },
  });
  const data = query.data?.data;
  const items = data?.items ?? [];

  return (
    <>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: "var(--color-neutral-600)" }}>账期：</span>
        <SearchableSelect
          style={{ width: 140 }}
          value={yearMonth}
          placeholder="选择月份"
          allowClear={false}
          onChange={(v) => setYearMonth(String(v))}
          options={yearMonthOptions.map((ym) => ({ value: ym, label: ym }))}
        />
        <button
          type="button"
          className="ds-btn ds-btn-secondary ds-btn-sm"
          style={{ marginLeft: "auto" }}
          disabled={items.length === 0}
          onClick={() =>
            exportToCsv(
              `agent-commissions-${yearMonth}.csv`,
              [
                { key: "user_id", label: "员工ID" },
                { key: "name", label: "姓名" },
                { key: "phone_masked", label: "手机（掩码）" },
                { key: "year_month", label: "账期" },
                { key: "paid_case_count", label: "结清案件数" },
                { key: "base_amount", label: "回款金额" },
                { key: "commission_rate", label: "提成比例" },
                { key: "commission", label: "应发提成" },
              ],
              items.map((it) => ({
                user_id: it.user_id,
                name: it.name,
                phone_masked: it.phone_masked,
                year_month: it.year_month,
                paid_case_count: it.paid_case_count,
                base_amount: it.base_amount,
                commission_rate: `${(it.commission_rate * 100).toFixed(0)}%`,
                commission: it.commission,
              })),
            )
          }
        >
          <Download className="w-3.5 h-3.5" />
          导出
        </button>
      </div>

      {/* 总览 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: 16,
          marginBottom: 16,
        }}
      >
        <SummaryCard
          label="本月已收回款"
          value={data ? formatAmount(data.total_base) : "—"}
          color="#1d4ed8"
        />
        <SummaryCard
          label="应发提成总额"
          value={data ? formatAmount(data.total_commission) : "—"}
          color="#057a55"
        />
        <SummaryCard
          label="涉及员工"
          value={`${items.length} 人`}
          color="#7e22ce"
        />
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>员工</th>
              <th>手机号</th>
              <th>当月已结清案件</th>
              <th>当月回款金额</th>
              <th>提成率</th>
              <th>应发金额</th>
              <th>操作</th>
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
                  本月暂无内部催收员产生提成
                </td>
              </tr>
            )}
            {items.map((it) => (
              <tr key={it.user_id}>
                <td>
                  <strong>{it.name}</strong>
                </td>
                <td style={{ fontFamily: "monospace", fontSize: 12, color: "#6b7280" }}>
                  {it.phone_masked}
                </td>
                <td>{it.paid_case_count}</td>
                <td>{formatAmount(it.base_amount)}</td>
                <td style={{ color: "#6b7280" }}>{(it.commission_rate * 100).toFixed(1)}%</td>
                <td style={{ fontWeight: 700, color: "#057a55" }}>
                  {formatAmount(it.commission)}
                </td>
                <td>
                  <button
                    type="button"
                    className="ds-btn ds-btn-ghost ds-btn-sm"
                    onClick={() => setDetailFor(it)}
                    disabled={it.paid_case_count === 0}
                  >
                    明细
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {detailFor && <CommissionDetailSheet item={detailFor} onClose={() => setDetailFor(null)} />}
    </>
  );
}

function SummaryCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div
      style={{
        background: "white",
        border: "1px solid var(--color-neutral-200)",
        borderRadius: 8,
        padding: "16px 20px",
      }}
    >
      <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

function CommissionDetailSheet({
  item,
  onClose,
}: {
  item: AgentCommissionItem;
  onClose: () => void;
}) {
  const { query } = useCustom<AgentCommissionDetailResp>({
    url: `admin/agent-commissions/${item.user_id}`,
    method: "get",
    config: { query: { year_month: item.year_month } },
  });
  const detail = query.data?.data;
  const lines = detail?.items ?? [];

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        display: "flex",
        justifyContent: "flex-end",
      }}
    >
      <div
        style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.3)" }}
        onClick={onClose}
      />
      <div
        style={{
          position: "relative",
          width: 560,
          height: "100%",
          background: "#fff",
          boxShadow: "-4px 0 24px rgba(0,0,0,0.12)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            padding: "20px 24px",
            borderBottom: "1px solid #e5e7eb",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>
              {item.name} · {item.year_month} 提成明细
            </h2>
            <div style={{ fontSize: 12, color: "#6b7280", marginTop: 4 }}>
              {item.paid_case_count} 个案件 · 回款 {formatAmount(item.base_amount)} · 提成{" "}
              <strong style={{ color: "#057a55" }}>{formatAmount(item.commission)}</strong>
            </div>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer" }}>
            <X size={20} />
          </button>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
          {query.isLoading && <div style={{ color: "#9ca3af" }}>加载中…</div>}
          {!query.isLoading && lines.length === 0 && (
            <div style={{ color: "#9ca3af" }}>本月该员工无 paid 案件</div>
          )}
          <table style={{ width: "100%", fontSize: 13 }}>
            <thead>
              <tr>
                <th>业主</th>
                <th>结清金额</th>
                <th>结清时间</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((ln) => (
                <tr key={ln.case_id}>
                  <td>{ln.owner_name}</td>
                  <td style={{ fontWeight: 600, color: "#057a55" }}>
                    {formatAmount(ln.paid_amount)}
                  </td>
                  <td style={{ color: "#6b7280", fontSize: 12 }}>
                    {new Date(ln.paid_at).toLocaleDateString("zh-CN")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// Tab 3 — 成本汇总（占位）
// ═══════════════════════════════════════════════════════════════

interface CostSummary {
  year_month: string;
  provider_payable_total: string;
  agent_commission_total: string;
  total_cost: string;
  provider_count: number;
  agent_count: number;
  paid_case_count: number;
}

function SummaryTab() {
  const months = useMemo(() => recentYearMonths(6), []);
  const [yearMonth, setYearMonth] = useState<string>(months[0]);
  const { query } = useCustom<CostSummary>({
    url: "admin/cost-summary",
    method: "get",
    config: { query: { year_month: yearMonth } },
  });
  const data = query.data?.data;
  const providerTotal = Number(data?.provider_payable_total ?? 0);
  const agentTotal = Number(data?.agent_commission_total ?? 0);
  const total = Number(data?.total_cost ?? 0);
  const providerPct = total > 0 ? (providerTotal / total) * 100 : 0;
  const agentPct = total > 0 ? (agentTotal / total) * 100 : 0;

  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 20 }}>
        <span style={{ fontSize: 13, color: "#6b7280" }}>选择月份</span>
        <SearchableSelect
          style={{ width: 160 }}
          value={yearMonth}
          onChange={(v) => setYearMonth(String(v))}
          options={months.map((m) => ({ value: m, label: m }))}
        />
      </div>

      {query.isLoading && <p style={{ color: "#9ca3af" }}>加载中…</p>}

      {data && (
        <div>
          <div
            className="grid gap-3"
            style={{ gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}
          >
            <KpiCard label="本月总成本" value={`¥${formatAmount(String(total))}`} tone="primary" />
            <KpiCard
              label="应付服务商"
              value={`¥${formatAmount(String(providerTotal))}`}
              hint={`涉及 ${data.provider_count} 家服务商`}
              tone="info"
            />
            <KpiCard
              label="应发员工提成"
              value={`¥${formatAmount(String(agentTotal))}`}
              hint={`涉及 ${data.agent_count} 名内勤`}
              tone="success"
            />
            <KpiCard
              label="结清案件"
              value={`${data.paid_case_count}`}
              unit="单"
              tone="muted"
            />
          </div>

          <div
            className="bg-white"
            style={{
              marginTop: 24, padding: 20, border: "1px solid #e5e7eb",
              borderRadius: 8,
            }}
          >
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
              成本结构占比
            </h3>
            {total === 0 ? (
              <p style={{ fontSize: 13, color: "#9ca3af" }}>本月暂无支出</p>
            ) : (
              <div>
                <div
                  style={{
                    display: "flex", height: 28, borderRadius: 6, overflow: "hidden",
                    border: "1px solid #e5e7eb",
                  }}
                >
                  {providerTotal > 0 && (
                    <div
                      title={`应付服务商 ¥${formatAmount(String(providerTotal))}`}
                      style={{
                        width: `${providerPct}%`,
                        background: "#3b82f6",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        color: "white", fontSize: 11, fontWeight: 600,
                      }}
                    >
                      {providerPct >= 8 && `${providerPct.toFixed(1)}%`}
                    </div>
                  )}
                  {agentTotal > 0 && (
                    <div
                      title={`应发员工提成 ¥${formatAmount(String(agentTotal))}`}
                      style={{
                        width: `${agentPct}%`,
                        background: "#10b981",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        color: "white", fontSize: 11, fontWeight: 600,
                      }}
                    >
                      {agentPct >= 8 && `${agentPct.toFixed(1)}%`}
                    </div>
                  )}
                </div>
                <div style={{ display: "flex", gap: 16, marginTop: 12, fontSize: 12 }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                    <span style={{ width: 10, height: 10, background: "#3b82f6", borderRadius: 2 }} />
                    应付服务商 ¥{formatAmount(String(providerTotal))}
                  </span>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                    <span style={{ width: 10, height: 10, background: "#10b981", borderRadius: 2 }} />
                    应发员工提成 ¥{formatAmount(String(agentTotal))}
                  </span>
                </div>
              </div>
            )}
          </div>

          <div
            style={{
              marginTop: 16, padding: 12, background: "#f9fafb",
              borderRadius: 6, fontSize: 12, color: "#6b7280",
            }}
          >
            <BarChart3 className="w-3.5 h-3.5" style={{ display: "inline", marginRight: 4 }} />
            提示：此处的应付服务商按 settlement 表口径，应发员工提成按当月已结清案件 × {(0.05 * 100).toFixed(0)}% 算。明细可点对应 tab 下钻。
          </div>
        </div>
      )}
    </div>
  );
}

function KpiCard({
  label, value, hint, unit, tone = "muted",
}: {
  label: string;
  value: string;
  hint?: string;
  unit?: string;
  tone?: "primary" | "info" | "success" | "muted";
}) {
  const colors: Record<string, string> = {
    primary: "#1e40af",
    info: "#3b82f6",
    success: "#10b981",
    muted: "#374151",
  };
  return (
    <div
      style={{
        background: "white", padding: 16, border: "1px solid #e5e7eb",
        borderRadius: 8,
      }}
    >
      <div style={{ fontSize: 12, color: "#6b7280" }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: colors[tone], marginTop: 4 }}>
        {value}
        {unit && <span style={{ fontSize: 13, marginLeft: 4, fontWeight: 400 }}>{unit}</span>}
      </div>
      {hint && (
        <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 4 }}>{hint}</div>
      )}
    </div>
  );
}
