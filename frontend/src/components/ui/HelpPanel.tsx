// v1.5.7 — 全站统一的「功能说明面板」
// 用途：每个页面顶部加一个色调统一的简短说明，让用户秒懂这页是干什么的
// 4 种 tone 对应不同场景：
//   - info  (蓝)：常规功能说明 / 入门提示
//   - tip   (绿)：操作技巧 / 推荐策略
//   - warn  (黄)：注意事项 / 副作用提醒
//   - danger(红)：合规 / 不可逆操作 / 风险警示
import { AlertTriangle, BookOpen, Info, Lightbulb, X } from "lucide-react";
import { useEffect, useState } from "react";

export type HelpTone = "info" | "tip" | "warn" | "danger";

interface Props {
  /** 标题（如「话术库的作用」） */
  title: string;
  /** 段落或要点列表（数组里每个元素是一个 <li>，支持 ReactNode） */
  bullets?: React.ReactNode[];
  /** 段落正文（替代 bullets，纯文本说明） */
  body?: React.ReactNode;
  /** 配色基调，默认 info */
  tone?: HelpTone;
  /** 用于 localStorage 记忆「不再提示」的唯一 key（建议：页面路径） */
  dismissKey?: string;
  /** 可选的小贴士（底部分隔线下，斜体灰字） */
  footer?: React.ReactNode;
}

const TONE_STYLE: Record<HelpTone, { bg: string; border: string; color: string; icon: React.ReactNode }> = {
  info:   { bg: "#eff6ff", border: "#bfdbfe", color: "#1e3a8a", icon: <BookOpen className="w-4 h-4" /> },
  tip:    { bg: "#f0fdf4", border: "#bbf7d0", color: "#14532d", icon: <Lightbulb className="w-4 h-4" /> },
  warn:   { bg: "#fffbeb", border: "#fde68a", color: "#78350f", icon: <Info className="w-4 h-4" /> },
  danger: { bg: "#fef2f2", border: "#fecaca", color: "#7f1d1d", icon: <AlertTriangle className="w-4 h-4" /> },
};

const STORAGE_PREFIX = "help_panel_dismissed:";

export function HelpPanel({ title, bullets, body, tone = "info", dismissKey, footer }: Props) {
  const [dismissed, setDismissed] = useState(false);
  useEffect(() => {
    if (dismissKey && localStorage.getItem(STORAGE_PREFIX + dismissKey) === "1") {
      setDismissed(true);
    }
  }, [dismissKey]);

  if (dismissed) return null;
  const style = TONE_STYLE[tone];

  function handleDismiss() {
    if (dismissKey) localStorage.setItem(STORAGE_PREFIX + dismissKey, "1");
    setDismissed(true);
  }

  return (
    <div
      style={{
        background: style.bg,
        border: `1px solid ${style.border}`,
        borderRadius: 8,
        padding: "12px 16px",
        marginBottom: 16,
        fontSize: 13,
        color: style.color,
        lineHeight: 1.7,
        position: "relative",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 600, marginBottom: 6, paddingRight: 24 }}>
        <span style={{ display: "inline-flex", alignItems: "center" }}>{style.icon}</span>
        {title}
      </div>
      {body && <div>{body}</div>}
      {bullets && bullets.length > 0 && (
        <ul style={{ margin: 0, paddingLeft: 20 }}>
          {bullets.map((b, i) => <li key={i}>{b}</li>)}
        </ul>
      )}
      {footer && (
        <div style={{ marginTop: 8, paddingTop: 8, borderTop: `1px dashed ${style.border}`, fontSize: 12, fontStyle: "italic", opacity: 0.85 }}>
          {footer}
        </div>
      )}
      {dismissKey && (
        <button
          type="button"
          onClick={handleDismiss}
          aria-label="不再提示"
          title="不再提示（关闭后下次访问该页将不再显示此说明）"
          style={{
            position: "absolute",
            top: 10,
            right: 10,
            background: "transparent",
            border: "none",
            color: style.color,
            opacity: 0.6,
            cursor: "pointer",
            padding: 2,
          }}
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
