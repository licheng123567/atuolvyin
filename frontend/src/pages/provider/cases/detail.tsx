// v0.5.6 — 服务商管理员案件详情页
//
// 范围:**只读** + 「分配/重新分配」+「释放回服务商公海」两类操作。
// 不开放:发缴费链接 / 创建工单 / 申请减免 / 标记承诺缴费 / 升级督导 / 申请转法务 等
// (这些动作仍由物业 admin 或服务商 supervisor 那一侧操作,服务商 admin 只做调度)
import { useCustom, useCustomMutation, useGo } from "@refinedev/core";
import { ArrowLeft, Inbox, UserCheck } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { ActivityTimeline } from "../../../components/case/ActivityTimeline";
import { OwnerInfoCard } from "../../../components/case/OwnerInfoCard";
import { ProjectInfoCard } from "../../../components/case/ProjectInfoCard";
import type { CaseDetailResponse } from "../../../types/case";
import { ProviderAssignDrawer } from "./ProviderAssignDrawer";

export function ProviderCaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();
  const [assignOpen, setAssignOpen] = useState(false);
  const [releasing, setReleasing] = useState(false);

  const { query } = useCustom<CaseDetailResponse>({
    url: `provider/cases/${id ?? ""}`,
    method: "get",
    queryOptions: { enabled: !!id },
  });
  const detail = query.data?.data;
  const { mutate: releaseMutate } = useCustomMutation();

  if (query.isLoading) {
    return <div style={{ padding: 32, color: "var(--color-neutral-400)" }}>加载中…</div>;
  }
  if (!detail) {
    return (
      <div style={{ padding: 32, color: "var(--color-danger)" }}>
        案件不存在或不在本服务商接手项目范围
      </div>
    );
  }

  const handleRelease = () => {
    if (!window.confirm(`确认把「${detail.owner.name}」释放回服务商公海?\n当前催收员将看不到此案件。`)) {
      return;
    }
    setReleasing(true);
    releaseMutate(
      {
        url: `provider/cases/${detail.id}/release`,
        method: "post",
        values: {},
      },
      {
        onSuccess: () => {
          setReleasing(false);
          query.refetch();
        },
        onError: (err) => {
          setReleasing(false);
          alert(`释放失败:${(err as { message?: string }).message ?? "请重试"}`);
        },
      },
    );
  };

  return (
    <div>
      <div className="breadcrumb">
        <button
          type="button"
          onClick={() => go({ to: "/provider/cases" })}
          className="ds-btn ds-btn-ghost ds-btn-sm"
          style={{ padding: 0 }}
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          案件管理
        </button>
        <span style={{ margin: "0 6px", color: "var(--color-neutral-400)" }}>›</span>
        <span style={{ color: "var(--color-neutral-700)", fontWeight: 500 }}>
          {detail.owner.name}({detail.owner.building ?? ""} {detail.owner.room ?? ""})
        </span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.4fr) 260px",
          gap: 16,
          padding: "0 16px 16px",
        }}
      >
        {/* 左:业主信息 + 项目情况 */}
        <div>
          <OwnerInfoCard detail={detail} />
          <ProjectInfoCard detail={detail} />
        </div>

        {/* 中:活动时间线 */}
        <div style={{ minWidth: 0 }}>
          <ActivityTimeline
            calls={detail.calls}
            timelineEvents={detail.timeline_events}
            createdAt={detail.created_at}
          />
        </div>

        {/* 右:sticky 操作 */}
        <div
          style={{
            position: "sticky",
            top: 16,
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <div className="ds-card" style={{ padding: 14 }}>
            <div style={{ fontSize: 12.5, fontWeight: 700, color: "#374151", marginBottom: 10 }}>
              调度操作
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <button
                type="button"
                className="ds-btn ds-btn-primary"
                style={{ width: "100%", justifyContent: "center" }}
                onClick={() => setAssignOpen(true)}
              >
                <UserCheck className="w-3.5 h-3.5" />
                {detail.assigned_to ? "重新分配" : "分配给员工"}
              </button>
              {detail.assigned_to && (
                <button
                  type="button"
                  className="ds-btn ds-btn-secondary"
                  style={{ width: "100%", justifyContent: "center" }}
                  onClick={handleRelease}
                  disabled={releasing}
                >
                  <Inbox className="w-3.5 h-3.5" />
                  {releasing ? "处理中…" : "释放回公海"}
                </button>
              )}
            </div>
            <div
              style={{
                marginTop: 10,
                fontSize: 11,
                color: "var(--color-neutral-500)",
                lineHeight: 1.6,
              }}
            >
              服务商管理员仅做案件调度。改阶段 / 跟进备注 / 发缴费链接 / 标记承诺缴费等动作走「催收员」或「督导」工作台。
            </div>
          </div>
        </div>
      </div>

      {assignOpen && (
        <ProviderAssignDrawer
          caseId={detail.id}
          ownerName={detail.owner.name}
          currentAssignedTo={detail.assigned_to}
          onClose={() => setAssignOpen(false)}
          onDone={() => {
            setAssignOpen(false);
            query.refetch();
          }}
        />
      )}
    </div>
  );
}

export default ProviderCaseDetailPage;
