// v0.5.4 — 督导重新分配案件给另一催收员弹窗
// 后端:POST /api/v1/supervisor/cases/{case_id}/reassign
//       body: { target_user_id: int, note?: str }
//
// v0.5.6 — 从中间 Modal 迁移到 RightDrawer(用户反馈:分配时需要持续看到左侧案件列表,
// 中间弹窗挡住了上下文)。
//
// v0.9.0 — 用户反馈手填 user_id 不友好:
//   - 改用 SearchableSelect(姓名 + 手机号 / id),可搜索
//   - defaultValue 设为 currentAssignedTo(默认指向当前催收员,用户可清空再选)
//   - 数据源:复用 /admin/users(v0.9.0 已放宽给督导读)
import { useCustomMutation, useList } from "@refinedev/core";
import { Loader2, Users } from "lucide-react";
import { useEffect, useState } from "react";
import type { PaginatedResponse, UserRole } from "../../types";
import { SearchableSelect } from "../ui/SearchableSelect";
import { RightDrawer } from "../ui/RightDrawer";

interface UserListItem {
  id: number;
  name: string;
  role: UserRole;
  is_active?: boolean;
  phone_masked?: string;
}

export function SupervisorReassignModal({
  caseId,
  currentAssignedTo,
  onClose,
  onDone,
}: {
  caseId: number;
  currentAssignedTo?: number | null;
  onClose: () => void;
  onDone: () => void;
}) {
  // v0.9.0 — 默认指向当前催收员(用户可清空再选别人;空字符串=未选)
  const [targetId, setTargetId] = useState<number | "">(currentAssignedTo ?? "");
  const [note, setNote] = useState("");
  const { mutate, mutation } = useCustomMutation();

  // 拉用户列表(/admin/users 已 v0.9.0 允许督导读)
  const { query: usersQuery } = useList<UserListItem>({
    resource: "admin/users",
    pagination: { currentPage: 1, pageSize: 200 },
  });
  const rawUsers = usersQuery.data?.data;
  const allUsers: UserListItem[] = Array.isArray(rawUsers)
    ? (rawUsers as UserListItem[])
    : ((rawUsers as unknown as PaginatedResponse<UserListItem>)?.items ?? []);
  // 仅展示有效的催收员(role=agent)
  const agents = allUsers.filter(
    (u) => u.role === "agent" && (u.is_active === undefined || u.is_active),
  );

  // 当 agents 加载完成后,确保默认值仍在选项内;若 currentAssignedTo 不是有效 agent 则清空
  useEffect(() => {
    if (
      targetId !== "" &&
      agents.length > 0 &&
      !agents.some((a) => a.id === targetId)
    ) {
      setTargetId("");
    }
  }, [agents, targetId]);

  const validTarget =
    typeof targetId === "number" &&
    targetId > 0 &&
    targetId !== currentAssignedTo;

  const handleSubmit = () => {
    if (!validTarget) return;
    mutate(
      {
        url: `supervisor/cases/${caseId}/reassign`,
        method: "post",
        values: {
          target_user_id: targetId,
          note: note.trim() || undefined,
        },
      },
      {
        onSuccess: () => onDone(),
        onError: (err) =>
          alert(
            `重新分配失败:${(err as { message?: string }).message ?? "请重试"}`,
          ),
      },
    );
  };

  const options = agents.map((a) => ({
    value: a.id,
    label: a.name + (a.id === currentAssignedTo ? "(当前)" : ""),
    subtitle: a.phone_masked
      ? `${a.phone_masked} · #${a.id}`
      : `#${a.id}`,
  }));

  return (
    <RightDrawer
      open
      onClose={onClose}
      drawerKey="supervisor-reassign"
      defaultWidth={520}
      title={
        <span className="flex items-center gap-2">
          <Users className="w-5 h-5 text-[var(--color-primary)]" />
          重新分配案件 #{caseId}
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
            确认重新分配
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="text-xs text-[var(--color-neutral-600)] bg-[var(--color-neutral-50)] rounded p-2">
          提交后:案件 assigned_to 切换到目标催收员 + 推送通知给新/原催收员 + 时间线写入「重新分配」事件。
        </div>

        {currentAssignedTo && (
          <div className="text-xs text-[var(--color-neutral-500)]">
            当前催收员: 默认指向其姓名(可清空再选别人)— user #{currentAssignedTo}
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
            <SearchableSelect
              value={targetId}
              onChange={(v) => setTargetId(v === "" ? "" : Number(v))}
              options={options}
              placeholder="搜索姓名 / 手机号 / ID 选择催收员"
              emptyText="无匹配的催收员"
            />
          )}
          {typeof targetId === "number" && targetId === currentAssignedTo && (
            <div className="mt-1 text-xs text-red-600">
              目标不能与当前催收员相同(请清空后选择别的)
            </div>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1.5">
            备注(选填)
          </label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            placeholder="如「原催收员请假 / 业主投诉换人」"
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded resize-none"
          />
        </div>
      </div>
    </RightDrawer>
  );
}
