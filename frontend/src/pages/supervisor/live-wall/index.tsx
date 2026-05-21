// 1:1 还原 ui/supervisor.html#sv-livewall 实时通话墙
import { useCustom, useCustomMutation, useGo } from "@refinedev/core";
import {
  Activity,
  AlertTriangle,
  Headphones,
  PhoneCall,
  PhoneOff,
  RadioTower,
  ShieldQuestion,
  User2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { HelpPanel } from "../../../components/ui/HelpPanel";
import { useLiveCallStore, type LiveCall } from "../../../store/live-calls";

interface LiveCallsResp {
  items: LiveCall[];
}

// v2.1 — 坐席能力 map（前端 join 方案：拉一次全部坐席设备能力，按 caller_user_id 查）
interface AgentDeviceCapItem {
  user_id: number;
  latest_capability: string;
}
interface AgentDevicesCapResp {
  items: AgentDeviceCapItem[];
  total: number;
  page: number;
  page_size: number;
}

const CAP_BADGE_LABEL: Record<string, string> = {
  realtime: "实时",
  post_upload: "事后",
  incompatible: "无录音",
};

export function SupervisorLiveWallPage() {
  const go = useGo();
  const calls = useLiveCallStore((s) => s.calls);
  const setInitial = useLiveCallStore((s) => s.setInitial);
  const [now, setNow] = useState(() => Date.now());

  const { query } = useCustom<LiveCallsResp>({
    url: "supervisor/live-calls",
    method: "get",
  });

  // v2.1 — 拉一次全部坐席的最近能力，本地 cache
  // v0.5.7 fix:page_size=200 超后端 100 上限触发 422;改 100 + 单页内一次拿完(坐席通常 ≤100)
  const { query: capQ } = useCustom<AgentDevicesCapResp>({
    url: "admin/agent-devices",
    method: "get",
    config: { query: { page_size: 100 } },
  });
  const capMap = useMemo(() => {
    const m = new Map<number, string>();
    (capQ.data?.data?.items ?? []).forEach((it) =>
      m.set(it.user_id, it.latest_capability),
    );
    return m;
  }, [capQ.data]);

  useEffect(() => {
    if (query.data?.data?.items) {
      setInitial(query.data.data.items);
    }
  }, [query.data, setInitial]);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const sorted = useMemo(
    () =>
      [...calls].sort((a, b) => {
        if (a.risk_flagged !== b.risk_flagged) return a.risk_flagged ? -1 : 1;
        const at = a.started_at ? Date.parse(a.started_at) : 0;
        const bt = b.started_at ? Date.parse(b.started_at) : 0;
        return bt - at;
      }),
    [calls],
  );

  return (
    <div>
      <div className="page-header">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <RadioTower
            style={{ color: "var(--color-primary)", width: 22, height: 22 }}
          />
          <div>
            <h1 className="page-title">实时通话墙</h1>
            <div className="page-subtitle">
              所有正在通话坐席 · 主管 / 管理员 / 项目经理可直接干预
            </div>
          </div>
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontSize: 12.5,
            color: "var(--color-neutral-500)",
          }}
        >
          <span className="livewall-pulse" />
          实时同步中 · 当前{" "}
          <strong style={{ color: "var(--color-neutral-800)" }}>
            {sorted.length}
          </strong>{" "}
          通
        </div>
      </div>

      <HelpPanel
        tone="info"
        dismissKey="/supervisor/live-wall"
        title="督导 3 种干预手段（对正在通话）"
        bullets={[
          <><strong>点击卡片 = 进入实时跟单</strong>：旁路监听通话音频 + 实时看 ASR 转录文字 + 看 AI 弹的话术建议（不影响通话双方，催收员不知情）</>,
          <><strong>申请接管</strong>（黄按钮）：发送通知到催收员 App，催收员点确认后通话音频路由到督导耳麦，由督导继续与业主对话；适用于 L2 风控时业主情绪激烈、催收员控不住</>,
          <><strong>强制结束</strong>（红按钮）：填写理由后立刻挂断通话，催收员 App 收到强制结束提示；适用于催收员违规话术（语气强硬/威胁）需立即止损</>,
        ]}
        footer="⚠ 接管 / 强制结束都会写入审计日志，案件时间线和员工 KPI 都会记录"
      />

      {sorted.length === 0 && !query.isLoading && (
        <div className="livewall-empty">
          <PhoneCall />
          <p>当前无坐席通话中。坐席在 App 内点「拨打」后，本页会自动显示。</p>
        </div>
      )}

      {sorted.length > 0 && (
        <div className="livewall-grid">
          {sorted.map((c) => (
            <CallCard
              key={c.call_id}
              call={c}
              now={now}
              capability={capMap.get(c.caller_user_id)}
              onClick={() => go({ to: `/admin/workstation/${c.call_id}` })}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function CallCard({
  call,
  now,
  capability,
  onClick,
}: {
  call: LiveCall;
  now: number;
  capability?: string;
  onClick: () => void;
}) {
  const { mutate, mutation } = useCustomMutation();

  const startedMs = call.started_at ? Date.parse(call.started_at) : now;
  const elapsed = Math.max(0, Math.floor((now - startedMs) / 1000));
  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");

  const onForceHangup = (e: React.MouseEvent) => {
    e.stopPropagation();
    const reason = window.prompt(
      `确认强制结束 ${call.caller_name} 与 ${call.owner_name ?? "业主"} 的通话？\n请填写原因（将记入审计）：`,
    );
    if (!reason || !reason.trim()) return;
    mutate(
      {
        url: `supervisor/calls/${call.call_id}/force-hangup`,
        method: "post",
        values: { reason: reason.trim() },
      },
      {
        onSuccess: () => alert("已发起强制结束指令"),
        onError: (err) =>
          alert(`失败：${(err as { message?: string }).message ?? "未知"}`),
      },
    );
  };

  const onTakeover = (e: React.MouseEvent) => {
    e.stopPropagation();
    const reason = window.prompt(
      `向坐席 ${call.caller_name} 发起接管请求？请填写原因：`,
    );
    if (!reason || !reason.trim()) return;
    mutate(
      {
        url: `supervisor/calls/${call.call_id}/takeover`,
        method: "post",
        values: { reason: reason.trim() },
      },
      {
        onSuccess: () => alert("接管请求已发出，等待坐席响应"),
        onError: (err) =>
          alert(`失败：${(err as { message?: string }).message ?? "未知"}`),
      },
    );
  };

  const isLive = call.status === "live";

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onClick();
      }}
      className={`livewall-card${call.risk_flagged ? " livewall-card--risk" : ""}`}
    >
      <div className="livewall-card-head">
        <div className="livewall-caller">
          <User2 />
          <span>{call.caller_name}</span>
        </div>
        <div className="livewall-tags">
          {call.risk_flagged && (
            <AlertTriangle
              style={{ color: "var(--color-danger)" }}
              aria-label="风控告警"
            />
          )}
          {capability && (
            <span
              className={`cap-badge cap-badge--${capability}`}
              title={`坐席手机录音能力: ${CAP_BADGE_LABEL[capability] ?? capability}`}
            >
              {CAP_BADGE_LABEL[capability] ?? capability}
            </span>
          )}
          <span
            className={`livewall-mode livewall-mode--${
              call.recording_mode === "live" ? "live" : "post"
            }`}
          >
            {call.recording_mode === "live" ? "实时" : "事后"}
          </span>
        </div>
      </div>

      <div className="livewall-meta">
        {call.owner_name && (
          <div>
            业主：{call.owner_name}
            {call.owner_phone_masked ? ` · ${call.owner_phone_masked}` : ""}
          </div>
        )}
        {call.case_id && (
          <div className="livewall-sub">案件 #{call.case_id}</div>
        )}
      </div>

      <div className="livewall-status-row">
        <div
          className={`livewall-status livewall-status--${isLive ? "live" : "dialing"}`}
        >
          <Activity />
          {isLive ? "通话中" : "拨号中"}
        </div>
        <div className="livewall-timer">
          {mm}:{ss}
        </div>
      </div>

      <div className="livewall-enter">
        <Headphones />
        点击进入实时跟单
      </div>

      <div className="livewall-actions">
        <button
          type="button"
          onClick={onTakeover}
          disabled={mutation.isPending}
          className="livewall-btn livewall-btn--takeover"
        >
          <ShieldQuestion />
          申请接管
        </button>
        <button
          type="button"
          onClick={onForceHangup}
          disabled={mutation.isPending}
          className="livewall-btn livewall-btn--hangup"
        >
          <PhoneOff />
          强制结束
        </button>
      </div>
    </div>
  );
}
