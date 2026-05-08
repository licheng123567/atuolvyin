import { ApprovalListPage } from "./ApprovalListPage";
import { ApprovalDetailPage } from "./ApprovalDetailPage";

export function SupervisorDiscountApprovalsPage() {
  return (
    <ApprovalListPage
      approverRole="supervisor"
      approverName="督导小李"
      detailBasePath="/supervisor/discount-approvals"
    />
  );
}

export function SupervisorDiscountApprovalDetailPage() {
  return <ApprovalDetailPage backTo="/supervisor/discount-approvals" approverRole="supervisor" />;
}
