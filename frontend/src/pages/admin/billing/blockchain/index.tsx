// v0.8.0 Wave C — 「存证管理」(由 v0.5.9「存证消费」升级而来)
//
// 双 tab 结构:
//   - 计费视图(BillingTab):月度存证次数/金额/服务商/明细(原 index.tsx 内容)
//   - 风险敞口(RiskExposureTab):本月案件证据强度分布 + 高风险未上链 Top 10
//
// 月份选择上移至父容器,两 tab 共享 yearMonth state。
import { Shield } from "lucide-react";
import { useState } from "react";
import { BillingTab } from "./BillingTab";
import { RiskExposureTab } from "./RiskExposureTab";

type TabKey = "billing" | "risk";

function currentMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function AdminBillingBlockchainPage() {
  const [ym, setYm] = useState(currentMonth());
  const [tab, setTab] = useState<TabKey>("billing");

  return (
    <div className="p-6 space-y-4">
      {/* 页头 */}
      <div className="flex items-center gap-3">
        <Shield className="w-6 h-6 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">存证管理</h1>
        <span className="text-sm text-[var(--color-neutral-500)]">
          区块链 / 易保全 月度计费 + 风险敞口
        </span>
        <input
          type="month"
          value={ym}
          onChange={(e) => setYm(e.target.value)}
          className="ml-auto px-3 py-1.5 text-sm border border-[var(--color-neutral-300)] rounded"
        />
      </div>

      {/* Tab 切换 */}
      <div
        style={{
          display: "flex",
          gap: 0,
          borderBottom: "1px solid var(--color-neutral-200)",
        }}
      >
        <TabButton
          active={tab === "billing"}
          onClick={() => setTab("billing")}
          label="计费视图"
          hint="本月花了多少钱"
        />
        <TabButton
          active={tab === "risk"}
          onClick={() => setTab("risk")}
          label="风险敞口"
          hint="多少案件证据不够强"
        />
      </div>

      {/* Tab 内容 */}
      {tab === "billing" ? (
        <BillingTab yearMonth={ym} />
      ) : (
        <RiskExposureTab yearMonth={ym} />
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  label,
  hint,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  hint: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: "10px 18px",
        background: "transparent",
        border: "none",
        borderBottom: active
          ? "2px solid var(--color-primary)"
          : "2px solid transparent",
        marginBottom: -1,
        cursor: "pointer",
        color: active ? "var(--color-primary)" : "var(--color-neutral-600)",
        fontWeight: active ? 600 : 500,
        fontSize: 14,
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-start",
        gap: 2,
      }}
    >
      <span>{label}</span>
      <span
        style={{
          fontSize: 11,
          fontWeight: 400,
          color: "var(--color-neutral-400)",
        }}
      >
        {hint}
      </span>
    </button>
  );
}

export default AdminBillingBlockchainPage;
