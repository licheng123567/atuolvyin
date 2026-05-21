// 法务转化订单详情 — v1.5.7 + v0.5.5(业主信息卡 + 拆价 + 服务包内容)
// admin 点列表行进详情,看到订单全貌 + 业主信息 + 关联案件 + 服务包内容 + 文书 + 时间线
import { useCustom } from "@refinedev/core";
import { ArrowLeft, Briefcase, ExternalLink, FileText, Scale, Shield, User } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { LegalDocumentModal } from "../../../components/legal-conversion/LegalDocumentModal";

interface AttestationItem {
  id: number;
  submitted_at: string;
  case_id: number | null;
  data_type: string;
  cost_amount: string | null;
  tx_hash: string | null;
  chain_provider: string;
  status: string;
}

const DATA_TYPE_LABELS: Record<string, string> = {
  call_recording: "通话录音",
  transcript: "转写文本",
  analysis: "AI 分析",
  evidence_bundle: "证据包",
};

interface OrderDetail {
  id: number;
  case_id: number;
  package_id: number;
  package_name: string | null;
  status: "pending" | "dispatched" | "in_service" | "completed" | "cancelled";
  price_quoted: string;
  platform_fee_amount: string;
  assigned_law_firm: string | null;
  assigned_lawyer_name: string | null;
  dispatched_at: string | null;
  completed_at: string | null;
  created_at: string;
  notes: string | null;
  // v0.5.4 业主上下文 + v0.5.5 详情扩展字段
  owner_name: string | null;
  owner_room: string | null;
  owner_phone_masked: string | null;
  project_name: string | null;
  package_description: string | null;
  package_platform_fee_rate: string | null;
}

const STATUS_LABEL: Record<OrderDetail["status"], string> = {
  pending: "待撮合",
  dispatched: "已派单",
  in_service: "服务中",
  completed: "已完成",
  cancelled: "已取消",
};

const STATUS_BADGE: Record<OrderDetail["status"], string> = {
  pending: "ds-badge ds-badge-gray",
  dispatched: "ds-badge ds-badge-blue",
  in_service: "ds-badge ds-badge-orange",
  completed: "ds-badge ds-badge-green",
  cancelled: "ds-badge ds-badge-red",
};

export function AdminLegalConversionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const orderId = Number(id);
  const [docOpen, setDocOpen] = useState(false);

  const { query } = useCustom<OrderDetail>({
    url: `admin/legal-conversion-orders/${orderId}`,
    method: "get",
    queryOptions: { enabled: !!orderId },
  });

  // v0.6.0 — 关联区块链存证(走 LegalCase → BlockchainAttestation 路径,后端 join)
  const { query: attestQuery } = useCustom<AttestationItem[]>({
    url: `admin/legal-conversion-orders/${orderId}/attestations`,
    method: "get",
    queryOptions: { enabled: !!orderId },
  });
  const attestations: AttestationItem[] = attestQuery.data?.data ?? [];

  const order = query.data?.data;

  return (
    <div style={{ padding: 24, maxWidth: 980 }}>
      <Link
        to="/admin/legal-conversion"
        style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "var(--color-neutral-500)", fontSize: 13.5, textDecoration: "none", marginBottom: 12 }}
      >
        <ArrowLeft className="w-3.5 h-3.5" /> 返回订单列表
      </Link>

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 18 }}>
        <Briefcase style={{ width: 22, height: 22, color: "var(--color-primary)" }} />
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>法务转化订单 #{orderId}</h1>
        {order && (
          <span className={STATUS_BADGE[order.status]} style={{ fontSize: 12 }}>
            {STATUS_LABEL[order.status]}
          </span>
        )}
      </div>

      {query.isLoading && (
        <div style={{ padding: 32, textAlign: "center", color: "var(--color-neutral-400)" }}>加载中…</div>
      )}

      {query.isError && (
        <div className="ds-card">
          <div className="card-body" style={{ padding: 24 }}>
            <p style={{ color: "var(--color-danger)", marginBottom: 8 }}>订单不存在或已删除</p>
            <p style={{ fontSize: 13, color: "var(--color-neutral-500)" }}>
              请返回列表确认订单号；若是最近创建，可能尚未同步。
            </p>
          </div>
        </div>
      )}

      {order && (
        <>
          {/* v0.5.5 — 业主信息卡(优先展示,替换原孤立的案件 #ID) */}
          <div className="ds-card" style={{ marginBottom: 16 }}>
            <div className="card-body" style={{ padding: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 12 }}>
                <User style={{ width: 16, height: 16, color: "var(--color-neutral-500)" }} />
                <div style={{ fontSize: 14, fontWeight: 600 }}>业主信息</div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px 24px" }}>
                <Field
                  label="业主姓名"
                  value={order.owner_name ?? <span style={{ color: "var(--color-neutral-400)" }}>—</span>}
                />
                <Field
                  label="房号"
                  value={order.owner_room ?? <span style={{ color: "var(--color-neutral-400)" }}>—</span>}
                />
                <Field
                  label="所属项目"
                  value={order.project_name ?? <span style={{ color: "var(--color-neutral-400)" }}>—</span>}
                />
                <Field
                  label="联系电话"
                  value={
                    order.owner_phone_masked ? (
                      <span style={{ fontFamily: "monospace" }}>{order.owner_phone_masked}</span>
                    ) : (
                      <span style={{ color: "var(--color-neutral-400)" }}>—</span>
                    )
                  }
                />
                <Field
                  label="关联案件"
                  value={
                    <Link to={`/admin/cases/${order.case_id}`} style={{ color: "var(--color-primary)" }}>
                      案件 #{order.case_id}
                    </Link>
                  }
                />
              </div>
            </div>
          </div>

          {/* v0.5.5 — 订单信息(去重业主部分,聚焦法务履约 + 拆价) */}
          <div className="ds-card" style={{ marginBottom: 16 }}>
            <div className="card-body" style={{ padding: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>订单信息</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px 24px" }}>
                <Field label="服务包" value={order.package_name ?? "—"} />
                <Field label="律所" value={order.assigned_law_firm ?? <span style={{ color: "var(--color-neutral-400)" }}>未派</span>} />
                <Field label="律师" value={order.assigned_lawyer_name ?? <span style={{ color: "var(--color-neutral-400)" }}>未派</span>} />
                <Field
                  label="报价拆分"
                  value={
                    <PriceBreakdown
                      total={order.price_quoted}
                      platformFee={order.platform_fee_amount}
                      rate={order.package_platform_fee_rate}
                    />
                  }
                />
              </div>
              <div
                style={{
                  marginTop: 12,
                  fontSize: 11.5,
                  color: "var(--color-neutral-500)",
                  background: "var(--color-neutral-50)",
                  padding: "8px 10px",
                  borderRadius: 6,
                  lineHeight: 1.6,
                }}
              >
                💡 服务包报价由律所提交、<strong>平台 OPS 统一维护</strong>,对所有物业租户公开同价;
                平台抽成比例可在 OPS 后台调整(详见 PRD §20.4 服务包定价归属)。
              </div>
            </div>
          </div>

          {/* v0.5.5 — 服务包内容卡(含什么服务) */}
          {order.package_description && (
            <div className="ds-card" style={{ marginBottom: 16 }}>
              <div className="card-body" style={{ padding: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
                  服务包内容 — {order.package_name ?? ""}
                </div>
                <div
                  style={{
                    fontSize: 13,
                    color: "var(--color-neutral-700)",
                    whiteSpace: "pre-wrap",
                    lineHeight: 1.65,
                  }}
                >
                  {order.package_description}
                </div>
              </div>
            </div>
          )}

          <div className="ds-card" style={{ marginBottom: 16 }}>
            <div className="card-body" style={{ padding: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>状态时间线</div>
              <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: 13 }}>
                <TimelineItem label="订单创建" time={order.created_at} done />
                <TimelineItem label="律所派单" time={order.dispatched_at} done={!!order.dispatched_at} />
                <TimelineItem label="服务完成" time={order.completed_at} done={!!order.completed_at} />
              </ul>
            </div>
          </div>

          {order.notes && (
            <div className="ds-card" style={{ marginBottom: 16 }}>
              <div className="card-body" style={{ padding: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>备注</div>
                <div style={{ fontSize: 13, color: "var(--color-neutral-700)", whiteSpace: "pre-wrap" }}>{order.notes}</div>
              </div>
            </div>
          )}

          {/* v0.6.0 — 区块链存证(关联本案件下所有 confirmed 上链记录) */}
          <div className="ds-card" style={{ marginBottom: 16 }}>
            <div
              className="card-header"
              style={{ display: "flex", alignItems: "center", gap: 6 }}
            >
              <Shield className="w-4 h-4 text-[var(--color-primary)]" />
              <span className="card-title">区块链存证</span>
              <span
                style={{
                  marginLeft: "auto",
                  fontSize: 12,
                  color: "var(--color-neutral-500)",
                }}
              >
                共 {attestations.length} 条
              </span>
            </div>
            <div className="card-body" style={{ padding: 16 }}>
              {attestQuery.isLoading ? (
                <div style={{ fontSize: 13, color: "var(--color-neutral-500)" }}>
                  加载中…
                </div>
              ) : attestations.length === 0 ? (
                <div style={{ fontSize: 13, color: "var(--color-neutral-500)" }}>
                  本案件暂无上链存证。生成存证包后会自动上链(易保全 / mock),也可在
                  「案件详情 → 下载存证包」时触发。
                </div>
              ) : (
                <table style={{ width: "100%", fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: "var(--color-neutral-50)" }}>
                      <th style={{ textAlign: "left", padding: "8px 10px" }}>时间</th>
                      <th style={{ textAlign: "left", padding: "8px 10px" }}>类型</th>
                      <th style={{ textAlign: "right", padding: "8px 10px" }}>金额</th>
                      <th style={{ textAlign: "left", padding: "8px 10px" }}>链上凭证</th>
                    </tr>
                  </thead>
                  <tbody>
                    {attestations.map((a) => (
                      <tr key={a.id} style={{ borderTop: "1px solid var(--color-neutral-100)" }}>
                        <td style={{ padding: "6px 10px", fontSize: 12 }}>
                          {new Date(a.submitted_at).toLocaleString("zh-CN")}
                        </td>
                        <td style={{ padding: "6px 10px" }}>
                          {DATA_TYPE_LABELS[a.data_type] ?? a.data_type}
                        </td>
                        <td
                          style={{
                            padding: "6px 10px",
                            textAlign: "right",
                            fontFamily: "monospace",
                          }}
                        >
                          {a.cost_amount ? `¥${a.cost_amount}` : "—"}
                        </td>
                        <td style={{ padding: "6px 10px", fontSize: 12 }}>
                          {a.tx_hash ? (
                            <a
                              href={`/api/v1/public/verify/${a.tx_hash}`}
                              target="_blank"
                              rel="noreferrer"
                              style={{
                                color: "var(--color-primary)",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 4,
                              }}
                            >
                              <span style={{ fontFamily: "monospace" }}>
                                {a.tx_hash.slice(0, 12)}…
                              </span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          ) : (
                            <span style={{ color: "var(--color-neutral-400)" }}>
                              易保全 (无 hash)
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" className="ds-btn ds-btn-primary" onClick={() => setDocOpen(true)}>
              <FileText className="w-4 h-4" /> 查看文书
            </button>
            <Link to={`/admin/cases/${order.case_id}`} className="ds-btn ds-btn-secondary">
              <Scale className="w-4 h-4" /> 查看关联案件
            </Link>
          </div>
        </>
      )}

      {docOpen && order && (
        <LegalDocumentModal orderId={order.id} onClose={() => setDocOpen(false)} />
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 13.5 }}>{value}</div>
    </div>
  );
}

/**
 * v0.5.5 — 拆价展示:律所承接价 + 平台服务费 = 总报价。
 * 平台服务费 = 总价 × platform_fee_rate;律所承接价 = 总价 − 平台费。
 */
function PriceBreakdown({
  total,
  platformFee,
  rate,
}: {
  total: string;
  platformFee: string;
  rate: string | null;
}) {
  const totalNum = Number(total);
  const feeNum = Number(platformFee);
  const lawFirmShare = Math.max(0, totalNum - feeNum);
  const ratePct = rate ? (Number(rate) * 100).toFixed(0) : null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <span style={{ fontSize: 16, fontWeight: 700, color: "var(--color-neutral-900)" }}>
        ¥{total}
      </span>
      <span style={{ fontSize: 11.5, color: "var(--color-neutral-500)" }}>
        ＝ 律所承接 ¥{lawFirmShare.toFixed(2)} ＋ 平台服务费 ¥{Number(platformFee).toFixed(2)}
        {ratePct && `(${ratePct}%)`}
      </span>
    </div>
  );
}

function TimelineItem({ label, time, done }: { label: string; time: string | null; done: boolean }) {
  return (
    <li style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0" }}>
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: done ? "var(--color-success)" : "var(--color-neutral-300)",
          flexShrink: 0,
        }}
      />
      <span style={{ fontWeight: done ? 500 : 400, color: done ? "#1f2937" : "var(--color-neutral-400)" }}>{label}</span>
      <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--color-neutral-500)" }}>
        {time ? new Date(time).toLocaleString("zh-CN") : "—"}
      </span>
    </li>
  );
}
