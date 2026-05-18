// 短信通道 — 平台超管短信中心（028lk）配置
import { useCustom, useCustomMutation } from "@refinedev/core";
import { MessageSquare, Save, AlertTriangle, CheckCircle2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

interface SmsConfig {
  id: number;
  secret_name: string;
  sign_name: string;
  otp_template_id: string | null;
  has_secret_key: boolean;
  is_active: boolean;
  last_failure_at: string | null;
  last_failure_reason: string | null;
  updated_at: string;
}

export function SuperSmsConfigPage() {
  const { query } = useCustom<SmsConfig>({
    url: "super/sms-config",
    method: "get",
  });
  const config = query.data?.data ?? null;

  const [secretName, setSecretName] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [signName, setSignName] = useState("");
  const [otpTemplateId, setOtpTemplateId] = useState("");
  const [isActive, setIsActive] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [error, setError] = useState("");

  const initRef = useRef(false);
  useEffect(() => {
    if (config && !initRef.current) {
      initRef.current = true;
      setSecretName(config.secret_name);
      setSignName(config.sign_name);
      setOtpTemplateId(config.otp_template_id ?? "");
      setIsActive(config.is_active);
    }
  }, [config]);

  const { mutate: save, mutation } = useCustomMutation();

  const submit = () => {
    setError("");
    if (!secretName) {
      setError("短信中心账户名不能为空");
      return;
    }
    save(
      {
        url: "super/sms-config",
        method: "put",
        values: {
          secret_name: secretName,
          secret_key: secretKey || null,
          sign_name: signName,
          otp_template_id: otpTemplateId || null,
          is_active: isActive,
        },
      },
      {
        onSuccess: () => {
          setSavedAt(new Date().toLocaleTimeString("zh-CN"));
          setSecretKey("");
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
        <MessageSquare className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold">短信配置</h1>
      </div>

      {!config ? (
        <div
          className="p-4 bg-[var(--color-warning-light)] text-sm flex items-center gap-2"
          style={{ borderRadius: "var(--radius-md)", color: "var(--color-warning)" }}
        >
          <AlertTriangle className="w-4 h-4" />
          尚未配置短信中心。配置并激活后，登录 / 密码重置验证码方可经短信送达。
        </div>
      ) : config.is_active ? (
        <div
          className="p-4 bg-[var(--color-success-light)] text-sm flex items-center gap-2"
          style={{ borderRadius: "var(--radius-md)", color: "var(--color-success)" }}
        >
          <CheckCircle2 className="w-4 h-4" />
          短信通道已激活
        </div>
      ) : null}

      {config?.last_failure_at && (
        <div
          className="p-3 bg-[var(--color-danger-light)] text-sm"
          style={{ borderRadius: "var(--radius-md)", color: "var(--color-danger)" }}
        >
          最近失败：{config.last_failure_at?.slice(0, 19).replace("T", " ")} ·{" "}{config.last_failure_reason}
        </div>
      )}

      <div
        className="bg-white p-5 border border-[var(--color-neutral-200)] space-y-4"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            短信中心账户名（SecretName）
          </label>
          <input
            type="text"
            value={secretName}
            onChange={(e) => setSecretName(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            密钥（SecretKey）
          </label>
          <input
            type="password"
            autoComplete="new-password"
            value={secretKey}
            onChange={(e) => setSecretKey(e.target.value)}
            placeholder={
              config?.has_secret_key ? "••••••（已配置，留空保持不变）" : "请输入密钥"
            }
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
          <p className="text-xs text-[var(--color-neutral-400)] mt-1">
            提交后服务端 AES-256 加密落库；查询接口仅返回是否已配置
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            短信签名
          </label>
          <input
            type="text"
            value={signName}
            onChange={(e) => setSignName(e.target.value)}
            placeholder="如：有证慧催"
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            OTP 验证码模板 ID
          </label>
          <input
            type="text"
            value={otpTemplateId}
            onChange={(e) => setOtpTemplateId(e.target.value)}
            placeholder="留空则用直接文本模式发送"
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>

        <div>
          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="w-4 h-4"
            />
            激活短信通道
          </label>
        </div>

        {error && (
          <p className="text-sm" style={{ color: "var(--color-danger)" }}>{error}</p>
        )}

        <div className="flex items-center justify-between">
          {savedAt ? (
            <span className="text-xs text-[var(--color-success)]">已保存 ({savedAt})</span>
          ) : (
            <span />
          )}
          <button
            type="button"
            onClick={submit}
            disabled={mutation.isPending}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            style={{ background: "var(--color-primary)", borderRadius: "var(--radius-md)" }}
          >
            <Save className="w-4 h-4" />
            {mutation.isPending ? "保存中…" : "保存配置"}
          </button>
        </div>
      </div>
    </div>
  );
}
