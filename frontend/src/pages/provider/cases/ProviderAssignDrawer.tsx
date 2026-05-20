// v0.5.6 — 服务商管理员分配 / 重新分配案件给本服务商员工
//
// 后端:POST /api/v1/provider/cases/assign { case_ids: [int], assign_to: int }
// 目标员工:UserTenantMembership.provider_id == 本服务商 的任何 active 成员
// 用 RightDrawer(分级策略:分配是「需边看列表的多字段操作」)
import { useCustom, useCustomMutation } from "@refinedev/core";
import { Loader2, Users } from "lucide-react";
import { useState } from "react";
import { RightDrawer } from "../../../components/ui/RightDrawer";

interface TeamMember {
  user_id: number;
  name: string;
  role: string;
  is_active: boolean;
}

interface TeamListResp {
  items?: TeamMember[];
}

interface Props {
  caseId: number;
  ownerName: string;
  currentAssignedTo?: number | null;
  onClose: () => void;
  onDone: () => void;
}

export function ProviderAssignDrawer({
  caseId, ownerName, currentAssignedTo, onClose, onDone,
}: Props) {
  const [targetId, setTargetId] = useState<number | null>(null);
  const { mutate, mutation } = useCustomMutation();

  // 拉本服务商团队成员列表 — 复用现有 provider_admin GET /provider/team
  const { query: teamQuery } = useCustom<TeamListResp | TeamMember[]>({
    url: "provider/team",
    method: "get",
  });
  const teamRaw = teamQuery.data?.data;
  const team: TeamMember[] = Array.isArray(teamRaw) ? teamRaw : (teamRaw?.items ?? []);
  const activeMembers = team.filter((m) => m.is_active);

  const validTarget = targetId !== null && targetId !== currentAssignedTo;

  const handleSubmit = () => {
    if (!validTarget) return;
    mutate(
      {
        url: "provider/cases/assign",
        method: "post",
        values: { case_ids: [caseId], assign_to: targetId },
      },
      {
        onSuccess: () => onDone(),
        onError: (err) => {
          alert(`分配失败:${(err as { message?: string }).message ?? "请重试"}`);
        },
      },
    );
  };

  return (
    <RightDrawer
      open
      onClose={onClose}
      drawerKey="provider-cases-assign"
      defaultWidth={520}
      title={
        <span className="flex items-center gap-2">
          <Users className="w-5 h-5 text-[var(--color-primary)]" />
          {currentAssignedTo ? "重新分配" : "分配案件"} — {ownerName}
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
          只能分配给**本服务商**有效成员(任意 role:agent / supervisor / admin)。分配后
          案件 assigned_to 切换到目标员工 + pool_type='private',原催收员/督导可在自己的工作台看到变化。
        </div>

        {currentAssignedTo && (
          <div className="text-xs text-[var(--color-neutral-500)]">
            当前已分配给: user #{currentAssignedTo}
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1.5">
            目标员工 <span className="text-red-500">*</span>
          </label>
          {teamQuery.isLoading ? (
            <div className="text-sm text-[var(--color-neutral-500)]">加载中…</div>
          ) : activeMembers.length === 0 ? (
            <div className="text-sm text-red-600">
              本服务商暂无有效员工 — 请先到「团队管理」激活成员
            </div>
          ) : (
            <div className="space-y-1.5 max-h-96 overflow-y-auto border border-[var(--color-neutral-200)] rounded">
              {activeMembers.map((m) => (
                <label
                  key={m.user_id}
                  className={`flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-[var(--color-neutral-50)] ${
                    targetId === m.user_id ? "bg-blue-50" : ""
                  }`}
                >
                  <input
                    type="radio"
                    name="provider-assign-target"
                    value={m.user_id}
                    checked={targetId === m.user_id}
                    onChange={() => setTargetId(m.user_id)}
                  />
                  <span className="font-medium">{m.name}</span>
                  <span className="text-xs text-[var(--color-neutral-500)]">
                    · #{m.user_id} · {m.role}
                  </span>
                  {m.user_id === currentAssignedTo && (
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
