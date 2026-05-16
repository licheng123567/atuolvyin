// v2.4 Module D — In-call WebView 屏幕 /app/in-call/:call_id
// 1:1 对齐 ui/app-agent.html#app-in-call
//
// 设计约束（用户已确认）：
//   - **音频采集仍由 native 做**（Compose AudioStreamClient.kt 上传 binary frame）
//   - React 端只观察：连同一个 /ws/calls/{call_id} 接收 JSON 事件渲染 UI
//   - 控制按钮（挂断/静音/备注/发码）在 v2.4 不接 native bridge（避免 APK 升级）；
//     按下只做本地 UI 状态变化 + 跳到 /app/call-end 兜底（挂断按钮）。
//   - 实际「挂断」需要由系统拨号 UI 或 native CallWatcher 触发。
//
// demo 模式：URL ?demo=1 时跳过 WS 连接，注入 mock 转写 + AI 建议。
//   开发/无后端联调用：/app/in-call/123?demo=1

import { useEffect, useState } from "react"
import { useNavigate, useParams, useSearchParams } from "react-router-dom"
import {
  AlertTriangle,
  FileText,
  Link2,
  MicOff,
  PhoneOff,
} from "lucide-react"
import { useCallSocket } from "../_useCallSocket"
import { Bridge } from "../../../../lib/jsBridge"

function pad2(n: number): string {
  return n < 10 ? `0${n}` : `${n}`
}
function formatHMS(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${pad2(m)}:${pad2(s)}`
}

export function MobileInCallPage() {
  const { id } = useParams<{ id: string }>()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const callId = id ? Number(id) : NaN
  const isDemo = params.get("demo") === "1"
  const ownerName = params.get("owner") ?? "通话中"

  const [elapsed, setElapsed] = useState(0)
  const [muted, setMuted] = useState(false)
  const sock = useCallSocket(callId, { demo: isDemo })

  // 通话计时（前端简易版；真实计时建议用 native 起始时间戳）
  useEffect(() => {
    const t = window.setInterval(() => setElapsed((e) => e + 1), 1000)
    return () => window.clearInterval(t)
  }, [])

  const callTime = formatHMS(elapsed)

  // v2.4 — 挂断：调 native Bridge.endCall 尝试结束系统通话；
  //        Android 6/MIUI 10 上 native 是 no-op（API < 28），但 native 会通过
  //        WebNavigationBus.navigateTo("/app/call-end/{id}") 让 overlay 切到标记页。
  //        浏览器/无 bridge fallback：自行 navigate 到 call-end。
  const handleHangup = () => {
    if (Number.isFinite(callId) && callId > 0) {
      if (Bridge.isAndroid()) {
        Bridge.endCall(callId)
      } else {
        navigate(`/app/call-end/${callId}`, { replace: true })
      }
    } else {
      navigate("/app/home", { replace: true })
    }
  }

  return (
    <div className="incall-screen">
      {/* 顶部状态条 */}
      <div className="incall-status-bar">
        <span>{new Date().toLocaleTimeString("zh-CN", { hour12: false }).slice(0, 5)}</span>
        <span className="incall-call-badge">通话中 {callTime}</span>
        <span style={{ opacity: 0.85 }}>{sock.connected ? "●" : "○"}</span>
      </div>

      {/* 风控 L1 橙色提示条（仅有 active risk 时） */}
      {sock.activeRisk && (
        <div className="risk-strip">
          <AlertTriangle size={14} strokeWidth={2} />
          <span>{sock.activeRisk.message}</span>
          <button
            type="button"
            className="risk-strip-btn"
            onClick={() => sock.dismissRisk()}
          >
            知道了
          </button>
        </div>
      )}

      {/* 中部业主名 + 时长 + 网络 */}
      <div className="incall-header">
        <div className="incall-owner">{ownerName}</div>
        <div className="incall-duration">{callTime}</div>
        <div className="incall-network">
          ● {sock.connected ? "实时分析已就绪" : isDemo ? "演示模式" : "连接中…"}
        </div>
      </div>

      {/* 实时转写卡 */}
      {sock.transcript.length > 0 && (
        <div className="realtime-transcript">
          <div className="realtime-transcript-label">实时转写</div>
          {sock.transcript.map((line) => (
            <div
              key={line.id}
              className={`realtime-line realtime-line-${line.speaker}`}
            >
              [{line.speaker === "agent" ? "催收员" : "业主"}] {line.text}
            </div>
          ))}
        </div>
      )}

      {/* 波形动画占位 */}
      <div className="waveform-wrap">
        <div className="waveform" aria-hidden>
          <div className="waveform-bar" />
          <div className="waveform-bar" />
          <div className="waveform-bar" />
          <div className="waveform-bar" />
          <div className="waveform-bar" />
          <div className="waveform-bar" />
          <div className="waveform-bar" />
        </div>
        {muted && (
          <div
            style={{
              marginTop: 16,
              fontSize: 12,
              color: "#fbbf24",
              letterSpacing: 1,
            }}
          >
            🔇 已静音
          </div>
        )}
      </div>

      {/* AI 建议浮卡（slide-up） */}
      <div className={`ai-card-popup${sock.latestSuggestion ? " show" : ""}`}>
        <div className="ai-card-popup-title">💡 AI 建议</div>
        <div className="ai-card-popup-text">
          {sock.latestSuggestion?.text ?? ""}
        </div>
        <div className="ai-card-popup-actions">
          <button
            type="button"
            className="ai-card-adopt"
            onClick={() => sock.dismissSuggestion()}
          >
            采纳
          </button>
          <button
            type="button"
            className="ai-card-dismiss"
            onClick={() => sock.dismissSuggestion()}
          >
            忽略
          </button>
        </div>
      </div>

      {/* 4 控制按钮 */}
      <div className="incall-controls">
        <button
          type="button"
          className="ctrl-btn"
          onClick={() => setMuted((v) => !v)}
        >
          <div className="ctrl-btn-circle">
            <MicOff size={22} strokeWidth={2} />
          </div>
          <span>{muted ? "取消静音" : "静音"}</span>
        </button>
        <button type="button" className="ctrl-btn" onClick={handleHangup}>
          <div className="ctrl-btn-circle hangup">
            <PhoneOff size={22} strokeWidth={2} />
          </div>
          <span className="ctrl-btn-label-hangup">挂断</span>
        </button>
        <button
          type="button"
          className="ctrl-btn"
          onClick={() => navigate(`/app/call-end/${id ?? "0"}`)}
        >
          <div className="ctrl-btn-circle">
            <FileText size={22} strokeWidth={2} />
          </div>
          <span>备注</span>
        </button>
        <button
          type="button"
          className="ctrl-btn"
          onClick={() => window.alert("发码：v2.5 待接入")}
        >
          <div className="ctrl-btn-circle">
            <Link2 size={22} strokeWidth={2} />
          </div>
          <span>发码</span>
        </button>
      </div>
    </div>
  )
}

export default MobileInCallPage
