// Sprint 15 — System health monitoring page (SA.1.1)
import { useCustom } from "@refinedev/core";
import {
  Activity,
  Cpu,
  Database,
  MessageSquare,
  RefreshCw,
  Wifi,
} from "lucide-react";
import type { ReactNode } from "react";
import { formatLatency, formatPercent, getStatusDotColor } from "../helpers";

interface BackendHealth {
  status: "ok" | "degraded" | "down";
  backend: string;
  last_check_at: string | null;
}

interface ServiceHealth {
  db: { status: "ok" | "degraded" | "down"; latency_ms: number };
  asr: BackendHealth;
  llm: BackendHealth;
  mipush: BackendHealth;
  websocket: { status: "ok" | "degraded" | "down"; connected_clients: number };
}

interface ServiceMetrics {
  asr_p90_sec: number;
  asr_error_rate_24h: number;
  llm_avg_latency_ms: number;
}

const STATUS_LABEL: Record<string, string> = {
  ok: "正常",
  degraded: "降级",
  down: "故障",
};

export function SuperHealthPage() {
  const svcQuery = useCustom<ServiceHealth>({
    url: "super/health/services",
    method: "get",
  });
  const metricsQuery = useCustom<ServiceMetrics>({
    url: "super/health/metrics",
    method: "get",
  });

  const svcLoading = svcQuery.query.isLoading;
  const metricsLoading = metricsQuery.query.isLoading;
  const services = svcQuery.query.data?.data;
  const metrics = metricsQuery.query.data?.data;

  const handleRefresh = () => {
    svcQuery.query.refetch();
    metricsQuery.query.refetch();
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            系统健康监控
          </h1>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          className="flex items-center gap-1.5 px-3 py-2 text-sm border border-[var(--color-neutral-200)] rounded hover:bg-[var(--color-neutral-50)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          <RefreshCw className="w-4 h-4" />
          刷新
        </button>
      </div>

      <p className="text-xs text-[var(--color-neutral-400)]">
        本期暂用模拟数据：ASR/LLM/MiPush 仅展示 dispatcher 后端类型；WebSocket 客户端数为占位符。
      </p>

      {/* Service status grid (5 cards) */}
      {svcLoading || !services ? (
        <div className="text-sm text-[var(--color-neutral-500)]">加载中…</div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)",
            gap: 16,
          }}
        >
          <ServiceCard
            icon={<Database className="w-4 h-4" />}
            label="数据库 (DB)"
            status={services.db.status}
            sub={`延迟 ${formatLatency(services.db.latency_ms)}`}
          />
          <ServiceCard
            icon={<Cpu className="w-4 h-4" />}
            label="ASR 服务"
            status={services.asr.status}
            sub={`后端: ${services.asr.backend}`}
          />
          <ServiceCard
            icon={<Cpu className="w-4 h-4" />}
            label="LLM 服务"
            status={services.llm.status}
            sub={`后端: ${services.llm.backend}`}
          />
          <ServiceCard
            icon={<MessageSquare className="w-4 h-4" />}
            label="MiPush"
            status={services.mipush.status}
            sub={`后端: ${services.mipush.backend}`}
          />
          <ServiceCard
            icon={<Wifi className="w-4 h-4" />}
            label="WebSocket"
            status={services.websocket.status}
            sub={`在线: ${services.websocket.connected_clients}`}
          />
        </div>
      )}

      {/* Metric KPIs */}
      <div>
        <h2 className="text-base font-medium text-[var(--color-neutral-900)] mb-3">
          性能指标 (近 24h)
        </h2>
        {metricsLoading || !metrics ? (
          <div className="text-sm text-[var(--color-neutral-500)]">加载中…</div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: 16,
            }}
          >
            <MetricCard
              label="ASR P90 时长"
              value={`${metrics.asr_p90_sec.toFixed(1)} 秒`}
            />
            <MetricCard
              label="ASR 错误率"
              value={formatPercent(metrics.asr_error_rate_24h * 100)}
            />
            <MetricCard
              label="LLM 平均延迟"
              value={`${metrics.llm_avg_latency_ms.toFixed(0)} ms`}
            />
          </div>
        )}
      </div>
    </div>
  );
}

function ServiceCard({
  icon,
  label,
  status,
  sub,
}: {
  icon: ReactNode;
  label: string;
  status: "ok" | "degraded" | "down";
  sub: string;
}) {
  return (
    <div
      className="bg-white p-4 rounded-lg border border-[var(--color-neutral-200)]"
      style={{ borderRadius: "var(--radius-md)" }}
    >
      <div className="flex items-center gap-2 text-xs text-[var(--color-neutral-500)] mb-1">
        {icon}
        {label}
      </div>
      <div className="flex items-center gap-2 mt-2">
        <span
          aria-label={`status-${status}`}
          className={`inline-block w-2.5 h-2.5 rounded-full ${getStatusDotColor(status)}`}
        />
        <span className="text-base font-semibold">{STATUS_LABEL[status] ?? status}</span>
      </div>
      <div className="text-xs text-[var(--color-neutral-400)] mt-1">{sub}</div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="bg-white p-4 rounded-lg border border-[var(--color-neutral-200)]"
      style={{ borderRadius: "var(--radius-md)" }}
    >
      <div className="text-xs text-[var(--color-neutral-500)]">{label}</div>
      <div className="text-2xl font-semibold text-[var(--color-neutral-900)] mt-1">
        {value}
      </div>
    </div>
  );
}
