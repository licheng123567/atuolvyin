// v1.8.0 — 案件列表「记录跟进」快捷入口的 Modal 包装。
// 复用 FollowUpNoteCard 共享组件 + design-system.css 的 modal-overlay / ds-modal。
import { FollowUpNoteCard } from "./FollowUpNoteCard";

interface Props {
  caseId: number;
  ownerName: string;
  /** PATCH endpoint，例如 "agent/cases/123/stage" */
  endpoint: string;
  /** 成功后用于 invalidate 列表的 resource 名 */
  invalidateResource?: string;
  onClose: () => void;
}

export function FollowUpNoteModal({
  caseId,
  ownerName,
  endpoint,
  invalidateResource,
  onClose,
}: Props) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="ds-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480 }}>
        <div className="modal-header">
          <span className="modal-title">记录跟进 · {ownerName}</span>
          <button type="button" className="modal-close" onClick={onClose}>×</button>
        </div>
        <div style={{ padding: "8px 16px 16px" }}>
          <FollowUpNoteCard
            caseId={caseId}
            endpoint={endpoint}
            invalidateResource={invalidateResource}
            onSaved={onClose}
          />
        </div>
      </div>
    </div>
  );
}
