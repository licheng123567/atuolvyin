// 共享 KPI 卡片组件 — 用于提成/佣金汇总数字展示

interface KpiProps {
  label: string;
  value: string;
  highlight?: boolean;
}

export function Kpi({ label, value, highlight }: KpiProps) {
  return (
    <div
      className="p-4 rounded"
      style={{
        background: highlight
          ? "var(--color-primary-light)"
          : "var(--color-neutral-50)",
      }}
    >
      <p className="text-xs text-[var(--color-neutral-500)] mb-1">{label}</p>
      <p
        className="text-2xl font-bold"
        style={{
          color: highlight
            ? "var(--color-primary)"
            : "var(--color-neutral-900)",
        }}
      >
        {value}
      </p>
    </div>
  );
}
