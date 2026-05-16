// v2.4 Module D — In-call WebSocket observer hook
// 订阅 /ws/calls/{call_id}?token=...&role=agent，接收 JSON 事件：
//   - transcript.chunk    { speaker: 'agent'|'owner', text }
//   - suggestion.ready    { suggestion_text, ... }
//   - risk.alert          { level: 'L1'|'L2'|'L3', message, ... }
//   - tag.ready           （忽略，UI 不消费）
//   - supervisor.alert    （忽略，supervisor 端的）
//
// 设计：React 不做音频采集（native AudioStreamClient 已有）；
// React 只观察。WebView WebSocket 在 Chromium 53 是稳的（W3C WebSocket API 51+）。
// 自动重连：每 3s 重试一次，最多 5 次。
//
// 节流：transcript 100+/s 直接渲染会卡 React。这里把短窗口的同 speaker 行
// 合并成一行（用 useState 队列 + setInterval 200ms flush），最多保留 6 行。

import { useEffect, useRef, useState } from "react"
import { Bridge } from "../../../lib/jsBridge"

export type Speaker = "agent" | "owner"

export interface TranscriptLine {
  id: string
  speaker: Speaker
  text: string
}

export interface Suggestion {
  id: string
  text: string
  ts: number
}

export interface RiskAlert {
  level: "L1" | "L2" | "L3"
  message: string
  ts: number
}

export interface CallSocketState {
  connected: boolean
  retries: number
  transcript: TranscriptLine[]
  latestSuggestion: Suggestion | null
  activeRisk: RiskAlert | null
  /** 用户主动忽略某条 risk 后，调这个不会再被同 level 抢屏 */
  dismissRisk: () => void
  /** 隐藏当前 AI 浮卡 */
  dismissSuggestion: () => void
}

interface RawMsg {
  type?: string
  speaker?: Speaker | string
  text?: string
  suggestion_text?: string
  message?: string
  level?: string
  [k: string]: unknown
}

function wsUrlForCall(callId: number, token: string): string {
  const http = Bridge.getBackendUrl().replace(/\/+$/, "")
  // http(s)://host:18000 → ws(s)://host:18000
  const ws = http.replace(/^http/i, "ws")
  return `${ws}/ws/calls/${callId}?role=agent&token=${encodeURIComponent(token)}`
}

const MAX_TRANSCRIPT_LINES = 6
const FLUSH_INTERVAL_MS = 200

export function useCallSocket(callId: number, opts?: { demo?: boolean }): CallSocketState {
  const [connected, setConnected] = useState(false)
  const [retries, setRetries] = useState(0)
  const [transcript, setTranscript] = useState<TranscriptLine[]>([])
  const [latestSuggestion, setLatestSuggestion] = useState<Suggestion | null>(null)
  const [activeRisk, setActiveRisk] = useState<RiskAlert | null>(null)
  const dismissedSeqRef = useRef(0)

  const dismissRisk = () => {
    dismissedSeqRef.current += 1
    setActiveRisk(null)
  }
  const dismissSuggestion = () => setLatestSuggestion(null)

  // 节流缓冲：incoming transcript chunks 攒到本地，每 200ms flush 到 state
  const bufferRef = useRef<TranscriptLine[]>([])

  useEffect(() => {
    // demo 模式：不连 WS，注入 mock 数据，方便浏览器/无后端时看 UI
    if (opts?.demo) {
      setConnected(true)
      const t1 = window.setTimeout(() => {
        setTranscript([
          { id: "d1", speaker: "agent", text: "张先生您好，我是物业的小李，今天打过来主要是想..." },
          { id: "d2", speaker: "owner", text: "哎呀又是催费的，我说了房子有问题先不交。" },
        ])
        setActiveRisk({
          level: "L1",
          message: "AI 检测到异议：房屋质量问题",
          ts: Date.now(),
        })
      }, 600)
      const t2 = window.setTimeout(() => {
        setLatestSuggestion({
          id: "ds1",
          text: "检测到房屋质量异议（渗水问题），建议先安抚业主情绪，承诺提交工单并跟进处理，再引导缴费...",
          ts: Date.now(),
        })
      }, 1500)
      return () => {
        window.clearTimeout(t1)
        window.clearTimeout(t2)
      }
    }

    if (!Number.isFinite(callId) || callId <= 0) return
    const token = Bridge.getJwt()
    if (!token) return

    let cancelled = false
    let retry = 0
    let ws: WebSocket | null = null
    let reconnectTimer: number | null = null
    let flushTimer: number | null = null

    const flush = () => {
      if (bufferRef.current.length === 0) return
      const incoming = bufferRef.current
      bufferRef.current = []
      setTranscript((prev) => {
        // 合并：相同 speaker 紧邻的两行合并成一行（节省渲染）
        const merged = [...prev]
        for (const line of incoming) {
          const last = merged[merged.length - 1]
          if (last && last.speaker === line.speaker) {
            merged[merged.length - 1] = {
              id: last.id,
              speaker: last.speaker,
              text: `${last.text}${line.text}`,
            }
          } else {
            merged.push(line)
          }
        }
        if (merged.length > MAX_TRANSCRIPT_LINES) {
          return merged.slice(merged.length - MAX_TRANSCRIPT_LINES)
        }
        return merged
      })
    }

    const handleMessage = (ev: MessageEvent<unknown>) => {
      let raw: RawMsg | null = null
      try {
        const data = typeof ev.data === "string" ? ev.data : String(ev.data ?? "")
        raw = JSON.parse(data) as RawMsg
      } catch {
        return
      }
      if (!raw || !raw.type) return
      switch (raw.type) {
        case "transcript.chunk": {
          const speaker: Speaker =
            raw.speaker === "owner" ? "owner" : "agent"
          const text = String(raw.text ?? "")
          if (!text) return
          bufferRef.current.push({
            id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            speaker,
            text,
          })
          break
        }
        case "suggestion.ready": {
          const text = String(raw.suggestion_text ?? raw.text ?? "")
          if (!text) return
          setLatestSuggestion({
            id: `${Date.now()}`,
            text,
            ts: Date.now(),
          })
          break
        }
        case "risk.alert": {
          const lvl = String(raw.level ?? "L1")
          const msg = String(raw.message ?? "AI 风控提醒")
          if (lvl === "L1" || lvl === "L2" || lvl === "L3") {
            setActiveRisk({ level: lvl, message: msg, ts: Date.now() })
          }
          break
        }
        default:
          // tag.ready / supervisor.* 忽略
          break
      }
    }

    const connect = () => {
      if (cancelled) return
      try {
        ws = new WebSocket(wsUrlForCall(callId, token))
      } catch {
        scheduleReconnect()
        return
      }
      ws.onopen = () => {
        if (cancelled) return
        setConnected(true)
        retry = 0
        setRetries(0)
      }
      ws.onmessage = handleMessage
      ws.onclose = () => {
        if (cancelled) return
        setConnected(false)
        scheduleReconnect()
      }
      ws.onerror = () => {
        // close 会跟着触发，让那里处理重连
      }
    }

    const scheduleReconnect = () => {
      if (cancelled) return
      if (retry >= 5) return
      retry += 1
      setRetries(retry)
      reconnectTimer = window.setTimeout(connect, 3000)
    }

    connect()
    flushTimer = window.setInterval(flush, FLUSH_INTERVAL_MS)

    return () => {
      cancelled = true
      if (reconnectTimer != null) window.clearTimeout(reconnectTimer)
      if (flushTimer != null) window.clearInterval(flushTimer)
      if (ws) {
        try {
          ws.onmessage = null
          ws.onclose = null
          ws.onerror = null
          ws.close()
        } catch {
          /* ignore */
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [callId, opts?.demo])

  return {
    connected,
    retries,
    transcript,
    latestSuggestion,
    activeRisk,
    dismissRisk,
    dismissSuggestion,
  }
}
