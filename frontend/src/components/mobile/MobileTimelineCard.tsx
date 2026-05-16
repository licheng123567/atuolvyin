// v2.0 Task 4 — Mobile-only timeline card.
// 用于 Screen 6 案件详情通话时间线（每条通话一卡）。
// 与 PC 版 ActivityTimeline 不共享：移动版需要更紧凑的 12px 字号 + 圆角 10。
import type { ResultBadge } from "../../lib/caseStage";

export interface MobileTimelineCardProps {
  /** "MM-DD HH:mm" — formatShortDateTime 的输出。 */
  date: string;
  /** 通话时长秒，已经在调用方格式化为「X分Y秒」字符串。 */
  durationText: string;
  /** result_tag 转换后的 badge。 */
  resultBadge: ResultBadge;
  /** AI 分析摘要文本；为空时回退提示。 */
  aiSummary: string | null;
}

export function MobileTimelineCard(props: MobileTimelineCardProps) {
  const { date, durationText, resultBadge, aiSummary } = props;
  return (
    <div className="timeline-card">
      <div className="timeline-card-header">
        <span className="timeline-card-date">{date}</span>
        <span className="timeline-card-duration">{durationText}</span>
        <span className={resultBadge.cls} style={{ fontSize: 11 }}>
          {resultBadge.label}
        </span>
      </div>
      <div className="timeline-card-ai">
        {aiSummary && aiSummary.trim().length > 0 ? aiSummary : "—"}
      </div>
    </div>
  );
}

export default MobileTimelineCard;
