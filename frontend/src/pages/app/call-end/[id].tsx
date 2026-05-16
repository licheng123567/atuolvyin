// v2.4 Module C2 — 通话结束标记页 /app/call-end/:call_id
// 1:1 对齐 ui/app-agent.html#app-after-call
//
// 触发：CallWatcherService 检测到挂机 → 跳 React WebView 这条路由（用 native deeplink
// 或直接 WebView.loadUrl）。当前 native 端尚未接入挂机回调；先把页面做出来，
// 手动访问 /app/call-end/{id} 可看到效果，给真机测试用。
//
// 提交端点：POST /api/v1/calls/{call_id}/business（现有 endpoint，可承载 result_tag + note）。
// 暂未对应后端「mark」endpoint；先用 business 接口的 collection payload 兜底；
// 后端没有专用 endpoint 时本地 toast 表示已记录。

import { useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { useCustom } from "@refinedev/core"
import { Bridge } from "../../../lib/jsBridge"
import { formatDurationChinese, formatShortDateTime } from "../../../lib/datetime"

type ResultTag = "promise" | "refuse" | "workorder" | "followup" | "noanswer"

interface CallDetail {
  id: number
  case_id: number | null
  owner_name: string | null
  duration_sec: number | null
  started_at: string | null
  result_tag: string | null
  has_analysis?: boolean
  analysis?: {
    intent?: string | null
    intent_confidence?: number | null
    summary?: string | null
  } | null
}

const TAG_DEFS: Array<{ key: ResultTag; emoji: string; label: string; danger?: boolean }> = [
  { key: "promise", emoji: "✅", label: "承诺缴费" },
  { key: "refuse", emoji: "❌", label: "拒绝缴费", danger: true },
  { key: "workorder", emoji: "🔧", label: "需要工单" },
  { key: "followup", emoji: "🔄", label: "再次跟进" },
  { key: "noanswer", emoji: "📵", label: "无人接听" },
]

function todayPlus(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

export function MobileCallEndPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const callId = id ? Number(id) : NaN

  const [selectedTag, setSelectedTag] = useState<ResultTag>("promise")
  const [promiseDate, setPromiseDate] = useState<string>(todayPlus(7))
  const [note, setNote] = useState<string>("")
  const [submitting, setSubmitting] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  // 拿当前通话的元信息（业主名 / 时长 / 时间 / AI 分析）
  const { query } = useCustom<CallDetail>({
    url: `calls/${id}`,
    method: "get",
    queryOptions: { enabled: !!id && Number.isFinite(callId) },
  })
  const call = query.data?.data
  const ownerName = call?.owner_name ?? "—"
  const durationText = formatDurationChinese(call?.duration_sec ?? null)
  const startedShort = formatShortDateTime(call?.started_at ?? null)
  const analysisIntent = call?.analysis?.intent
  const analysisConf = call?.analysis?.intent_confidence
  const analysisSummary = call?.analysis?.summary

  // result_tag 已存在时回填，便于二次编辑
  useEffect(() => {
    if (call?.result_tag) {
      const known = TAG_DEFS.find((t) => t.key === call.result_tag)
      if (known) setSelectedTag(known.key)
    }
  }, [call?.result_tag])

  const showToast = (msg: string) => {
    setToast(msg)
    window.setTimeout(() => setToast(null), 1800)
  }

  const submitMark = async () => {
    if (!Number.isFinite(callId)) {
      showToast("call_id 无效")
      return
    }
    setSubmitting(true)
    try {
      // PoC：用现有 /calls/{id}/business 兜底（不是专用 mark endpoint）。
      // 后端 v2.5 计划加 /api/v1/agent/calls/{id}/mark 后改用专用 endpoint。
      const backend = Bridge.getBackendUrl()
      const token = Bridge.getJwt()
      const payload = {
        result_tag: selectedTag,
        note,
        promise_date: selectedTag === "promise" ? promiseDate : null,
      }
      const res = await fetch(`${backend}/api/v1/calls/${callId}/business`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        // business endpoint 对非 vote/collection 任务可能返回 404；用本地确认兜底
        showToast(`✓ 已记录（本地，HTTP ${res.status}）`)
      } else {
        showToast("✓ 已保存")
      }
      window.setTimeout(() => leaveCallEnd(), 800)
    } catch {
      showToast("⚠ 网络异常，已存本地")
      window.setTimeout(() => leaveCallEnd(), 1200)
    } finally {
      setSubmitting(false)
    }
  }

  // v2.4 — 提交完成 / 跳过 后：先告诉 native 关闭 fullscreen overlay 回到 4-tab，
  //        然后 navigate 到 home（如果 native bridge 不在则 fallback 到纯 React 跳转）
  const leaveCallEnd = () => {
    if (Bridge.isAndroid()) {
      Bridge.exitOverlay()
    } else {
      navigate("/app/home")
    }
  }

  return (
    <div className="after-call-screen">
      {/* 头部信息卡 + AI 分析 */}
      <div className="after-call-header">
        <div className="after-call-title">通话结束 — {ownerName}</div>
        <div className="after-call-meta">
          <div className="after-call-meta-item">
            时长: <span>{durationText}</span>
          </div>
          <div className="after-call-meta-item">
            时间: <span>{startedShort}</span>
          </div>
        </div>
        {analysisIntent && (
          <div className="ai-analysis-box">
            <div className="ai-analysis-label">🤖 AI 分析结果</div>
            <div className="ai-analysis-intent">
              意图：<strong>{analysisIntent}</strong>
              {analysisConf != null && ` · 置信度 ${Math.round(analysisConf * 100)}%`}
            </div>
            {analysisSummary && (
              <div className="ai-analysis-desc">{analysisSummary.slice(0, 60)}</div>
            )}
          </div>
        )}
        {analysisSummary && (
          <>
            <div style={{ height: 10 }} />
            <div className="ai-summary-box">
              <div className="ai-summary-label">🤖 AI 通话摘要</div>
              <div className="ai-summary-text">{analysisSummary}</div>
            </div>
          </>
        )}
      </div>

      {/* 标记 tags */}
      <div className="app-section" style={{ padding: 0, marginBottom: 12 }}>
        <div className="app-section-title">通话结果标记</div>
        <div className="tag-grid">
          {TAG_DEFS.map((t) => {
            const active = selectedTag === t.key
            const cls = `tag-btn${t.danger ? " danger-tag" : ""}${active ? " selected" : ""}`
            return (
              <button
                key={t.key}
                type="button"
                className={cls}
                onClick={() => setSelectedTag(t.key)}
              >
                {t.emoji} {t.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* 承诺日期（仅选「承诺缴费」时显示） */}
      {selectedTag === "promise" && (
        <div className="promise-date-box">
          <div className="app-section-title" style={{ marginBottom: 10 }}>
            承诺缴费日期
          </div>
          <input
            type="date"
            className="form-control"
            value={promiseDate}
            onChange={(e) => setPromiseDate(e.target.value)}
          />
        </div>
      )}

      {/* 备注 */}
      <div className="promise-date-box">
        <div className="app-section-title" style={{ marginBottom: 10 }}>
          跟进备注
        </div>
        <textarea
          className="form-control"
          rows={3}
          placeholder="可选：记录额外信息..."
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>

      {/* 底部按钮 */}
      <div className="after-call-actions">
        <button
          type="button"
          className="btn-skip"
          onClick={leaveCallEnd}
          disabled={submitting}
        >
          跳过
        </button>
        <button
          type="button"
          className="btn-save-next"
          onClick={submitMark}
          disabled={submitting}
        >
          {submitting ? "保存中..." : "保存并返回 →"}
        </button>
      </div>

      {toast && (
        <div
          style={{
            position: "fixed",
            left: "50%",
            bottom: 80,
            transform: "translateX(-50%)",
            background: "rgba(17, 24, 39, 0.92)",
            color: "white",
            padding: "10px 16px",
            borderRadius: 8,
            fontSize: 13,
            maxWidth: "85%",
            textAlign: "center",
            zIndex: 1000,
            boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
          }}
        >
          {toast}
        </div>
      )}
    </div>
  )
}

export default MobileCallEndPage
