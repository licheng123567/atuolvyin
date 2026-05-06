import { useCreate, useGo } from "@refinedev/core";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";

interface FormData {
  keyword: string;
  category: string;
  speaker: string;
}

const CATEGORIES = [
  { value: "owner_abuse", label: "业主辱骂（L1）" },
  { value: "owner_threat", label: "业主威胁（L2）" },
  { value: "agent_violation", label: "催收员违规（L2）" },
  { value: "agent_minor_misconduct", label: "催收员轻微不当（L1）" },
];

export function RiskKeywordCreatePage() {
  const go = useGo();
  const { mutate: createKw, mutation: createMutation } = useCreate();
  const isPending = createMutation.isPending;
  const [form, setForm] = useState<FormData>({
    keyword: "",
    category: "owner_threat",
    speaker: "customer",
  });
  const [errorMsg, setErrorMsg] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");
    if (!form.keyword.trim()) {
      setErrorMsg("请输入关键词");
      return;
    }
    createKw(
      { resource: "admin/risk-keywords", values: form },
      {
        onSuccess: () => go({ to: "/admin/risk-keywords" }),
        onError: (err) => {
          const e = err as { message?: string };
          setErrorMsg(e.message ?? "创建失败，请重试");
        },
      },
    );
  };

  return (
    <div className="max-w-lg">
      <div className="flex items-center gap-3 mb-6">
        <button
          type="button"
          onClick={() => go({ to: "/admin/risk-keywords" })}
          className="text-[var(--color-neutral-500)] hover:text-[var(--color-neutral-900)] transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          新增风控关键词
        </h1>
      </div>

      <form
        onSubmit={handleSubmit}
        className="bg-white rounded-lg border p-6 space-y-4"
        style={{ borderColor: "var(--color-neutral-200)", borderRadius: "var(--radius-md)" }}
      >
        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            关键词 *
          </label>
          <input
            type="text"
            required
            maxLength={64}
            value={form.keyword}
            onChange={(e) => setForm({ ...form, keyword: e.target.value })}
            className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2"
            style={{
              borderColor: "var(--color-neutral-300)",
              borderRadius: "var(--radius-md)",
            }}
            placeholder="如：投诉、威胁..."
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            场景分类 *
          </label>
          <select
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
            className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2"
            style={{
              borderColor: "var(--color-neutral-300)",
              borderRadius: "var(--radius-md)",
            }}
          >
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            检测说话人 *
          </label>
          <select
            value={form.speaker}
            onChange={(e) => setForm({ ...form, speaker: e.target.value })}
            className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2"
            style={{
              borderColor: "var(--color-neutral-300)",
              borderRadius: "var(--radius-md)",
            }}
          >
            <option value="customer">业主端</option>
            <option value="agent">催收员端</option>
          </select>
        </div>

        {errorMsg && (
          <p className="text-sm" style={{ color: "var(--color-danger)" }}>
            {errorMsg}
          </p>
        )}

        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={isPending}
            className="flex-1 py-2 text-sm font-medium text-white disabled:opacity-50 transition-colors rounded-md"
            style={{
              background: "var(--color-danger)",
              borderRadius: "var(--radius-md)",
            }}
          >
            {isPending ? "保存中..." : "保存"}
          </button>
          <button
            type="button"
            onClick={() => go({ to: "/admin/risk-keywords" })}
            className="px-4 py-2 text-sm border rounded-md text-[var(--color-neutral-600)] hover:bg-[var(--color-neutral-50)] transition-colors"
            style={{ borderColor: "var(--color-neutral-200)", borderRadius: "var(--radius-md)" }}
          >
            取消
          </button>
        </div>
      </form>
    </div>
  );
}
