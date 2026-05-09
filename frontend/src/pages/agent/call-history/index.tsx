// 1:1 还原 ui/agent-pc.html#call-history 通话记录
// v1.6.5 — 接真实后端 GET /api/v1/agent/me/call-history
// 「查看转写 / 详情」跳到 /calls/:id（CallDetailPage）；「回到工作台」跳到 /agent/workstation/:id
import { useCustom } from "@refinedev/core";
import { Download } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PaginationBar } from "../../../components/ui/PaginationBar";
import { SearchInput } from "../../../components/ui/SearchInput";
import { useDebouncedValue } from "../../../hooks/useDebouncedValue";

const PAGE_SIZE = 20;

interface CallHistoryItem {
  call_id: number;
  started_at: string | null;
  duration_sec: number | null;
  result_tag: string | null;
  case_id: number | null;
  owner_name: string | null;
  building: string | null;
  room: string | null;
  project_id: number | null;
  project_name: string | null;
  has_transcript: boolean;
  has_analysis: boolean;
  recording_url?: string | null;  // v1.6.7 — E5 inline 录音
  score?: number | null;           // v1.6.7 — E6 综合评分 0-100
}

interface ProjectOption { id: number; name: string }

interface ListResp {
  items: CallHistoryItem[];
  total: number;
  page: number;
  page_size: number;
}

const RESULT_OPTIONS: { value: string; label: string; badge: string }[] = [
  { value: "promised", label: "承诺缴费", badge: "ds-badge ds-badge-blue" },
  { value: "paid", label: "已缴费", badge: "ds-badge ds-badge-green" },
  { value: "refused", label: "拒绝", badge: "ds-badge ds-badge-red" },
  { value: "missed", label: "未接通", badge: "ds-badge ds-badge-gray" },
];

function badgeFor(result: string | null): { label: string; cls: string } {
  if (!result) return { label: "—", cls: "ds-badge ds-badge-gray" };
  const hit = RESULT_OPTIONS.find((o) => result.includes(o.value));
  if (hit) return { label: hit.label, cls: hit.badge };
  return { label: result, cls: "ds-badge ds-badge-gray" };
}

function formatDuration(sec: number | null): string {
  if (!sec || sec < 0) return "—";
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toTimeString().slice(0, 8);
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

export function AgentCallHistoryPage() {
  const navigate = useNavigate();
  const [dateFrom, setDateFrom] = useState(todayStr());
  const [dateTo, setDateTo] = useState(todayStr());
  const [resultFilter, setResultFilter] = useState("");
  const [projectFilter, setProjectFilter] = useState("");
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(1);
  const debouncedKw = useDebouncedValue(keyword, 300);

  // 项目下拉复用 agent/me/projects（已有）
  const { query: projectsQuery } = useCustom<ProjectOption[]>({
    url: "agent/me/projects",
    method: "get",
  });
  const projectOptions: ProjectOption[] = projectsQuery.data?.data ?? [];

  const query: Record<string, string | number> = {
    page,
    page_size: PAGE_SIZE,
  };
  if (dateFrom) query.date_from = dateFrom;
  if (dateTo) query.date_to = dateTo;
  if (resultFilter) query.result = resultFilter;
  if (projectFilter) query.project_id = projectFilter;
  if (debouncedKw.trim()) query.q = debouncedKw.trim();

  const { query: listQuery } = useCustom<ListResp>({
    url: "agent/me/call-history",
    method: "get",
    config: { query },
  });
  const items: CallHistoryItem[] = listQuery.data?.data?.items ?? [];
  const total = listQuery.data?.data?.total ?? 0;
  const isLoading = listQuery.isLoading;

  const totalDurationMin = items.reduce(
    (s, c) => s + (c.duration_sec ? c.duration_sec / 60 : 0),
    0,
  );

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">通话记录</div>
          <div className="page-subtitle">
            筛选范围内 {total} 通，已加载 {items.length} 通 · 总时长约 {Math.round(totalDurationMin)} 分钟
          </div>
        </div>
      </div>

      {/* 筛选条 */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <SearchInput
          value={keyword}
          onChange={(v) => { setKeyword(v); setPage(1); }}
          placeholder="按业主 / 楼栋 / 房号搜索"
          width={220}
        />
        <select
          className="filter-select"
          value={projectFilter}
          onChange={(e) => { setProjectFilter(e.target.value); setPage(1); }}
        >
          <option value="">全部项目</option>
          {projectOptions.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <select
          className="filter-select"
          value={resultFilter}
          onChange={(e) => { setResultFilter(e.target.value); setPage(1); }}
        >
          <option value="">全部结果</option>
          {RESULT_OPTIONS.map((r) => (
            <option key={r.value} value={r.value}>{r.label}</option>
          ))}
        </select>
        <span style={{ fontSize: 12, color: "var(--color-neutral-600)" }}>从</span>
        <input
          type="date"
          className="filter-select"
          value={dateFrom}
          onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
          style={{ height: 32 }}
        />
        <span style={{ fontSize: 12, color: "var(--color-neutral-600)" }}>到</span>
        <input
          type="date"
          className="filter-select"
          value={dateTo}
          onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
          style={{ height: 32 }}
        />
        {(keyword || projectFilter || resultFilter || dateFrom !== todayStr() || dateTo !== todayStr()) && (
          <button
            type="button"
            className="ds-btn ds-btn-ghost ds-btn-sm"
            onClick={() => {
              setKeyword(""); setProjectFilter(""); setResultFilter("");
              setDateFrom(todayStr()); setDateTo(todayStr()); setPage(1);
            }}
          >
            清空筛选
          </button>
        )}
        <button
          type="button"
          className="ds-btn ds-btn-secondary ds-btn-sm"
          style={{ marginLeft: "auto" }}
          onClick={() => alert("导出 Excel — v1.7 wired")}
        >
          <Download className="w-3 h-3" /> 导出记录
        </button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>通话时间</th>
              <th>业主姓名</th>
              <th>楼栋/房号</th>
              <th>项目</th>
              <th>通话时长</th>
              <th>通话结果</th>
              <th>AI 评分</th>
              <th>录音</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={9} style={{ textAlign: "center", padding: 32, color: "var(--color-neutral-400)" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td colSpan={9} style={{ textAlign: "center", padding: 32, color: "var(--color-neutral-400)" }}>
                  暂无符合条件的通话
                </td>
              </tr>
            )}
            {items.map((c) => {
              const room = c.building && c.room ? `${c.building}${c.room}` : (c.building ?? c.room ?? "—");
              const badge = badgeFor(c.result_tag);
              const inProgress = c.duration_sec == null && c.started_at != null;
              return (
                <tr key={c.call_id}>
                  <td style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 12.5 }}>
                    {formatTime(c.started_at)}
                  </td>
                  <td><strong>{c.owner_name ?? "—"}</strong></td>
                  <td>{room}</td>
                  <td style={{ fontSize: 12, color: "var(--color-primary)" }}>
                    {c.project_name ? `📁 ${c.project_name}` : <span style={{ color: "var(--color-neutral-400)" }}>—</span>}
                  </td>
                  <td>{inProgress ? "进行中" : formatDuration(c.duration_sec)}</td>
                  <td>
                    {inProgress
                      ? <span className="ds-badge ds-badge-red">通话中</span>
                      : <span className={badge.cls}>{badge.label}</span>}
                  </td>
                  {/* v1.6.7 — E6 AI 评分列 */}
                  <td>
                    {c.score != null ? (
                      <span style={{
                        fontFamily: "var(--font-mono, monospace)", fontSize: 13, fontWeight: 700,
                        color: c.score >= 80 ? "#15803d" : c.score >= 60 ? "#1d4ed8" : "#b45309",
                      }}>{c.score}</span>
                    ) : (
                      <span style={{ color: "var(--color-neutral-400)" }}>—</span>
                    )}
                  </td>
                  {/* v1.6.7 — E5 inline 录音播放 */}
                  <td>
                    {c.recording_url ? (
                      <audio
                        controls
                        preload="none"
                        src={c.recording_url}
                        style={{ height: 28, width: 180 }}
                      />
                    ) : (
                      <span style={{ color: "var(--color-neutral-400)", fontSize: 12 }}>—</span>
                    )}
                  </td>
                  <td>
                    {inProgress ? (
                      <button
                        type="button"
                        className="ds-btn ds-btn-primary ds-btn-sm"
                        onClick={() => navigate(`/agent/workstation/${c.call_id}`)}
                      >
                        回到工作台
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="ds-btn ds-btn-ghost ds-btn-sm"
                        onClick={() => navigate(`/calls/${c.call_id}`)}
                      >
                        {c.has_transcript ? "查看转写" : "查看详情"}
                      </button>
                    )}
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
    </div>
  );
}
