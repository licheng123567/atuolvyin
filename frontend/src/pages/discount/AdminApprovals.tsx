import { ApprovalListPage } from "./ApprovalListPage";
import { ApprovalDetailPage } from "./ApprovalDetailPage";

export function AdminDiscountApprovalsPage() {
  return (
    <ApprovalListPage
      approverRole="admin"
      approverName="物业 admin"
      detailBasePath="/admin/discount-approvals"
    />
  );
}

export function AdminDiscountApprovalDetailPage() {
  return <ApprovalDetailPage backTo="/admin/discount-approvals" approverRole="admin" />;
}
