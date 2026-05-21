// 1:1 还原 ui/agent-pc.html#my-cases 我的案件
// v1.6.5 — 加项目过滤 + 统一 SearchInput / PaginationBar
// v1.6.9 — 公海池抢单：tabs（我的 / 公海）+ 抢单按钮 + 持有上限提示
import { useCustom, useCreate, useCustomMutation, useInvalidate, useList } from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { Eye, Inbox, MessageSquarePlus, Phone, RotateCcw } from "lucide-react";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { PaginatedResponse } from "../../../types";
import { FollowUpNoteModal } from "../../../components/case/FollowUpNoteModal";
import { QrDialDialog } from "../../../components/dial/QrDialDialog";
import { PaginationBar } from "../../../components/ui/PaginationBar";
import { SearchInput } from "../../../components/ui/SearchInput";
import { useDebouncedValue } from "../../../hooks/useDebouncedValue";
// v0.9.0 — 放回公海改 Drawer + 必填理由
import { AgentReleaseToPoolDrawer } from "../../../components/agent/AgentReleaseToPoolDrawer";

interface OwnerInfo {
  id: number;
  name: string;
  phone_masked: string;
  building: string | null;
  room: string | null;
  do_not_call: boolean;
}

interface CaseItem {
  id: number;
  owner: OwnerInfo;
  assigned_to: number | null;
  pool_type: string;
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
  priority_score: number;
  project_id: number | null;
  project_name: string | null;
  last_contact_at?: string | null;
}

interface ProjectOption { id: number; name: string }

const STAGE_LABELS: Record<string, string> = {
  new: "待跟进",
  in_progress: "跟进中",
  promised: "承诺缴费",
  paid: "已缴费",
  escalated: "升级处理",
  closed: "已关闭",
};

const STAGE_BADGE_CLASS: Record<string, string> = {
  new: "ds-badge ds-badge-orange",
  in_progress: "ds-badge ds-badge-blue",
  promised: "ds-badge ds-badge-blue",
  paid: "ds-badge ds-badge-green",
  escalated: "ds-badge ds-badge-purple",
  closed: "ds-badge ds-badge-gray",
};

function formatLast(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const today = new Date();
  if (d.toDateString() === today.toDateString()) return `今天 ${d.toTimeString().slice(0, 5)}`;
  const yest = new Date(); yest.setDate(yest.getDate() - 1);
  if (d.toDateString() === yest.toDateString()) return `昨天 ${d.toTimeString().slice(0, 5)}`;
  return d.toISOString().slice(0, 10);
}

type Tab = "mine" | "pool";

interface PoolQuota {
  held_open: number;
  claim_max: number;
  can_claim_more: boolean;
  remaining: number;
}

export function AgentCaseListPage() {
  const navigate = useNavigate();
  const invalidate = useInvalidate();
  const [tab, setTab] = useState<Tab>("mine");
  const [page, setPage] = useState(1);
  const [stage, setStage] = useState("");
  const [projectId, setProjectId] = useState<string>("");
  const [keyword, setKeyword] = useState("");
  const [todayMode, setTodayMode] = useState(false);  // v1.6.7
  const debouncedKw = useDebouncedValue(keyword, 300);
  const [actingId, setActingId] = useState<number | null>(null);
  // v1.8.0 — 列表行「记录跟进」快捷入口
  const [followUpCase, setFollowUpCase] = useState<{ id: number; ownerName: string } | null>(null);
  const [qrState, setQrState] = useState<{
    caseId: number;
    qrPayload: string;
    expiresAt: string;
  } | null>(null);
  const lastQrCaseId = useRef<number | null>(null);
  const PAGE_SIZE = 20;

  const filters: CrudFilter[] = [];
  if (stage) filters.push({ field: "stage", operator: "eq", value: stage });
  if (projectId) filters.push({ field: "project_id", operator: "eq", value: Number(projectId) });
  if (debouncedKw.trim()) filters.push({ field: "q", operator: "contains", value: debouncedKw.trim() });
  if (todayMode && tab === "mine") filters.push({ field: "today", operator: "eq", value: true });
  // v1.6.9 — 公海 tab 时只看 pool_type=public（后端 _build_visible_case_filter 会自动过滤已分配的）
  if (tab === "pool") filters.push({ field: "pool_type", operator: "eq", value: "public" });

  const { query } = useList<CaseItem>({
    resource: "agent/cases",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });

  // v1.6.9 — 持有数量 + 上限
  const { query: quotaQuery } = useCustom<PoolQuota>({
    url: "agent/me/pool-quota",
    method: "get",
  });
  const quota = quotaQuery.data?.data;

  const { mutate: claimMutate } = useCustomMutation();
  // v0.9.0 — releaseMutate 已下沉到 AgentReleaseToPoolDrawer

  function handleClaim(caseId: number) {
    setActingId(caseId);
    claimMutate(
      { url: `agent/cases/${caseId}/claim`, method: "post", values: {} },
      {
        onSuccess: () => {
          setActingId(null);
          void invalidate({ resource: "agent/cases", invalidates: ["list"] });
          void quotaQuery.refetch();
          alert("✓ 抢单成功，已加入「我的案件」");
        },
        onError: (err) => {
          setActingId(null);
          alert(`抢单失败：${err.message ?? "请重试"}`);
        },
      },
    );
  }

  // v0.9.0 — 放回公海改 Drawer + 必填理由(替换原 window.confirm)
  const [releaseTarget, setReleaseTarget] = useState<{ id: number; name: string } | null>(null);

  function handleRelease(caseId: number, ownerName: string) {
    setReleaseTarget({ id: caseId, name: ownerName });
  }

  // 项目下拉来自专属端点（distinct project visible to agent）
  const { query: projectsQuery } = useCustom<ProjectOption[]>({
    url: "agent/me/projects",
    method: "get",
  });
  const projectOptions: ProjectOption[] = projectsQuery.data?.data ?? [];

  const rawData = query.data?.data;
  const items: CaseItem[] =
    (rawData as unknown as PaginatedResponse<CaseItem>)?.items ??
    (rawData as CaseItem[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;

  const visible = items;

  const { mutate: dialMutate } = useCreate();

  function requestQrPayload(caseId: number) {
    lastQrCaseId.current = caseId;
    dialMutate(
      {
        resource: "calls/dial-request",
        // mode: "qr" — 强制走二维码路径（push 模式需要 MiPush 设备注册，PoC 演示用 qr）
        values: { case_id: caseId, mode: "qr" },
      },
      {
        onSuccess: (resp) => {
          const data = resp.data as { qr_payload?: string; expires_at?: string };
          if (data.qr_payload && data.expires_at) {
            setQrState({
              caseId,
              qrPayload: data.qr_payload,
              expiresAt: data.expires_at,
            });
          } else {
            alert("拨号请求成功但未返回二维码，请联系管理员");
          }
        },
        onError: (err) => {
          alert(`拨号失败：${err.message ?? "未知错误"}`);
        },
      },
    );
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">{tab === "pool" ? "公海池" : "我的案件"}</h1>
          <div className="page-subtitle">
            {tab === "pool"
              ? `共 ${total} 件可抢，先到先得${quota ? `；你已持有 ${quota.held_open}/${quota.claim_max} 件` : ""}`
              : `共 ${total} 件分配案件${quota ? `（持有 ${quota.held_open}/${quota.claim_max}）` : ""}`}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <SearchInput
            value={keyword}
            onChange={(v) => { setKeyword(v); setPage(1); }}
            placeholder="搜索业主姓名 / 房号"
            width={220}
          />
          <select
            className="filter-select"
            value={projectId}
            onChange={(e) => { setProjectId(e.target.value); setPage(1); }}
          >
            <option value="">全部项目</option>
            {projectOptions.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          {tab === "mine" && (
            <select
              className="filter-select"
              value={stage}
              onChange={(e) => { setStage(e.target.value); setPage(1); }}
            >
              <option value="">全部状态</option>
              {Object.entries(STAGE_LABELS).map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          )}
          {tab === "mine" && (
            <button
              type="button"
              data-testid="cases-today-toggle"
              onClick={() => { setTodayMode((v) => !v); setPage(1); }}
              className={`ds-btn ${todayMode ? "ds-btn-primary" : "ds-btn-ghost"} ds-btn-sm`}
              title="只显示今日待联系：未结案 + 今天还没拨过 / 上次联系超过 7 天"
            >
              {todayMode ? "✓ 今日待联系" : "今日待联系"}
            </button>
          )}
          {(keyword || projectId || stage || todayMode) && (
            <button
              type="button"
              className="ds-btn ds-btn-ghost ds-btn-sm"
              onClick={() => { setKeyword(""); setProjectId(""); setStage(""); setTodayMode(false); setPage(1); }}
            >
              清空筛选
            </button>
          )}
        </div>
      </div>

      {/* v1.6.9 — Tab 切换：我的案件 / 公海池 */}
      <div style={{ display: "flex", gap: 4, marginBottom: 12, borderBottom: "1px solid var(--color-neutral-200)" }}>
        <button
          type="button"
          data-testid="cases-tab-mine"
          onClick={() => { setTab("mine"); setPage(1); }}
          style={{
            padding: "8px 16px",
            border: "none",
            background: "transparent",
            borderBottom: tab === "mine" ? "2px solid var(--color-primary)" : "2px solid transparent",
            color: tab === "mine" ? "var(--color-primary)" : "var(--color-neutral-600)",
            fontWeight: tab === "mine" ? 600 : 500,
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          我的案件{quota ? ` (${quota.held_open})` : ""}
        </button>
        <button
          type="button"
          data-testid="cases-tab-pool"
          onClick={() => { setTab("pool"); setPage(1); setStage(""); setTodayMode(false); }}
          style={{
            padding: "8px 16px",
            border: "none",
            background: "transparent",
            borderBottom: tab === "pool" ? "2px solid var(--color-primary)" : "2px solid transparent",
            color: tab === "pool" ? "var(--color-primary)" : "var(--color-neutral-600)",
            fontWeight: tab === "pool" ? 600 : 500,
            cursor: "pointer",
            fontSize: 13,
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
          }}
          title="公海未分配案件，先到先得；按持有上限限制"
        >
          <Inbox size={13} /> 公海池
        </button>
      </div>

      {tab === "pool" && quota && !quota.can_claim_more && (
        <div
          style={{
            padding: "8px 12px",
            marginBottom: 12,
            background: "#fef3c7",
            border: "1px solid #fde68a",
            borderRadius: 6,
            fontSize: 12,
            color: "#92400e",
          }}
        >
          ⚠ 你已达持有上限 {quota.claim_max} 件，请先处理掉部分案件再来抢单（标记缴清/结案后会自动释放配额）
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>业主姓名</th>
              <th>楼栋/房号</th>
              <th>项目</th>
              <th>欠费金额</th>
              <th>欠费月数</th>
              <th>状态</th>
              <th>最近联系</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading && (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!query.isLoading && visible.length === 0 && (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  {tab === "pool" ? "公海当前没有可抢案件" : "暂无分配的案件"}
                </td>
              </tr>
            )}
            {visible.map((c) => {
              const room =
                c.owner.building && c.owner.room
                  ? `${c.owner.building}${c.owner.room}`
                  : c.owner.building ?? c.owner.room ?? "—";
              const isPaid = c.stage === "paid";
              return (
                <tr key={c.id}>
                  <td>
                    <strong>{c.owner.name}</strong>
                    <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>
                      {c.owner.phone_masked}
                    </div>
                  </td>
                  <td>{room}</td>
                  <td style={{ fontSize: 12, color: "var(--color-primary)" }}>
                    {c.project_name ? `📁 ${c.project_name}` : <span style={{ color: "var(--color-neutral-400)" }}>—</span>}
                  </td>
                  <td
                    style={{
                      color: isPaid ? "#057a55" : "#e02424",
                      fontWeight: 600,
                    }}
                  >
                    {c.amount_owed
                      ? `¥${Number(c.amount_owed).toLocaleString()}`
                      : "—"}
                  </td>
                  <td>
                    {c.months_overdue != null ? `${c.months_overdue}个月` : "—"}
                  </td>
                  <td>
                    <span className={STAGE_BADGE_CLASS[c.stage] ?? "ds-badge ds-badge-gray"}>
                      {STAGE_LABELS[c.stage] ?? c.stage}
                    </span>
                  </td>
                  <td>{formatLast(c.last_contact_at)}</td>
                  <td>
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                      {tab === "pool" ? (
                        <>
                          <button
                            type="button"
                            data-testid="case-claim-btn"
                            className="ds-btn ds-btn-primary ds-btn-sm"
                            onClick={() => handleClaim(c.id)}
                            disabled={actingId === c.id || (quota?.can_claim_more === false)}
                            title={
                              quota && !quota.can_claim_more
                                ? `已达上限 ${quota.claim_max} 件`
                                : "抢单：加入「我的案件」"
                            }
                          >
                            <Inbox className="w-3 h-3" />
                            {actingId === c.id ? "抢单中…" : "抢单"}
                          </button>
                          <button
                            type="button"
                            className="ds-btn ds-btn-ghost ds-btn-sm"
                            onClick={() => navigate(`/agent/cases/${c.id}`)}
                          >
                            <Eye className="w-3 h-3" /> 详情
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="ds-btn ds-btn-primary ds-btn-sm"
                            onClick={() => requestQrPayload(c.id)}
                            disabled={actingId === c.id || c.owner.do_not_call}
                            title={c.owner.do_not_call ? "业主已加入免打扰" : "扫码到 App 拨号"}
                          >
                            <Phone className="w-3 h-3" /> 拨号
                          </button>
                          <button
                            type="button"
                            className="ds-btn ds-btn-ghost ds-btn-sm"
                            onClick={() => navigate(`/agent/cases/${c.id}`)}
                          >
                            <Eye className="w-3 h-3" /> 详情
                          </button>
                          {/* v1.8.0 — 列表行「记录跟进」快捷入口 */}
                          <button
                            type="button"
                            className="ds-btn ds-btn-ghost ds-btn-sm"
                            onClick={() => setFollowUpCase({ id: c.id, ownerName: c.owner.name })}
                            title="无需进入详情页，直接写本次跟进备注"
                          >
                            <MessageSquarePlus className="w-3 h-3" /> 记录跟进
                          </button>
                          {/* v1.6.9 — 自己持有的未结案案件可放回公海;v0.9.0 — 改 Drawer + 必填理由 */}
                          {c.stage !== "paid" && c.stage !== "closed" && (
                            <button
                              type="button"
                              className="ds-btn ds-btn-ghost ds-btn-sm"
                              style={{ color: "var(--color-neutral-500)" }}
                              onClick={() => handleRelease(c.id, c.owner.name)}
                              title="把案件放回公海(其他催收员可抢;释放后该案件不再属于你 — 必填理由)"
                            >
                              <RotateCcw className="w-3 h-3" /> 放回公海
                            </button>
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
          total={total}
          onPageChange={setPage}
        />
      </div>

      {qrState && (
        <QrDialDialog
          qrPayload={qrState.qrPayload}
          expiresAt={qrState.expiresAt}
          onClose={() => setQrState(null)}
          onRegenerate={() => requestQrPayload(qrState.caseId)}
        />
      )}

      {/* v1.8.0 — 列表行「记录跟进」Modal */}
      {followUpCase && (
        <FollowUpNoteModal
          caseId={followUpCase.id}
          ownerName={followUpCase.ownerName}
          endpoint={`agent/cases/${followUpCase.id}/stage`}
          invalidateResource="agent/cases"
          onClose={() => setFollowUpCase(null)}
        />
      )}

      {/* v0.9.0 — 放回公海 Drawer(替换 window.confirm,必填理由) */}
      {releaseTarget && (
        <AgentReleaseToPoolDrawer
          caseId={releaseTarget.id}
          ownerName={releaseTarget.name}
          onClose={() => setReleaseTarget(null)}
          onDone={() => {
            setReleaseTarget(null);
            void invalidate({ resource: "agent/cases", invalidates: ["list"] });
            void quotaQuery.refetch();
          }}
        />
      )}
    </div>
  );
}
