// v2.0 Task 4 — Mobile-friendly Chinese datetime helpers.
// 用于 Screen 5 案件列表「联系于X前」/ Screen 6 详情「最近联系」/ Screen 6 时间线日期。

const ONE_DAY_MS = 24 * 60 * 60 * 1000;

function toDate(value: string | Date | null | undefined): Date | null {
  if (!value) return null;
  if (value instanceof Date) return Number.isFinite(value.getTime()) ? value : null;
  const d = new Date(value);
  return Number.isFinite(d.getTime()) ? d : null;
}

/**
 * 中文相对时间：
 * - 60 min 内 → "刚刚"
 * - 同日       → "今天"
 * - 昨日       → "昨天"
 * - ≤ 30 天    → "N 天前"
 * - 同年       → "M月D日"
 * - 跨年       → "YYYY-MM-DD"
 */
export function relativeTimeChinese(value: string | Date | null | undefined): string {
  const d = toDate(value);
  if (!d) return "—";
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();

  if (diffMs >= 0 && diffMs < 60 * 60 * 1000) return "刚刚";

  const startOfDay = (x: Date) =>
    new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const dayDiff = Math.round((startOfDay(now) - startOfDay(d)) / ONE_DAY_MS);

  if (dayDiff === 0) return "今天";
  if (dayDiff === 1) return "昨天";
  if (dayDiff > 0 && dayDiff <= 30) return `${dayDiff}天前`;
  if (now.getFullYear() === d.getFullYear()) {
    return `${d.getMonth() + 1}月${d.getDate()}日`;
  }
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** "MM-DD HH:mm" 用于时间线/通话记录卡片. */
export function formatShortDateTime(value: string | Date | null | undefined): string {
  const d = toDate(value);
  if (!d) return "—";
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${mm}-${dd} ${hh}:${mi}`;
}

/** "MM-DD" only — 列表型。 */
export function formatMonthDay(value: string | Date | null | undefined): string {
  const d = toDate(value);
  if (!d) return "—";
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${mm}-${dd}`;
}

/** 秒数 → "X分Y秒" / "Y秒"（< 60s 时不显示分）。 */
export function formatDurationChinese(sec: number | null | undefined): string {
  if (sec == null || sec < 0 || !Number.isFinite(sec)) return "—";
  const total = Math.floor(sec);
  if (total < 60) return `${total}秒`;
  const m = Math.floor(total / 60);
  const s = total % 60;
  if (s === 0) return `${m}分`;
  return `${m}分${s}秒`;
}

/** 总分钟数 → "X小时Y分" / "Y分"。 */
export function formatTotalMinutes(min: number | null | undefined): string {
  if (min == null || min < 0 || !Number.isFinite(min)) return "—";
  const total = Math.floor(min);
  if (total < 60) return `${total}分`;
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (m === 0) return `${h}小时`;
  return `${h}小时${m}分`;
}

/** 返回当前月份字符串 "YYYY-MM"，用于月选择器默认值。 */
export function currentYM(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
