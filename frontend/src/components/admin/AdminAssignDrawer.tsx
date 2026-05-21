// v0.6.0 — 物业管理员分配 / 重新分配案件给本租户内部催收员
//
// 设计:参考 frontend/src/pages/provider/cases/ProviderAssignDrawer.tsx 风格,
// 采用 RightDrawer(用户反馈中间居中弹窗下拉只能看 2-3 个名字,体验差)。
//
// 后端:POST /api/v1/admin/cases/assign { case_ids: [int], assign_to: int }
// 目标员工:admin/users 中 role=agent 的成员(物业侧)。
// 兼容批量分配 — caseIds 数组,既支持单条又支持公海批量。
import { useCustomMutation, useList } from "@refinedev/core";
import { Loader2, Users } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse, UserRole } from "../../types";
import { RightDrawer } from "../ui/RightDrawer";

interface AdminUserItem {
  id: number;
  name: string;
  role: UserRole;
  is_active?: boolean;
}

interface Props {
  caseIds: number[];                  // 支持单条/批量
  ownerName?: string;                 // 单条时显示业主名,批量时可不传
  currentAssignedTo?: number | null;  // 已分配的 user_id,用于「重新分配」语义
  onClose: () => void;
  onAssigned: () => void;             // 调用方负责 invalidate / refetch
}

export function AdminAssignDrawer({
  caseIds, ownerName, currentAssignedTo, onClose, onAssigned,
}: Props) {
  const [targetId, setTargetId] = useState<number | null>(null);
  const { mutate, mutation } = useCustomMutation();

  // 拉物业侧用户 — 用现有 admin/users 端点,前端 filter role=agent
  const { query: usersQuery } = useList<AdminUserItem>({
    resource: "admin/users",
    pagination: { currentPage: 1, pageSize: 100 },
  });
  const rawUsers = usersQuery.data?.data;
  const allUsers: AdminUserItem[] = Array.isArray(rawUsers)
    ? (rawUsers as AdminUserItem[])
    : ((rawUsers as unknown as PaginatedResponse<AdminUserItem>)?.items ?? []);
  const agents = allUsers.filter(
    (u) => u.role === "agent" && (u.is_active === undefined || u.is_active),
  );

  const isBatch = caseIds.length > 1;
  const validTarget = targetId !== null && targetId !== currentAssignedTo;

  const handleSubmit = () => {
    if (!validTarget || caseIds.length === 0) return;
    mutate(
      {
        url: "admin/cases/assign",
        method: "post",
        values: { case_ids: caseIds, assign_to: targetId },
      },
      {
        onSuccess: () => onAssigned(),
        onError: (err) => {
          alert(`分配失败:${(err as { message?: string }).message ?? "请重试"}`);
        },
      },
    );
  };

  const titleText = isBatch
    ? `批量分配 — ${caseIds.length} 个案件`
    : currentAssignedTo
      ? `重新分配${ownerName ? ` — ${ownerName}` : ""}`
      : `分配案件${ownerName ? ` — ${ownerName}` : ""}`;

  return (
    <RightDrawer
      open
      onClose={onClose}
      drawerKey="admin-cases-assign"
      defaultWidth={520}
      title={
        <span className="flex items-center gap-2">
          <Users className="w-5 h-5 text-[var(--color-primary)]" />
          {titleText}
        </span>
      }
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-sm rounded border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-50)]"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!validTarget || mutation.isPending}
            className="px-4 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-1.5"
          >
            {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            {currentAssignedTo ? "确认重新分配" : "确认分配"}
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="text-xs text-[var(--color-neutral-600)] bg-[var(--color-neutral-50)] rounded p-2">
          只能分配给<strong>本租户内部催收员</strong>(role=agent)。分配后案件 assigned_to
          切换 + pool_type 变 private,原催收员/督导可在自己的工作台看到变化。
        </div>

        {currentAssignedTo && (
          <div className="text-xs text-[var(--color-neutral-500)]">
            当前已分配给: user #{currentAssignedTo}
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1.5">
            目标催收员 <span className="text-red-500">*</span>
          </label>
          {usersQuery.isLoading ? (
            <div className="text-sm text-[var(--color-neutral-500)]">加载中…</div>
          ) : agents.length === 0 ? (
            <div className="text-sm text-red-600">
              本租户暂无有效催收员 — 请先到「用户管理」激活成员
            </div>
          ) : (
            <div className="space-y-1.5 max-h-[60vh] overflow-y-auto border border-[var(--color-neutral-200)] rounded">
              {agents.map((a) => (
                <label
                  key={a.id}
                  className={`flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-[var(--color-neutral-50)] ${
                    targetId === a.id ? "bg-blue-50" : ""
                  }`}
                >
                  <input
                    type="radio"
                    name="admin-assign-target"
                    value={a.id}
                    checked={targetId === a.id}
                    onChange={() => setTargetId(a.id)}
                  />
                  <span className="font-medium">{a.name}</span>
                  <span className="text-xs text-[var(--color-neutral-500)]">
                    · #{a.id} · 催收员
                  </span>
                  {a.id === currentAssignedTo && (
                    <span className="ml-auto text-xs text-[var(--color-neutral-400)]">
                      (当前)
                    </span>
                  )}
                </label>
              ))}
            </div>
          )}
          {targetId !== null && targetId === currentAssignedTo && (
            <div className="mt-1 text-xs text-red-600">
              目标不能与当前催收员相同
            </div>
          )}
        </div>
      </div>
    </RightDrawer>
  );
}
