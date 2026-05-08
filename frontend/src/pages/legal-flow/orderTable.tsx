// 法务订单列表表格 — 三个工作台共享渲染
import { Link } from "react-router-dom";
import { STATUS_BADGES, STATUS_LABELS } from "./_mock";
import type { LegalOrderDTO } from "./api";

interface Props {
  orders: LegalOrderDTO[];
  showTenant?: boolean;
  showFirm?: boolean;
  showLawyer?: boolean;
  detailBasePath: string;
}

export function OrderTable({ orders, showTenant, showFirm, showLawyer, detailBasePath }: Props) {
  if (orders.length === 0) {
    return (
      <div className="ds-card"><div style={{ padding: 32, textAlign: "center", color: "var(--color-neutral-400)" }}>暂无订单</div></div>
    );
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>订单号</th>
            <th>业主 / 房号</th>
            {showTenant && <th>物业租户</th>}
            <th>服务包</th>
            <th>金额</th>
            {showFirm && <th>律所</th>}
            {showLawyer && <th>承办律师</th>}
            <th>状态</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.id}>
              <td style={{ color: "var(--color-primary)", fontFamily: "monospace" }}>#{o.id}</td>
              <td><strong>{o.case_owner ?? "—"}</strong> / {o.case_building ?? ""}</td>
              {showTenant && <td style={{ fontSize: 12 }}>{o.tenant_name ?? "—"}</td>}
              <td>{o.package_label}</td>
              <td>{o.case_amount === null ? "—" : `¥${o.case_amount.toLocaleString("zh-CN")}`}</td>
              {showFirm && <td style={{ fontSize: 12 }}>{o.law_firm_name ?? <span style={{ color: "var(--color-neutral-400)" }}>未派</span>}</td>}
              {showLawyer && <td style={{ fontSize: 12 }}>{o.lawyer_name ?? <span style={{ color: "var(--color-neutral-400)" }}>未分</span>}</td>}
              <td><span className={STATUS_BADGES[o.status]}>{STATUS_LABELS[o.status]}</span></td>
              <td style={{ fontSize: 12, color: "var(--color-neutral-500)" }}>{o.created_at?.replace("T", " ").slice(0, 19) ?? "—"}</td>
              <td>
                <Link to={`${detailBasePath}/${o.id}`} className="ds-btn ds-btn-secondary ds-btn-sm">详情</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
