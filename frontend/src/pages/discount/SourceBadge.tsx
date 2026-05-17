export function SourceBadge({ providerId, providerName }: { providerId: number | null; providerName: string | null }) {
  return providerId == null
    ? <span className="ds-badge ds-badge-gray">物业内勤</span>
    : <span className="ds-badge ds-badge-blue">服务商 · {providerName ?? `#${providerId}`}</span>;
}
