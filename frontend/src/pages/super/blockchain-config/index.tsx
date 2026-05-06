// Sprint 10.6 — 平台超管区块链存证配置（PRD §L1972）
import { useCustom, useCustomMutation } from "@refinedev/core";
import { Link2, Save, AlertTriangle, CheckCircle2 } from "lucide-react";
import { useEffect, useState } from "react";

interface BlockchainConfig {
  id: number;
  provider: string;
  api_endpoint: string;
  has_api_key: boolean;
  is_active: boolean;
  last_failure_at: string | null;
  last_failure_reason: string | null;
  updated_at: string;
}

const PROVIDER_OPTIONS = [
  { value: "antchain", label: "蚂蚁链" },
  { value: "fisco-bcos", label: "FISCO BCOS" },
  { value: "mock", label: "Mock（仅测试）" },
];

export function SuperBlockchainConfigPage() {
  const { query } = useCustom<BlockchainConfig | null>({
    url: "super/blockchain-config",
    method: "get",
  });
  const config = query.data?.data ?? null;

  const [provider, setProvider] = useState("antchain");
  const [endpoint, setEndpoint] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [isActive, setIsActive] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (config) {
      setProvider(config.provider);
      setEndpoint(config.api_endpoint);
      setIsActive(config.is_active);
    }
  }, [config]);

  const { mutate: save, mutation } = useCustomMutation();

  const submit = () => {
    setError("");
    if (!endpoint) {
      setError("API endpoint 不能为空");
      return;
    }
    save(
      {
        url: "super/blockchain-config",
        method: "put",
        values: {
          provider,
          api_endpoint: endpoint,
          api_key: apiKey || null,
          is_active: isActive,
        },
      },
      {
        onSuccess: () => {
          setSavedAt(new Date().toLocaleTimeString("zh-CN"));
          setApiKey("");
          query.refetch();
        },
        onError: () => setError("保存失败"),
      },
    );
  };

  if (query.isLoading) {
    return <div className="p-6 text-[var(--color-neutral-400)]">加载中…</div>;
  }

  return (
    <div className="p-6 max-w-2xl space-y-4">
      <div className="flex items-center gap-2">
        <Link2 className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold">区块链存证配置</h1>
      </div>

      {!config ? (
        <div
          className="p-4 bg-[var(--color-warning-light)] text-sm flex items-center gap-2"
          style={{
            borderRadius: "var(--radius-md)",
            color: "var(--color-warning)",
          }}
        >
          <AlertTriangle className="w-4 h-4" />
          尚未配置区块链存证。配置后存证包 attestation.json 将携带 provider 元数据。
        </div>
      ) : config.is_active ? (
        <div
          className="p-4 bg-[var(--color-success-light)] text-sm flex items-center gap-2"
          style={{
            borderRadius: "var(--radius-md)",
            color: "var(--color-success)",
          }}
        >
          <CheckCircle2 className="w-4 h-4" />
          当前激活：{config.provider}
        </div>
      ) : null}

      {config?.last_failure_at && (
        <div
          className="p-3 bg-[var(--color-danger-light)] text-sm"
          style={{
            borderRadius: "var(--radius-md)",
            color: "var(--color-danger)",
          }}
        >
          最近失败：{config.last_failure_at?.slice(0, 19).replace("T", " ")} ·
          {config.last_failure_reason}
        </div>
      )}

      <div
        className="bg-white p-5 border border-[var(--color-neutral-200)] space-y-4"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            服务提供商
          </label>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            {PROVIDER_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            API Endpoint
          </label>
          <input
            type="url"
            value={endpoint}
            onChange={(e) => setEndpoint(e.target.value)}
            placeholder="https://api.antchain.example/attest"
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            API Key
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={
              config?.has_api_key
                ? "••••••（已配置，留空保持不变）"
                : "请输入 API key"
            }
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
          <p className="text-xs text-[var(--color-neutral-400)] mt-1">
            提交后服务端 AES-256 加密落库；查询接口仅返回是否已配置
          </p>
        </div>

        <div>
          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="w-4 h-4"
            />
            激活此配置
          </label>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex items-center justify-between">
          {savedAt ? (
            <span className="text-xs text-[var(--color-success)]">
              已保存 ({savedAt})
            </span>
          ) : (
            <span />
          )}
          <button
            type="button"
            onClick={submit}
            disabled={mutation.isPending}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            <Save className="w-4 h-4" />
            {mutation.isPending ? "保存中…" : "保存配置"}
          </button>
        </div>
      </div>
    </div>
  );
}
