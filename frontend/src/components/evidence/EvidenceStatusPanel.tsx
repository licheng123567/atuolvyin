// v0.8.0 — 法务案件证据状态面板(诉讼证据中心)
//
// 数据源:GET /api/v1/legal/cases/{id}/evidence-status
// 操作:POST /api/v1/legal/cases/{id}/attest(打包上链)+ 下载存证包 + 证据清单
//
// 设计原则:
// - 强弱对比明显:本地哈希(弱)vs 司法链(强)颜色 + 文案双重提示
// - 法律视角文案:不堆 tx_hash 等技术细节;讲「这案件能不能打官司」
// - 一键升级:法务点「打包上链 ¥99」即把弱证据全升强(幂等,不重扣费)
import { useCustom, useCustomMutation } from "@refinedev/core";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { getToken } from "../../providers/auth-provider";

interface CategoryItem {
  category: string;
  total: number;
  confirmed: number;  // 已上链
  pending: number;    // 已标记待上链
  local_only: number; // 仅本地哈希
}

interface EvidenceStatusResp {
  legal_case_id: number;
  case_id: number;
  categories: CategoryItem[];
  latest_attestation_at: string | null;
  latest_chain_provider: string | null;
  has_any_confirmed: boolean;
  has_any_pending: boolean;
}

interface AttestStats {
  attested: number;
  already_attested: number;
  failed: number;
  total_cost: string;
  attestation_ids: number[];
}

const PRICE_PER_BUNDLE = "99";  // ¥99/案,与 BillingPricing 一致

export function EvidenceStatusPanel({
  legalCaseId,
}: {
  legalCaseId: number;
}) {
  const { query } = useCustom<EvidenceStatusResp>({
    url: `legal/cases/${legalCaseId}/evidence-status`,
    method: "get",
    queryOptions: { enabled: legalCaseId > 0, retry: false },
  });

  const { mutate: attestMutate, mutation: attestMutation } = useCustomMutation();
  const [attestResult, setAttestResult] = useState<AttestStats | null>(null);
  const [downloadingBundle, setDownloadingBundle] = useState(false);
  const [bundleError, setBundleError] = useState("");

  const data = query.data?.data;

  if (query.isLoading) {
    return (
      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-5 mb-4">
        <div className="text-sm text-[var(--color-neutral-400)]">证据状态加载中…</div>
      </div>
    );
  }
  if (!data) return null;

  const hasStrong = data.has_any_confirmed;
  const hasPending = data.has_any_pending;
  const totalCategories = data.categories.reduce((s, c) => s + c.total, 0);
  const totalConfirmed = data.categories.reduce((s, c) => s + c.confirmed, 0);
  const totalLocalOnly = data.categories.reduce((s, c) => s + c.local_only, 0);

  const handleAttest = () => {
    if (!confirm(
      `确认打包上链?\n\n` +
      `将本案件所有未上链的录音 / 转写 / AI 分析批量上链(易保全司法链),` +
      `按计费单价扣费(单次 ¥5 或案件包 ¥${PRICE_PER_BUNDLE},以实际生成 attestation 数为准)。\n\n` +
      `已上链的会跳过(幂等,不重复扣费)。`
    )) return;

    attestMutate(
      {
        url: `legal/cases/${legalCaseId}/attest`,
        method: "post",
        values: {},
      },
      {
        onSuccess: (resp) => {
          const stats = resp.data as unknown as AttestStats;
          setAttestResult(stats);
          void query.refetch();
        },
        onError: (err) => {
          alert(`上链失败:${(err as { message?: string }).message ?? "请重试"}`);
        },
      },
    );
  };

  const handleDownloadBundle = async () => {
    setBundleError("");
    setDownloadingBundle(true);
    try {
      const token = getToken() ?? "";
      const apiBase = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";
      const resp = await fetch(
        `${apiBase}/api/v1/legal/cases/${legalCaseId}/evidence-bundle`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!resp.ok) {
        setBundleError(`下载失败:${resp.status}`);
        return;
      }
      const cd = resp.headers.get("content-disposition") ?? "";
      const fm = cd.match(/filename="([^"]+)"/);
      const filename = fm?.[1] ?? `evidence_legal_${legalCaseId}.zip`;
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setBundleError((err as Error).message);
    } finally {
      setDownloadingBundle(false);
    }
  };

  const handleDownloadReceipt = async () => {
    setBundleError("");
    try {
      const token = getToken() ?? "";
      const apiBase = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";
      // 直接在新 tab 打开 — 浏览器渲染 HTML 后用户「打印为 PDF」
      const url = `${apiBase}/api/v1/legal/cases/${legalCaseId}/evidence-receipt?token=${encodeURIComponent(token)}`;
      window.open(url, "_blank");
    } catch (err) {
      setBundleError((err as Error).message);
    }
  };

  return (
    <div
      className="bg-white rounded-lg border-l-4 p-5 mb-4"
      style={{
        borderTopWidth: 1,
        borderRightWidth: 1,
        borderBottomWidth: 1,
        borderTopColor: "var(--color-neutral-200)",
        borderRightColor: "var(--color-neutral-200)",
        borderBottomColor: "var(--color-neutral-200)",
        borderLeftColor: hasStrong ? "var(--color-success)" : "#dc2626",
      }}
    >
      {/* 顶部:总状态 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {hasStrong ? (
            <>
              <ShieldCheck className="w-5 h-5 text-[var(--color-success)]" />
              <strong className="text-base">本案件证据状态:已强化为司法链证据</strong>
            </>
          ) : (
            <>
              <ShieldAlert className="w-5 h-5 text-red-600" />
              <strong className="text-base">本案件证据状态:仅本地哈希(法庭可被质疑)</strong>
            </>
          )}
        </div>
        {hasStrong && data.latest_chain_provider && (
          <span className="text-xs text-[var(--color-neutral-500)]">
            链上服务商:{data.latest_chain_provider === "ebaoquan" ? "易保全(司法链)" : data.latest_chain_provider}
            {data.latest_attestation_at && (
              <> · 最近上链 {new Date(data.latest_attestation_at).toLocaleString("zh-CN")}</>
            )}
          </span>
        )}
      </div>

      {/* 4 类证据数量对比 */}
      <table className="w-full text-sm mb-3">
        <thead className="text-xs text-[var(--color-neutral-500)]">
          <tr>
            <th className="text-left py-1">数据类型</th>
            <th className="text-right py-1">数量</th>
            <th className="text-right py-1">本地哈希</th>
            <th className="text-right py-1">待上链</th>
            <th className="text-right py-1">司法链</th>
            <th className="text-left py-1 pl-3">法律效力</th>
          </tr>
        </thead>
        <tbody>
          {data.categories.map((c) => {
            const allStrong = c.total > 0 && c.confirmed === c.total;
            const allLocal = c.confirmed === 0 && c.pending === 0;
            return (
              <tr key={c.category} className="border-t border-[var(--color-neutral-100)]">
                <td className="py-2">{c.category}</td>
                <td className="text-right font-mono">{c.total}</td>
                <td className="text-right font-mono text-[var(--color-neutral-500)]">
                  {c.local_only > 0 ? `✓ ${c.local_only}` : "—"}
                </td>
                <td className="text-right font-mono text-[var(--color-warning)]">
                  {c.pending > 0 ? `⏳ ${c.pending}` : "—"}
                </td>
                <td className="text-right font-mono text-[var(--color-success)]">
                  {c.confirmed > 0 ? `🔗 ${c.confirmed}` : "—"}
                </td>
                <td className="pl-3 text-xs">
                  {c.total === 0 ? (
                    <span className="text-[var(--color-neutral-400)]">无数据</span>
                  ) : allStrong ? (
                    <span className="text-[var(--color-success)] font-medium">🟢 强证据</span>
                  ) : allLocal ? (
                    <span className="text-red-600">⚠️ 弱(可被质疑)</span>
                  ) : (
                    <span className="text-[var(--color-warning)] font-medium">🟡 混合(部分强)</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* 警示 / 成功提示框 */}
      {!hasStrong && totalCategories > 0 && (
        <div
          className="text-xs p-3 rounded mb-3"
          style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#7f1d1d" }}
        >
          <strong>⚠️ 法律效力提示:</strong> 当前证据均为本地哈希,法庭上对方律师可质疑「单方面计算的哈希,如何证明未篡改」。
          <br />
          如本案件**已进入诉讼 / 律师函阶段**,强烈建议「打包上链」升级为司法链强证据:
          <ul className="list-disc pl-5 mt-1">
            <li>易保全司法链 — 最高法 2018 第11号文确认,互联网法院**直接接受**</li>
            <li>律师函 / 起诉状可直接附 tx_hash 作证据链,免后续司法鉴定</li>
            <li>对方律师无法以「单方面证据」为由要求重新鉴定</li>
          </ul>
        </div>
      )}

      {hasStrong && (
        <div
          className="text-xs p-3 rounded mb-3"
          style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", color: "#14532d" }}
        >
          <CheckCircle2 className="w-3.5 h-3.5 inline mr-1" />
          <strong>已强化为司法链证据。</strong>共 {totalConfirmed} 件上链,可在律师函 / 起诉状直接附 tx_hash 作证据链。
          {totalLocalOnly > 0 && (
            <span className="block mt-1 text-[var(--color-warning)]">
              ⚠️ 仍有 {totalLocalOnly} 件仅本地哈希,如需完全无可质疑请再次「打包上链」(幂等,只对未上链数据扣费)。
            </span>
          )}
        </div>
      )}

      {hasPending && (
        <div
          className="text-xs p-3 rounded mb-3"
          style={{ background: "#fffbeb", border: "1px solid #fde68a", color: "#78350f" }}
        >
          <Sparkles className="w-3.5 h-3.5 inline mr-1" />
          <strong>本案件含 L2 风险事件已被督导标记「待上链」</strong>(零成本标记)。
          点「打包上链」时一并升级为司法链证据。
        </div>
      )}

      {/* 操作按钮 */}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white rounded disabled:opacity-50"
          style={{
            background: hasStrong && totalLocalOnly === 0 ? "#9ca3af" : "var(--color-primary)",
          }}
          onClick={handleAttest}
          disabled={attestMutation.isPending}
          title={
            hasStrong && totalLocalOnly === 0
              ? "本案件证据已全部上链,无需重复操作"
              : `打包上链:把所有未上链证据升级为司法链强证据(¥${PRICE_PER_BUNDLE}/案)`
          }
        >
          {attestMutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <ShieldCheck className="w-4 h-4" />
          )}
          {attestMutation.isPending
            ? "正在上链…"
            : hasStrong && totalLocalOnly === 0
              ? "已全部上链"
              : `打包上链 ¥${PRICE_PER_BUNDLE}`}
        </button>

        <button
          type="button"
          className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-50)] disabled:opacity-50"
          onClick={handleDownloadBundle}
          disabled={downloadingBundle}
        >
          {downloadingBundle ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
          {downloadingBundle ? "打包中…" : "下载证据包 ZIP"}
        </button>

        <button
          type="button"
          className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-50)]"
          onClick={handleDownloadReceipt}
          title="生成证据清单 HTML(浏览器打开后可「打印为 PDF」,法务交给律师 / 法庭用)"
        >
          <FileText className="w-4 h-4" />
          生成证据清单
        </button>

        {bundleError && (
          <span className="text-xs text-red-600 self-center">
            <AlertTriangle className="w-3 h-3 inline" /> {bundleError}
          </span>
        )}
      </div>

      {/* 上链结果反馈 */}
      {attestResult && (
        <div
          className="text-xs p-3 rounded mt-3"
          style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", color: "#14532d" }}
        >
          ✅ 上链完成:本次新上链 <strong>{attestResult.attested}</strong> 件
          {attestResult.already_attested > 0 && (
            <> · 已上链跳过 {attestResult.already_attested} 件</>
          )}
          {attestResult.failed > 0 && (
            <span className="text-red-600"> · 失败 {attestResult.failed} 件</span>
          )}
          {Number(attestResult.total_cost) > 0 && (
            <> · 本次费用 <strong>¥{attestResult.total_cost}</strong></>
          )}
          。律师函 / 起诉状可直接附 tx_hash 作证据链。
        </div>
      )}
    </div>
  );
}

export default EvidenceStatusPanel;
