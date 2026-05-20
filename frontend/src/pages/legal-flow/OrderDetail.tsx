// 法务订单详情 — 三个工作台共用，通过 actor 决定操作权限
import { ArrowLeft, FileText, Upload, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { SearchableSelect } from "../../components/ui/SearchableSelect";
import { DOC_LABELS, STATUS_BADGES, STATUS_LABELS, type DocType } from "./_mock";
import {
  useAssignLawyer, useCompleteOrder, useLawyersInMyFirm, useLegalOrder,
  useUploadDocument, type LegalOrderDTO,
} from "./api";

type Actor = "tenant_legal" | "firm_admin" | "lawyer";

interface Props {
  orderId: number;
  actor: Actor;
  backTo: string;
}

const ACTOR_VIEW: Record<Actor, "tenant_legal" | "lawfirm" | "lawyer"> = {
  tenant_legal: "tenant_legal",
  firm_admin: "lawfirm",
  lawyer: "lawyer",
};

export function OrderDetail({ orderId, actor, backTo }: Props) {
  const view = ACTOR_VIEW[actor];
  const { order, isLoading, isError } = useLegalOrder(view, orderId);

  if (isLoading) {
    return <div style={{ padding: 24, color: "var(--color-neutral-400)" }}>加载中…</div>;
  }
  if (isError || !order) {
    return (
      <div style={{ padding: 24 }}>
        <Link to={backTo} style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "var(--color-neutral-500)", fontSize: 13 }}>
          <ArrowLeft size={14} /> 返回订单列表
        </Link>
        <div className="ds-card" style={{ marginTop: 12 }}><div style={{ padding: 32, textAlign: "center", color: "var(--color-neutral-400)" }}>
          订单 #{orderId} 不存在或无权访问
        </div></div>
      </div>
    );
  }

  return (
    <div>
      <Link to={backTo} style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "var(--color-neutral-500)", fontSize: 13, textDecoration: "none", marginBottom: 12 }}>
        <ArrowLeft size={14} /> 返回订单列表
      </Link>

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 18, flexWrap: "wrap" }}>
        <FileText style={{ width: 22, height: 22, color: "var(--color-primary)" }} />
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>订单 #{order.id}</h1>
        <span className={STATUS_BADGES[order.status]} style={{ fontSize: 12 }}>{STATUS_LABELS[order.status]}</span>
        <span className="ds-badge ds-badge-blue" style={{ fontSize: 11 }}>{order.package_label}</span>
      </div>

      <OrderInfoCard order={order} />
      <TimelineCard order={order} />
      {order.notes && <NotesCard notes={order.notes} />}
      <DocumentsCard order={order} canUpload={actor === "lawyer" && order.status === "in_service"} />

      {actor === "firm_admin" && order.status === "dispatched" && (
        <AssignLawyerCard order={order} />
      )}
      {actor === "lawyer" && order.status === "in_service" && (
        <CompleteCard order={order} />
      )}
      {actor === "tenant_legal" && (
        <div className="ds-card" style={{ marginTop: 16 }}>
          <div className="card-body" style={{ padding: 14, fontSize: 13, color: "var(--color-neutral-600)", lineHeight: 1.7, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 240 }}>
              <strong>物业法务对接人视角</strong>：可查看完整案件背景（通话记录 / 工单 / 时间线 / 欠费理由），辅助判断是否需要法务介入。
            </div>
            <Link to={`/supervisor/cases/${order.case_id}`} className="ds-btn ds-btn-secondary ds-btn-sm">
              查看完整案件 →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

function OrderInfoCard({ order }: { order: LegalOrderDTO }) {
  return (
    <div className="ds-card" style={{ marginBottom: 16 }}>
      <div className="card-body" style={{ padding: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>订单信息</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px 24px" }}>
          <Field label="关联案件" value={`#${order.case_id} · ${order.case_owner ?? "—"} / ${order.case_building ?? ""}`} />
          <Field label="物业租户" value={order.tenant_name ?? "—"} />
          <Field label="欠费金额" value={
            order.case_amount === null
              ? <span style={{ color: "var(--color-neutral-400)" }}>—</span>
              : <span style={{ fontWeight: 600 }}>¥{order.case_amount.toLocaleString("zh-CN")}{order.case_months_overdue ? ` · 欠 ${order.case_months_overdue} 月` : ""}</span>
          } />
          <Field label="服务包" value={order.package_label} />
          <Field label="律所" value={order.law_firm_name ?? <span style={{ color: "var(--color-neutral-400)" }}>未派</span>} />
          <Field label="承办律师" value={order.lawyer_name ?? <span style={{ color: "var(--color-neutral-400)" }}>未分</span>} />
          <Field label="报价" value={<span style={{ fontWeight: 600 }}>¥{order.price_quoted.toLocaleString("zh-CN")}</span>} />
          <Field label="创建人" value={order.created_by ?? "—"} />
          <Field label="催收摘要" value={<span style={{ fontSize: 12 }}>{order.timeline_summary ?? "—"}</span>} />
        </div>
      </div>
    </div>
  );
}

function TimelineCard({ order }: { order: LegalOrderDTO }) {
  return (
    <div className="ds-card" style={{ marginBottom: 16 }}>
      <div className="card-body" style={{ padding: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>状态时间线</div>
        <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: 13 }}>
          <TimelineItem label="订单创建" time={order.created_at} done />
          <TimelineItem label="律所派单" time={order.dispatched_at} done={!!order.dispatched_at} />
          <TimelineItem label="律师接单" time={order.in_service_at} done={!!order.in_service_at} />
          <TimelineItem label="服务完成" time={order.completed_at} done={!!order.completed_at} />
        </ul>
      </div>
    </div>
  );
}

function NotesCard({ notes }: { notes: string }) {
  return (
    <div className="ds-card" style={{ marginBottom: 16 }}>
      <div className="card-body" style={{ padding: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>备注 / 处理建议</div>
        <div style={{ fontSize: 13, color: "var(--color-neutral-700)", whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{notes}</div>
      </div>
    </div>
  );
}

function DocumentsCard({ order, canUpload }: { order: LegalOrderDTO; canUpload: boolean }) {
  const [uploadOpen, setUploadOpen] = useState(false);
  return (
    <div className="ds-card" style={{ marginBottom: 16 }}>
      <div className="card-body" style={{ padding: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>文书 / 材料（{order.docs.length}）</div>
          {canUpload && (
            <button type="button" className="ds-btn ds-btn-primary ds-btn-sm" onClick={() => setUploadOpen(true)}>
              <Upload size={12} /> 上传文书
            </button>
          )}
        </div>
        {order.docs.length === 0 ? (
          <div style={{ fontSize: 12, color: "var(--color-neutral-400)", padding: 8 }}>暂无文书</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {order.docs.map((d) => (
              <div key={d.id} style={{ display: "flex", alignItems: "center", padding: 10, border: "1px solid #e5e7eb", borderRadius: 6, gap: 10 }}>
                <FileText size={14} style={{ color: "var(--color-primary)", flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{d.doc_label} · {d.filename}</div>
                  <div style={{ fontSize: 11, color: "var(--color-neutral-500)" }}>{d.uploaded_by ?? "—"} · {d.uploaded_at?.replace("T", " ").slice(0, 19) ?? "—"}</div>
                </div>
                <a
                  href={d.url}
                  className="ds-btn ds-btn-ghost ds-btn-sm"
                  onClick={(e) => { e.preventDefault(); alert("文书下载需对接 MinIO 签名 URL（v1.7 实装）"); }}
                >下载</a>
              </div>
            ))}
          </div>
        )}
      </div>
      {uploadOpen && <UploadModal orderId={order.id} onClose={() => setUploadOpen(false)} />}
    </div>
  );
}

function UploadModal({ orderId, onClose }: { orderId: number; onClose: () => void }) {
  const [docType, setDocType] = useState<DocType>("lawyer_letter");
  const [filename, setFilename] = useState("");
  const { uploadDoc, isPending } = useUploadDocument();
  function submit() {
    if (!filename.trim()) return alert("请填写文件名");
    uploadDoc(orderId, {
      doc_type: docType,
      filename: filename.trim(),
    }, { onSuccess: onClose });
  }
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }} onClick={onClose}>
      <div style={{ background: "white", borderRadius: 8, width: 460, maxWidth: "92%" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ padding: 16, borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between" }}>
          <span style={{ fontWeight: 600 }}>上传文书</span>
          <button type="button" onClick={onClose} style={{ border: "none", background: "transparent", cursor: "pointer" }}><X size={18} /></button>
        </div>
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="form-group">
            <label className="form-label">文书类型</label>
            <select className="form-control" value={docType} onChange={(e) => setDocType(e.target.value as DocType)}>
              {Object.entries(DOC_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">文件名</label>
            <input type="text" className="form-control" value={filename} onChange={(e) => setFilename(e.target.value)} placeholder="例：业主姓名_律师函_20260508.pdf" />
          </div>
          <div style={{ background: "#fffbeb", padding: 10, borderRadius: 6, fontSize: 12, color: "#78350f" }}>
            ⚠ 当前仅记录元数据；实际文件上传走 MinIO 签名 URL（v1.7 实装）。
          </div>
        </div>
        <div style={{ padding: 16, borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button type="button" className="ds-btn ds-btn-secondary" onClick={onClose} disabled={isPending}>取消</button>
          <button type="button" className="ds-btn ds-btn-primary" onClick={submit} disabled={isPending}>
            {isPending ? "提交中…" : "提交"}
          </button>
        </div>
      </div>
    </div>
  );
}

function AssignLawyerCard({ order }: { order: LegalOrderDTO }) {
  const [lawyerId, setLawyerId] = useState("");
  const { lawyers, isLoading } = useLawyersInMyFirm();
  const { assignLawyer, isPending } = useAssignLawyer();
  function submit() {
    if (!lawyerId) return;
    const lawyer = lawyers.find((l) => l.id === Number(lawyerId));
    if (!lawyer) return;
    assignLawyer(order.id, lawyer.id, {
      onSuccess: () => alert(`已分配给 ${lawyer.name}，订单状态变更为「服务中」`),
    });
  }
  return (
    <div className="ds-card" style={{ marginBottom: 16, borderLeft: "3px solid var(--color-primary)" }}>
      <div className="card-body" style={{ padding: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>律所内部分配律师</div>
        <p style={{ fontSize: 12, color: "var(--color-neutral-600)", marginBottom: 10 }}>
          订单已派到本所（{order.law_firm_name ?? "—"}），请从本所律师中选择承办人。承办律师收到通知后即可起草文书。
        </p>
        <div style={{ display: "flex", gap: 8 }}>
          <div style={{ flex: 1 }}>
            <SearchableSelect
              value={lawyerId}
              onChange={(v) => setLawyerId(String(v))}
              disabled={isLoading || isPending}
              placeholder={isLoading ? "加载本所律师…" : "请选择本所律师"}
              options={lawyers.map((l) => ({
                value: String(l.id),
                label: `${l.name}${l.specialties.length ? `（专长:${l.specialties.join("、")}）` : ""}`,
              }))}
            />
          </div>
          <button type="button" className="ds-btn ds-btn-primary" disabled={!lawyerId || isPending} onClick={submit}>
            {isPending ? "分配中…" : "确认分配"}
          </button>
        </div>
      </div>
    </div>
  );
}

function CompleteCard({ order }: { order: LegalOrderDTO }) {
  const { completeOrder, isPending } = useCompleteOrder();
  function submit() {
    if (order.docs.length === 0) {
      if (!confirm("当前订单尚未上传任何文书，确认完成？")) return;
    }
    completeOrder(order.id, {
      onSuccess: () => alert(`订单 #${order.id} 已标记完成`),
    });
  }
  return (
    <div className="ds-card" style={{ marginBottom: 16, borderLeft: "3px solid var(--color-success)" }}>
      <div className="card-body" style={{ padding: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>完结订单</div>
        <p style={{ fontSize: 12, color: "var(--color-neutral-600)", marginBottom: 10, lineHeight: 1.6 }}>
          确认服务已交付（文书已上传 / 调解纪要已录入 / 立案号已回填），点击下方按钮完结订单。
        </p>
        <button type="button" className="ds-btn ds-btn-primary" onClick={submit} disabled={isPending}>
          {isPending ? "处理中…" : "标记完成"}
        </button>
      </div>
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

function TimelineItem({ label, time, done }: { label: string; time: string | null; done: boolean }) {
  const display = time ? time.replace("T", " ").slice(0, 19) : "—";
  return (
    <li style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0" }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: done ? "var(--color-success)" : "var(--color-neutral-300)", flexShrink: 0 }} />
      <span style={{ fontWeight: done ? 500 : 400, color: done ? "#1f2937" : "var(--color-neutral-400)" }}>{label}</span>
      <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--color-neutral-500)" }}>{display}</span>
    </li>
  );
}
