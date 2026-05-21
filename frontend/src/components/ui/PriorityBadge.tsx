// v0.7.0 — 案件优先级 badge 共享组件
//
// 算法(后端 admin_cases.py:_calc_priority):
//   priority_score = amount_owed × 0.4 + months_overdue × 0.3
// 实际数据范围:0 ~ 数千(欠款 ¥4500 + 60 月 = 1818 分这种很常见)
// 分级阈值(原物业 admin/pool/index.tsx:54-60 已有,本组件抽离):
//   ≥80    红色 高优先级
//   60-80  橙色 中优先级
//   40-60  蓝色 低-中优先级
//   <40    灰色 低优先级
//
// 跨用法:物业 admin 案件列表 + 公海;服务商 admin 案件列表 + 看板
import type { CSSProperties, JSX } from "react";

export interface PriorityBadgeProps {
  score: number | null | undefined;
  /** 可选:显示得分数字(默认 true)。看板等紧凑场景可传 false 只显颜色块 */
  showScore?: boolean;
  style?: CSSProperties;
  className?: string;
}

export function PriorityBadge({
  score, showScore = true, style, className,
}: PriorityBadgeProps): JSX.Element {
  if (score == null) {
    return (
      <span
        className={`ds-badge ds-badge-gray ${className ?? ""}`}
        style={style}
        title="未计算优先级"
      >
        —
      </span>
    );
  }

  const meta = pickMeta(score);
  return (
    <span
      className={`${meta.cls} ${className ?? ""}`}
      style={style}
      title={`优先级 ${meta.label}(${score} 分)= 欠款 × 0.4 + 逾期月数 × 0.3;≥80 高 / 60-80 中 / 40-60 低-中 / <40 低`}
    >
      {showScore ? `${meta.label} · ${score}` : meta.label}
    </span>
  );
}

function pickMeta(score: number): { cls: string; label: string } {
  if (score >= 80) return { cls: "ds-badge ds-badge-red", label: "高" };
  if (score >= 60) return { cls: "ds-badge ds-badge-orange", label: "中" };
  if (score >= 40) return { cls: "ds-badge ds-badge-blue", label: "低-中" };
  return { cls: "ds-badge ds-badge-gray", label: "低" };
}

// 注:若需 className 字符串复用,直接读 PriorityBadge JSX 的 className,
// 或在 PriorityBadge 之外单独建一个 helper 文件;不在本文件再额外导出 hook/util
// (react-refresh 规则要求组件文件只导出组件)。
