// 减免审批列表 — 督导 / admin 共用，按 props.role 区分
// v1.6.5 — 加分页（服务端 page/pageSize）+ 搜索（前端，后端暂无 keyword）
import { CheckCircle2, ClipboardList, Eye, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { HelpPanel } from "../../components/ui/HelpPanel";
import { PaginationBar } from "../../components/ui/PaginationBar";
import { SearchInput } from "../../components/ui/SearchInput";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { useDiscountPolicy } from "../../hooks/useDiscountPolicy";
import { STATUS_BADGES, STATUS_LABELS } from "./_mock";
import {
  useApproveOffer, useDiscountOffers, useEscalateOffer, useRejectOffer,
  type DiscountOfferDTO,
} from "./api";
import { SourceBadge } from "./SourceBadge";

const PAGE_SIZE = 20;

interface Props {
  approverRole: "supervisor" | "admin";
  approverName: string;
  detailBasePath: string;
}

export function ApprovalListPage({ approverRole, approverName: _approverName, detailBasePath }: Props) {
  const [tab, setTab] = useState<"pending" | "all">("pending");
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState("");
  const debouncedKw = useDebouncedValue(keyword, 300);
  const [actingOn, setActingOn] = useState<{ offer: DiscountOfferDTO; mode: "approve" | "reject" | "escalate" } | null>(null);
  const policy = useDiscountPolicy();

  const pendingStatus = approverRole === "supervisor" ? "pending_supervisor" : "pending_admin";
  const { items: pageItems, total: visibleTotal } = useDiscountOffers(
    tab === "pending" ? { myPending: true, page, pageSize: PAGE_SIZE } : { page, pageSize: PAGE_SIZE },
  );
  // 计数仅取 total，pageSize=1 避免拉全量
  const { total: pendingCount } = useDiscountOffers({ myPending: true, page: 1, pageSize: 1 });
  const { total: approvedCount } = useDiscountOffers({ status: "approved", page: 1, pageSize: 1 });
  const { total: rejectedCount } = useDiscountOffers({ status: "rejected", page: 1, pageSize: 1 });
  const { total: executedCount } = useDiscountOffers({ status: "executed", page: 1, pageSize: 1 });

  const counts = {
    pending: pendingCount,
    approved: approvedCount,
    rejected: rejectedCount,
    executed: executedCount,
  };

  // 后端暂未支持 keyword，前端在当前页内做过滤（业主姓名 / 房号 / 申请号）
  const visibleItems = useMemo(() => {
    const kw = debouncedKw.trim().toLowerCase();
    if (!kw) return pageItems;
    return pageItems.filter((o) =>
      `${o.case_owner ?? ""} ${o.case_building ?? ""} ${o.id}`.toLowerCase().includes(kw),
    );
  }, [pageItems, debouncedKw]);

  return (
    <div>
      <div className="page-header">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <ClipboardList size={20} style={{ color: "var(--color-primary)" }} />
            <div className="page-title">减免审批 — {approverRole === "supervisor" ? "督导视角" : "物业 admin 视角"}</div>
          </div>
          <div className="page-subtitle">
            {approverRole === "supervisor"
              ? `审批 ${policy.autoThreshold}–${policy.supervisorMax}% 减免 / 分期 / 违约金减免（> ${policy.supervisorMax}% 转 admin）`
              : `审批 > ${policy.supervisorMax}% 大额减免 / 跨项目特批（督导无权操作）`}
          </div>
        </div>
      </div>

      <HelpPanel
        tone="info"
        dismissKey={`/discount-approvals/${approverRole}`}
        title="减免权限矩阵（admin 已配置）"
        bullets={[
          policy.disabled ? (
            <><strong style={{ color: "var(--color-danger)" }}>本租户已停用减免功能</strong> — 仅可处理已存量未执行的 offer</>
          ) : policy.autoThreshold === 0 ? (
            <><strong>所有减免均需人工审批</strong>（admin 已关闭自动通过）</>
          ) : (
            <><strong>催收员（自动）</strong>：减免 &lt; {policy.autoThreshold}% 直接生效（仅记审计）</>
          ),
          <><strong>督导审批</strong>：减免 {policy.autoThreshold}–{policy.supervisorMax}% / 分期 ≤ 12 期 / 违约金减免</>,
          <><strong>admin 审批</strong>：减免 &gt; {policy.supervisorMax}% / 分期 &gt; 12 期 / 跨项目批量减免</>,
          <><strong>有效期</strong>：批准后 7 天内业主必须按方案缴清，超期 offer 自动失效</>,
        ]}
        footer="阈值由 admin 在「系统配置 → 减免审批策略」调整；所有决策记入审计日志"
      />

      <div className="status-bar">
        <div className="status-bar-item" style={{ color: "var(--color-warning)" }}>
          <ClipboardList size={14} /> 待我审批 <strong>{counts.pending}</strong>
        </div>
        <div className="status-bar-item" style={{ color: "var(--color-primary)" }}>
          已批准 <strong>{counts.approved}</strong>
        </div>
        <div className="status-bar-item" style={{ color: "var(--color-danger)" }}>
          已拒绝 <strong>{counts.rejected}</strong>
        </div>
        <div className="status-bar-item" style={{ color: "var(--color-success)" }}>
          <CheckCircle2 size={14} /> 业主已执行 <strong>{counts.executed}</strong>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <SearchInput
          value={keyword}
          onChange={(v) => { setKeyword(v); setPage(1); }}
          placeholder="按申请号 / 业主 / 房号搜索"
          width={240}
        />
        <button type="button" className={`ds-btn ${tab === "pending" ? "ds-btn-primary" : "ds-btn-secondary"} ds-btn-sm`} onClick={() => { setTab("pending"); setPage(1); }}>
          待审批（{counts.pending}）
        </button>
        <button type="button" className={`ds-btn ${tab === "all" ? "ds-btn-primary" : "ds-btn-secondary"} ds-btn-sm`} onClick={() => { setTab("all"); setPage(1); }}>
          全部历史（{visibleTotal}）
        </button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>申请号</th>
              <th>业主 / 房号</th>
              <th>来源</th>
              <th>类型</th>
              <th>原金额 → 业主同意</th>
              <th>折扣</th>
              <th>申请人</th>
              <th>状态</th>
              <th>有效期至</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {visibleItems.length === 0 && (
              <tr><td colSpan={10} style={{ textAlign: "center", padding: 32, color: "var(--color-neutral-400)" }}>
                暂无审批
              </td></tr>
            )}
            {visibleItems.map((o) => {
              const canActHere = o.status === pendingStatus;
              return (
                <tr key={o.id}>
                  <td style={{ color: "var(--color-primary)", fontFamily: "monospace" }}>#{o.id}</td>
                  <td><strong>{o.case_owner ?? "—"}</strong> / {o.case_building ?? ""}</td>
                  <td>
                    <SourceBadge providerId={o.provider_id} providerName={o.provider_name} />
                  </td>
                  <td>{o.offer_type_label}{o.installment_months ? `（${o.installment_months} 期）` : ""}</td>
                  <td>
                    <span style={{ color: "var(--color-neutral-500)", textDecoration: "line-through" }}>¥{Number(o.original_amount).toLocaleString("zh-CN")}</span>
                    <span style={{ margin: "0 4px", color: "var(--color-neutral-400)" }}>→</span>
                    <span style={{ fontWeight: 600 }}>¥{Number(o.proposed_amount).toLocaleString("zh-CN")}</span>
                  </td>
                  <td>
                    <span style={{
                      fontWeight: 600,
                      color: o.discount_pct > policy.supervisorMax ? "var(--color-danger)" : o.discount_pct >= policy.autoThreshold ? "var(--color-warning)" : "var(--color-success)",
                    }}>
                      {o.discount_pct}%
                    </span>
                  </td>
                  <td style={{ fontSize: 12 }}>{o.applicant_name ?? "—"}</td>
                  <td><span className={STATUS_BADGES[o.status]}>{STATUS_LABELS[o.status]}</span></td>
                  <td style={{ fontSize: 12, color: "var(--color-neutral-500)" }}>{o.expires_at?.slice(0, 10) ?? "—"}</td>
                  <td>
                    <div style={{ display: "flex", gap: 4 }}>
                      <Link to={`${detailBasePath}/${o.id}`} className="ds-btn ds-btn-secondary ds-btn-sm">
                        <Eye size={12} /> 详情
                      </Link>
                      {canActHere && (
                        <>
                          <button type="button" className="ds-btn ds-btn-primary ds-btn-sm" onClick={() => setActingOn({ offer: o, mode: "approve" })}>批准</button>
                          <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" style={{ color: "var(--color-danger)" }} onClick={() => setActingOn({ offer: o, mode: "reject" })}>拒绝</button>
                          {approverRole === "supervisor" && (
                            <button type="button" className="ds-btn ds-btn-ghost ds-btn-sm" onClick={() => setActingOn({ offer: o, mode: "escalate" })}>转 admin</button>
                          )}
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <PaginationBar
          page={page}
          pageSize={PAGE_SIZE}
          total={visibleTotal}
          onPageChange={setPage}
        />
      </div>

      {actingOn && (
        <ActionModal
          offer={actingOn.offer}
          mode={actingOn.mode}
          onClose={() => setActingOn(null)}
        />
      )}
    </div>
  );
}

function ActionModal({ offer, mode, onClose }: { offer: DiscountOfferDTO; mode: "approve" | "reject" | "escalate"; onClose: () => void }) {
  const [note, setNote] = useState("");
  const { approve, isPending: approving } = useApproveOffer();
  const { reject, isPending: rejecting } = useRejectOffer();
  const { escalate, isPending: escalating } = useEscalateOffer();
  const isPending = approving || rejecting || escalating;

  const titleMap = { approve: "批准减免申请", reject: "拒绝减免申请", escalate: "转 admin 审批" };
  const placeholderMap = {
    approve: "（可选）批准备注，如「业主家庭确实困难，可一次性结清」",
    reject: "（必填）拒绝原因，如「减免比例过高，建议再谈判」",
    escalate: "（可选）转交说明",
  };

  function submit() {
    if (mode === "reject" && !note.trim()) return alert("拒绝时必须填写原因");
    if (mode === "approve") approve(offer.id, note, { onSuccess: onClose });
    if (mode === "reject") reject(offer.id, note, { onSuccess: onClose });
    if (mode === "escalate") escalate(offer.id, note, { onSuccess: onClose });
  }

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }} onClick={onClose}>
      <div style={{ background: "white", borderRadius: 8, width: 480, maxWidth: "92%" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ padding: 16, borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between" }}>
          <span style={{ fontWeight: 600 }}>{titleMap[mode]}</span>
          <button type="button" onClick={onClose} style={{ border: "none", background: "transparent", cursor: "pointer" }}><X size={18} /></button>
        </div>
        <div style={{ padding: 16, fontSize: 13, color: "#374151", lineHeight: 1.7 }}>
          <div style={{ marginBottom: 10, padding: 10, background: "#f9fafb", borderRadius: 6 }}>
            <div><strong>{offer.case_owner ?? "—"}</strong> / {offer.case_building ?? ""}</div>
            <div style={{ fontSize: 12, color: "var(--color-neutral-600)", marginTop: 2 }}>
              {offer.offer_type_label} · ¥{Number(offer.original_amount).toLocaleString("zh-CN")} → ¥{Number(offer.proposed_amount).toLocaleString("zh-CN")}（{offer.discount_pct}%）
            </div>
            <div style={{ fontSize: 12, color: "var(--color-neutral-700)", marginTop: 6, lineHeight: 1.6 }}>
              申请理由：{offer.reason}
            </div>
          </div>
          <textarea
            className="form-control"
            rows={4}
            placeholder={placeholderMap[mode]}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>
        <div style={{ padding: 16, borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button type="button" className="ds-btn ds-btn-secondary" onClick={onClose} disabled={isPending}>取消</button>
          <button type="button" className="ds-btn ds-btn-primary" onClick={submit} disabled={isPending}>
            {isPending ? "处理中…" : `确认${titleMap[mode]}`}
          </button>
        </div>
      </div>
    </div>
  );
}
