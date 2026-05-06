// Sprint 13.1 — 区块链存证公开核验入口（PRD §20.3 v1.1）
// 无需登录；接受 URL 参数 :tx_hash 直接查询，或在页面输入框查询。
import { CheckCircle2, FileCheck2, Search, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:18000";

interface VerifyResp {
  tx_hash: string;
  block_height: number;
  chain_provider: string;
  chain_endpoint: string | null;
  data_sha256: string;
  data_type: string;
  status: string;
  submitted_at: string;
  confirmed_at: string | null;
  tenant_name: string | null;
  call_id: number | null;
  started_at: string | null;
  duration_sec: number | null;
}

const TX_HASH_RE = /^[0-9a-f]{64}$/;

export function VerifyPage() {
  const params = useParams<{ tx_hash?: string }>();
  const navigate = useNavigate();
  const [input, setInput] = useState(params.tx_hash ?? "");
  const [data, setData] = useState<VerifyResp | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (params.tx_hash) {
      void doVerify(params.tx_hash);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.tx_hash]);

  const doVerify = async (txHash: string) => {
    const trimmed = txHash.trim().toLowerCase();
    if (!TX_HASH_RE.test(trimmed)) {
      setError("tx_hash 格式不合法（应为 64 位 16 进制字符）");
      setData(null);
      return;
    }
    setLoading(true);
    setError("");
    setData(null);
    try {
      const resp = await fetch(`${API_BASE}/api/v1/public/verify/${trimmed}`);
      if (resp.status === 404) {
        setError("未找到该 tx_hash 的存证记录");
        return;
      }
      if (!resp.ok) {
        setError(`查询失败（HTTP ${resp.status}）`);
        return;
      }
      const json = (await resp.json()) as VerifyResp;
      setData(json);
    } catch (e) {
      setError(`网络错误：${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const v = input.trim().toLowerCase();
    if (v && v !== params.tx_hash) {
      navigate(`/verify/${v}`);
    } else {
      void doVerify(v);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-3">
            <ShieldAlert className="w-7 h-7 text-blue-600" />
            <h1 className="text-2xl font-bold text-gray-900">
              区块链存证核验
            </h1>
          </div>
          <p className="text-sm text-gray-600">
            输入存证回执上的 tx_hash，校验录音/转写/分析数据的链上证明。
            <br />
            本页面公开访问，可向业主或法庭出示作为存证证据。
          </p>
        </div>

        <form
          onSubmit={onSubmit}
          className="bg-white rounded-lg shadow-sm p-5 mb-6 border border-gray-200"
        >
          <label className="block text-sm font-medium text-gray-700 mb-2">
            交易哈希（tx_hash）
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="例如 a3f8b9... (64 位 16 进制字符)"
              className="flex-1 px-3 py-2 text-sm font-mono border border-gray-300 rounded focus:border-blue-500 focus:outline-none"
              autoComplete="off"
              spellCheck={false}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-1"
            >
              <Search className="w-4 h-4" />
              {loading ? "查询中…" : "核验"}
            </button>
          </div>
        </form>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-sm text-red-800">
            {error}
          </div>
        )}

        {data && (
          <div className="bg-white rounded-lg shadow-sm border border-green-300 overflow-hidden">
            <div className="bg-green-50 px-5 py-3 border-b border-green-200 flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-green-600" />
              <span className="text-sm font-semibold text-green-800">
                存证有效 · 状态：{data.status}
              </span>
            </div>
            <div className="p-5 space-y-4">
              <Row label="链上交易哈希" value={data.tx_hash} mono />
              <Row label="数据 SHA-256" value={data.data_sha256} mono />
              <Row label="区块高度" value={String(data.block_height)} />
              <Row
                label="存证类型"
                value={describeDataType(data.data_type)}
              />
              <Row label="链方提供商" value={data.chain_provider} />
              {data.chain_endpoint && (
                <Row label="链方接入点" value={data.chain_endpoint} mono />
              )}
              <Row
                label="提交时间"
                value={fmtTime(data.submitted_at)}
              />
              {data.confirmed_at && (
                <Row label="确认时间" value={fmtTime(data.confirmed_at)} />
              )}
              <hr className="my-2" />
              <Row label="数据归属租户" value={data.tenant_name ?? "—"} />
              {data.call_id && (
                <Row label="通话 ID" value={String(data.call_id)} />
              )}
              {data.started_at && (
                <Row label="通话开始时间" value={fmtTime(data.started_at)} />
              )}
              {data.duration_sec != null && (
                <Row label="通话时长" value={`${data.duration_sec} 秒`} />
              )}

              <div className="mt-6 p-3 bg-blue-50 border border-blue-200 rounded text-xs text-blue-800 flex items-start gap-2">
                <FileCheck2 className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <div>
                  本回执确认 SHA-256 为「{data.data_sha256.slice(0, 16)}…」的数据
                  在 {fmtTime(data.submitted_at)} 已提交至{data.chain_provider}链。
                  您可使用 <code className="bg-white px-1 rounded">sha256sum</code>
                  自行计算原始数据哈希，并与上方 SHA-256 比对，从而独立验证数据未被篡改。
                </div>
              </div>
            </div>
          </div>
        )}

        {!data && !error && !loading && !params.tx_hash && (
          <div className="text-center text-sm text-gray-500 py-8">
            请输入存证 tx_hash 查询。
          </div>
        )}
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-3">
      <div className="text-xs text-gray-500 sm:w-32 flex-shrink-0">{label}</div>
      <div
        className={`text-sm text-gray-900 break-all ${mono ? "font-mono" : ""}`}
      >
        {value}
      </div>
    </div>
  );
}

function describeDataType(t: string): string {
  switch (t) {
    case "call_recording":
      return "通话录音";
    case "transcript":
      return "通话转写文本";
    case "analysis":
      return "AI 分析结果";
    case "evidence_bundle":
      return "案件存证包";
    default:
      return t;
  }
}

function fmtTime(s: string): string {
  return s.replace("T", " ").slice(0, 19);
}
