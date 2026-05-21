// v0.9.0 — 督导批量分配 / 重派案件给催收员
//
// 同 AdminAssignDrawer(物业 admin 版本)同构,差异仅:
//   - 端点:POST /supervisor/cases/batch-assign(支持单条 + 批量,统一接口)
//   - SearchableSelect 替代 radio 列表(用户反馈搜得更快)
//   - 返回 BatchAssignResult: 成功数 + 失败明细(分批容错)
//
// 数据源:复用 /admin/users(v0.9.0 已放宽给督导读)
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

interface BatchAssignFailure {
  case_id: number;
  code: string;
  message: string;
}

interface BatchAssignResult {
  success_count: number;
  failed: BatchAssignFailure[];
}

interface Props {
  caseIds: number[];
  /** 单条时显示业主名;批量时通常不传 */
  ownerName?: string;
  /** 当前已分配的 user_id — 用于「重新分配」的默认值 */
  currentAssignedTo?: number | null;
  onClose: () => void;
  onAssigned: () => void;
}

export function SupervisorAssignDrawer({
  caseIds,
  ownerName,
  currentAssignedTo,
  onClose,
  onAssigned,
}: Props) {
  const [targetId, setTargetId] = useState<number | "">(currentAssignedTo ?? "");
  const [note, setNote] = useState("");
  const [lastResult, setLastResult] = useState<BatchAssignResult | null>(null);
  const { mutate, mutation } = useCustomMutation<BatchAssignResult>();

  const { query: usersQuery } = useList<UserListItem>({
    resource: "admin/users",
    pagination: { currentPage: 1, pageSize: 200 },
  });
  const rawUsers = usersQuery.data?.data;
  const allUsers: UserListItem[] = Array.isArray(rawUsers)
    ? (rawUsers as UserListItem[])
    : ((rawUsers as unknown as PaginatedResponse<UserListItem>)?.items ?? []);
  const agents = allUsers.filter(
    (u) => u.role === "agent" && (u.is_active === undefined || u.is_active),
  );

  useEffect(() => {
    if (
      targetId !== "" &&
      agents.length > 0 &&
      !agents.some((a) => a.id === targetId)
    ) {
      setTargetId("");
    }
  }, [agents, targetId]);

  const isBatch = caseIds.length > 1;
  const validTarget =
    typeof targetId === "number" &&
    targetId > 0 &&
    targetId !== currentAssignedTo;

  const handleSubmit = () => {
    if (!validTarget || caseIds.length === 0) return;
    mutate(
      {
        url: "supervisor/cases/batch-assign",
        method: "post",
        values: {
          case_ids: caseIds,
          target_user_id: targetId,
          note: note.trim() || undefined,
        },
      },
      {
        onSuccess: (resp) => {
          const r = resp.data as BatchAssignResult;
          setLastResult(r);
          // 全成功且无失败 → 直接关
          if (r.failed.length === 0) {
            onAssigned();
          }
          // 否则保持 Drawer 开,展示失败明细让用户复盘
        },
        onError: (err) => {
          alert(`分配失败:${(err as { message?: string }).message ?? "请重试"}`);
        },
      },
    );
  };

  const options = agents.map((a) => ({
    value: a.id,
    label: a.name + (a.id === currentAssignedTo ? "(当前)" : ""),
    subtitle: a.phone_masked ? `${a.phone_masked} · #${a.id}` : `#${a.id}`,
  }));

  const titleText = isBatch
    ? `督导批量分配 — ${caseIds.length} 个案件`
    : currentAssignedTo
      ? `督导重新分配${ownerName ? ` — ${ownerName}` : ""}`
      : `督导分配案件${ownerName ? ` — ${ownerName}` : ""}`;

  return (
    <RightDrawer
      open
      onClose={onClose}
      drawerKey="supervisor-cases-assign"
      defaultWidth={560}
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
            {lastResult ? "关闭" : "取消"}
          </button>
          {!lastResult && (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!validTarget || mutation.isPending}
              className="px-4 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-1.5"
            >
              {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              {currentAssignedTo ? "确认重新分配" : `确认分配${isBatch ? ` (${caseIds.length})` : ""}`}
            </button>
          )}
        </>
      }
    >
      <div className="space-y-3">
        <div className="text-xs text-[var(--color-neutral-600)] bg-[var(--color-neutral-50)] rounded p-2">
          督导分配/重派 — 案件 assigned_to 切换 + pool_type 改 private + 推送通知给新催收员 + 时间线写入「重新分配」事件。
          {isBatch && "  批量模式:一条失败不影响其他。"}
        </div>

        {currentAssignedTo && (
          <div className="text-xs text-[var(--color-neutral-500)]">
            当前催收员:默认指向其姓名 — user #{currentAssignedTo}
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
              目标不能与当前催收员相同
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
            rows={2}
            placeholder="如「业主投诉换人 / 项目调整」"
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded resize-none"
          />
        </div>

        {/* 提交结果反馈(批量时才有意义) */}
        {lastResult && (
          <div className="rounded border border-[var(--color-neutral-200)] p-3 space-y-2">
            <div className="text-sm font-medium">
              ✅ 成功分配 {lastResult.success_count} 件
              {lastResult.failed.length > 0 &&
                ` · ⚠️ ${lastResult.failed.length} 件未分配`}
            </div>
            {lastResult.failed.length > 0 && (
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {lastResult.failed.map((f) => (
                  <div
                    key={f.case_id}
                    className="text-xs text-[var(--color-neutral-600)] flex gap-2"
                  >
                    <span className="text-[var(--color-neutral-400)] font-mono">
                      #{f.case_id}
                    </span>
                    <span>{f.message}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </RightDrawer>
  );
}
