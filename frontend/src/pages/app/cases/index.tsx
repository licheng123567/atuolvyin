// v2.0 Task 4 — Screen 5：案件列表（Android WebView）
// 1:1 对齐 ui/app-agent.html#app-cases
// 数据源：GET /api/v1/agent/cases
import { useList } from "@refinedev/core";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Search } from "lucide-react";
import { Bridge } from "../../../lib/jsBridge";
import { stageBadgeClass, stageLabel } from "../../../lib/caseStage";
import { relativeTimeChinese } from "../../../lib/datetime";

interface OwnerInfo {
  id: number;
  name: string;
  phone?: string | null;
  phone_masked: string;
  building: string | null;
  room: string | null;
  do_not_call: boolean;
}

interface CaseItem {
  id: number;
  tenant_id: number;
  project_id: number | null;
  project_name: string | null;
  owner: OwnerInfo;
  assigned_to: number | null;
  pool_type: string;
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
  priority_score: number;
  last_contact_at: string | null;
  monthly_contact_count: number;
  status: string;
  created_at: string;
  updated_at: string;
}

type Tab = "all" | "follow" | "promised";

const TAB_DEFS: { key: Tab; label: string; stages: string[] | null }[] = [
  { key: "all", label: "全部", stages: null },
  { key: "follow", label: "跟进中", stages: ["new", "in_progress"] },
  { key: "promised", label: "承诺缴费", stages: ["promised"] },
];

const PAGE_SIZE = 20;

function formatYuan(value: string | null | undefined): string {
  if (!value) return "¥0";
  const n = Number(value);
  if (!Number.isFinite(n)) return `¥${value}`;
  return `¥${n.toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`;
}

function formatLastContact(iso: string | null | undefined): string {
  if (!iso) return "未联系";
  return `联系于${relativeTimeChinese(iso)}`;
}

function ownerLocation(o: OwnerInfo): string {
  const parts = [o.building, o.room].filter((x): x is string => !!x);
  return parts.join("");
}

export function MobileCasesPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [tab, setTab] = useState<Tab>("all");
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(1);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  // v2.2 Module B3 — 从 home 搜索图标进入时 (?focus=search) 自动 focus 搜索框
  useEffect(() => {
    if (searchParams.get("focus") === "search" && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [searchParams]);

  // ── 三个 tab 的 total（用最小代价 page_size:1 各拉一次） ─────
  const { query: totalAllQ } = useList<CaseItem>({
    resource: "agent/cases",
    pagination: { currentPage: 1, pageSize: 1 },
  });
  const { query: totalFollowQ } = useList<CaseItem>({
    resource: "agent/cases",
    pagination: { currentPage: 1, pageSize: 1 },
    // backend 只支持单值 stage；这里只取 in_progress 一个；new 单算
    filters: [{ field: "stage", operator: "eq", value: "in_progress" }],
  });
  const { query: totalNewQ } = useList<CaseItem>({
    resource: "agent/cases",
    pagination: { currentPage: 1, pageSize: 1 },
    filters: [{ field: "stage", operator: "eq", value: "new" }],
  });
  const { query: totalPromisedQ } = useList<CaseItem>({
    resource: "agent/cases",
    pagination: { currentPage: 1, pageSize: 1 },
    filters: [{ field: "stage", operator: "eq", value: "promised" }],
  });

  const totalAll = totalAllQ.data?.total ?? 0;
  const totalFollow =
    (totalFollowQ.data?.total ?? 0) + (totalNewQ.data?.total ?? 0);
  const totalPromised = totalPromisedQ.data?.total ?? 0;
  const tabCounts: Record<Tab, number> = {
    all: totalAll,
    follow: totalFollow,
    promised: totalPromised,
  };

  // ── 当前 tab 的列表（注意 backend stage 只支持单值，跟进中需要客户端合并 new+in_progress） ─
  const currentDef = TAB_DEFS.find((t) => t.key === tab) ?? TAB_DEFS[0];

  // 「跟进中」 tab 用 promised 之外的 stage 思路：
  //   方案 A — 不传 stage 拿全部，客户端按 stages 过滤 → 不准 (page 截断)
  //   方案 B — 拉 in_progress 一页 + new 一页拼接 → 太复杂
  //   方案 C — 不传 stage 拉全量；客户端再筛。够用：移动端列表通常 < 200 条
  // 折中：当 tab=follow 时不传 stage，客户端筛 + 客户端分页（pageSize 100，loading "加载更多" 取消）
  // 当 tab=all/promised 时走服务端分页。
  const useClientFilter = tab === "follow";

  const { query: listQ } = useList<CaseItem>({
    resource: "agent/cases",
    pagination: useClientFilter
      ? { currentPage: 1, pageSize: 100 }
      : { currentPage: page, pageSize: PAGE_SIZE },
    filters:
      tab === "promised"
        ? [{ field: "stage", operator: "eq", value: "promised" }]
        : [],
  });

  const isLoading = listQ.isLoading;
  const rawItems: CaseItem[] | undefined = listQ.data?.data;
  const totalForPaging = listQ.data?.total ?? 0;

  // 客户端 tab 过滤（仅 follow 走）
  const tabFiltered = useMemo<CaseItem[]>(() => {
    const items = rawItems ?? [];
    if (!useClientFilter) return items;
    const stages = currentDef.stages ?? [];
    if (stages.length === 0) return items;
    return items.filter((c) => stages.includes(c.stage));
  }, [rawItems, useClientFilter, currentDef.stages]);

  // 客户端 keyword 过滤（统一）
  const visible = useMemo<CaseItem[]>(() => {
    const kw = keyword.trim();
    if (!kw) return tabFiltered;
    const low = kw.toLowerCase();
    return tabFiltered.filter((c) => {
      const haystack = `${c.owner.name} ${c.owner.building ?? ""} ${c.owner.room ?? ""}`.toLowerCase();
      return haystack.includes(low);
    });
  }, [tabFiltered, keyword]);

  const handleOpenCase = (id: number) => {
    if (Bridge.isAndroid()) {
      Bridge.openCaseDetail(id);
    } else {
      navigate(`/app/cases/${id}`);
    }
  };

  return (
    <div>
      {/* ── 顶部标题（白底 sticky） ── */}
      <div
        style={{
          background: "white",
          padding: "12px 16px 0",
          position: "sticky",
          top: 0,
          zIndex: 10,
        }}
      >
        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 10 }}>
          我的案件
        </div>
      </div>

      {/* ── 搜索框 ── */}
      <div className="search-bar-mobile">
        <Search size={16} strokeWidth={2} aria-hidden />
        <input
          ref={searchInputRef}
          type="text"
          placeholder="搜索业主姓名或房号..."
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
      </div>

      {/* ── Tab pill ── */}
      <div className="filter-tabs-mobile">
        {TAB_DEFS.map((t) => (
          <div
            key={t.key}
            className={`filter-tab-m ${tab === t.key ? "active" : ""}`}
            onClick={() => {
              setTab(t.key);
              setPage(1);
            }}
          >
            {t.label} ({tabCounts[t.key]})
          </div>
        ))}
      </div>

      {/* ── 列表 ── */}
      <div style={{ padding: "12px 16px 0" }}>
        {isLoading && (
          <div
            style={{
              padding: 24,
              textAlign: "center",
              color: "#9ca3af",
              fontSize: 13,
            }}
          >
            加载中…
          </div>
        )}
        {!isLoading && visible.length === 0 && (
          <div
            style={{
              background: "white",
              padding: 24,
              borderRadius: 10,
              textAlign: "center",
              color: "#9ca3af",
              fontSize: 13,
            }}
          >
            暂无案件
          </div>
        )}
        {visible.map((c) => (
          <div
            key={c.id}
            className="case-card-full"
            onClick={() => handleOpenCase(c.id)}
            style={{ cursor: "pointer" }}
          >
            <div className="case-card-row1">
              <div className="case-card-name">{c.owner.name}</div>
              <div className="case-card-amount">{formatYuan(c.amount_owed)}</div>
            </div>
            <div className="case-card-row2">
              <div className="case-card-sub">
                {ownerLocation(c.owner)}
                {c.months_overdue ? ` · 欠${c.months_overdue}个月` : ""}
                {` · ${formatLastContact(c.last_contact_at)}`}
              </div>
              <span className={stageBadgeClass(c.stage)} style={{ fontSize: 11 }}>
                {stageLabel(c.stage)}
              </span>
            </div>
          </div>
        ))}

        {/* ── 服务端分页：仅 all/promised 模式有效 ── */}
        {!useClientFilter && !isLoading && visible.length > 0 && (
          <div
            style={{
              padding: "16px 0",
              textAlign: "center",
              color: "#9ca3af",
              fontSize: 12,
            }}
          >
            {page * PAGE_SIZE >= totalForPaging ? (
              <span>已加载全部 {totalForPaging} 条</span>
            ) : (
              <button
                type="button"
                onClick={() => setPage((p) => p + 1)}
                style={{
                  background: "white",
                  border: "1px solid #d1d5db",
                  borderRadius: 8,
                  padding: "8px 18px",
                  fontSize: 13,
                  color: "#374151",
                  cursor: "pointer",
                }}
              >
                加载更多
              </button>
            )}
          </div>
        )}
      </div>

      {/* 底部留 70px 给 Compose tab bar */}
      <div style={{ height: 70 }} />
    </div>
  );
}

export default MobileCasesPage;
