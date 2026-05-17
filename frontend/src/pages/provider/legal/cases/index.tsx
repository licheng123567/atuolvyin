// §9.1 — 服务商法务-案件浏览列表页（只读，手机号脱敏）
import { useGo } from "@refinedev/core";
import { Scale } from "lucide-react";
import { useMemo, useState } from "react";
import { PaginationBar } from "../../../../components/ui/PaginationBar";
import { SearchInput } from "../../../../components/ui/SearchInput";
import { useDebouncedValue } from "../../../../hooks/useDebouncedValue";
import { useProviderLegalCases } from "../api";
import { TableStateRow } from "../TableStateRow";

const PAGE_SIZE = 20;

export function ProviderLegalCasesPage() {
  const go = useGo();
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState("");
  const debouncedKw = useDebouncedValue(keyword, 300);

  const { items, total, isLoading, isError } = useProviderLegalCases({ page, pageSize: PAGE_SIZE });

  const filteredItems = useMemo(() => {
    const kw = debouncedKw.trim().toLowerCase();
    if (!kw) return items;
    return items.filter((c) => {
      const ownerMatch = (c.owner_name ?? "").toLowerCase().includes(kw);
      const roomMatch = `${c.building ?? ""}${c.room ?? ""}`.toLowerCase().includes(kw);
      return ownerMatch || roomMatch;
    });
  }, [items, debouncedKw]);

  return (
    <div>
      <div className="page-header">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Scale size={20} style={{ color: "var(--color-primary)" }} />
            <h1 className="page-title">法务案件</h1>
          </div>
          <p className="page-subtitle">浏览本服务商承接项目下的案件（只读，手机号脱敏）</p>
        </div>
      </div>

      <div style={{ marginBottom: 12 }}>
        <SearchInput
          value={keyword}
          onChange={(v) => { setKeyword(v); setPage(1); }}
          placeholder="搜索业主 / 房号"
          width={240}
        />
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>业主 / 房号</th>
              <th>项目</th>
              <th>欠费金额</th>
              <th>逾期</th>
              <th>案件阶段</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <TableStateRow colSpan={6}>加载中…</TableStateRow>}
            {isError && !isLoading && <TableStateRow colSpan={6}>加载失败</TableStateRow>}
            {!isLoading && !isError && filteredItems.length === 0 && (
              <TableStateRow colSpan={6}>{keyword ? "无匹配结果" : "暂无案件"}</TableStateRow>
            )}
            {!isLoading && !isError && filteredItems.map((c) => (
              <tr key={c.case_id}>
                <td>
                  <div>
                    <strong>{c.owner_name ?? "—"}</strong>
                    {` ${c.building ?? ""}${c.room ?? ""}`}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--color-neutral-500)" }}>
                    {c.owner_phone_masked}
                  </div>
                </td>
                <td>{c.project_name ?? "—"}</td>
                <td>¥{c.amount_owed ?? "0.00"}</td>
                <td>{c.months_overdue ?? 0} 月</td>
                <td>
                  <span className="ds-badge ds-badge-blue">{c.stage}</span>
                </td>
                <td>
                  <button
                    type="button"
                    className="ds-btn ds-btn-ghost ds-btn-sm"
                    onClick={() => go({ to: `/provider/legal/cases/${c.case_id}` })}
                  >
                    查看
                  </button>
                </td>
              </tr>
            ))}
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
