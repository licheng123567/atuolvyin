// 话术反馈 — 1:1 还原 ui/supervisor.html#sv-scripts
// v1.5.7 — mock 表格 + 采用率 bar + 督导标注 + 查看完整详情
import { Eye, Headphones, X } from "lucide-react";
import { useState } from "react";

interface ScriptItem {
  id: number;
  title: string;
  excerpt: string;
  full_content: string;
  notes: string;
  intent: string;
  intent_badge: string;
  scene: string;             // 通话场景
  adoption: number;
  good_count: number;        // 好评次数
  bad_count: number;         // 差评次数
  used_count: number;        // 总推送次数
  label: "good" | "bad" | "pending";
  source: "platform" | "tenant";  // 来源
  recent_uses: { call_id: number; agent: string; date: string; was_adopted: boolean }[];
}

const MOCK_SCRIPTS: ScriptItem[] = [
  {
    id: 1, title: "经济困难·分期方案",
    excerpt: "\"理解您的困难，我们可以为您申请 3 个月分期缴费方案，每月只需还 ¥820，不影响您的...",
    full_content: "理解您的困难，我们可以为您申请 3 个月分期缴费方案，每月只需还 ¥820，不影响您的征信记录。这个方案需要您签一份补充协议，我们可以约时间送上门，或者您可以直接在小程序上签电子协议，您看哪种方式方便？",
    notes: "适用于明确表示「经济困难 + 短期没钱」的业主，强调「不影响征信」是关键 trigger。",
    intent: "经济困难", intent_badge: "ds-badge ds-badge-orange", scene: "异议处理",
    adoption: 86, good_count: 14, bad_count: 1, used_count: 86, label: "good", source: "tenant",
    recent_uses: [
      { call_id: 1024, agent: "李小红", date: "2026-05-06", was_adopted: true },
      { call_id: 1019, agent: "王芳芳", date: "2026-05-05", was_adopted: true },
      { call_id: 1014, agent: "张建华", date: "2026-05-04", was_adopted: false },
    ],
  },
  {
    id: 2, title: "房屋质量·工单分账",
    excerpt: "\"您好，房屋质量问题已提交工单，预计 5 个工作日处理。物业费与维修服务是分开的账目...",
    full_content: "您好，房屋质量问题已提交工单，预计 5 个工作日处理。物业费与维修服务是分开的账目，物业费是公共服务费（电梯、保洁、绿化、安保）。维修问题我们今天给您工单号，您随时可以查询进度。物业费这块我们今天还是先按合同缴清，可以吗？",
    notes: "把维修和物业费明确分开，给业主一个看得见的「工单号」是关键。",
    intent: "房屋质量", intent_badge: "ds-badge ds-badge-blue", scene: "异议处理",
    adoption: 72, good_count: 9, bad_count: 2, used_count: 64, label: "good", source: "tenant",
    recent_uses: [
      { call_id: 1010, agent: "王芳芳", date: "2026-05-05", was_adopted: true },
      { call_id: 1005, agent: "陈明远", date: "2026-05-03", was_adopted: false },
    ],
  },
  {
    id: 3, title: "拒缴·法律威慑（强力版）",
    excerpt: "\"您的物业费已逾期超过 6 个月，如仍未缴清我们将不得不采取相应法律措施，请您尽快处...",
    full_content: "您的物业费已逾期超过 6 个月，如仍未缴清我们将不得不采取相应法律措施，请您尽快处理。我们已经联系律所，最快下周就会发律师函到您家里。建议您今天先缴 30%，剩下我们可以分期，避免事情升级到法院。",
    notes: "⚠ 高风险话术：使用「法律措施」「律师函」可能引发投诉。务必慎用，建议改用平和版。",
    intent: "拒缴", intent_badge: "ds-badge ds-badge-red", scene: "异议处理",
    adoption: 34, good_count: 1, bad_count: 8, used_count: 21, label: "bad", source: "platform",
    recent_uses: [
      { call_id: 996, agent: "李小红", date: "2026-05-02", was_adopted: false },
      { call_id: 991, agent: "陈明远", date: "2026-05-01", was_adopted: false },
    ],
  },
  {
    id: 4, title: "暂缓·下周回访承诺",
    excerpt: "\"感谢您的理解，我们已为您备注下周一上午 10 点回访，如有变化可随时联系我们客服热线...",
    full_content: "感谢您的理解，我们已为您备注下周一上午 10 点回访，如有变化可随时联系我们客服热线 400-xxx-xxxx。回访时希望我们能为您提供具体的还款方案，您看可以吗？",
    notes: "适用于业主表示「下周再说」的暂缓型对话，关键是「主动定时间」。",
    intent: "暂缓", intent_badge: "ds-badge ds-badge-gray", scene: "承诺确认",
    adoption: 79, good_count: 6, bad_count: 0, used_count: 38, label: "pending", source: "tenant",
    recent_uses: [
      { call_id: 988, agent: "刘晓娟", date: "2026-05-01", was_adopted: true },
    ],
  },
  {
    id: 5, title: "拒缴·违约金提醒",
    excerpt: "\"根据合同第 9 条规定，逾期物业费将产生每日万分之五的违约金，当前累计违约金 ¥124...",
    full_content: "根据合同第 9 条规定，逾期物业费将产生每日万分之五的违约金，当前累计违约金 ¥124.50。如果今天缴清，违约金可以申请减免；如果继续拖延，每天还会增加约 ¥3。您看是今天处理还是明天？",
    notes: "用具体数字（¥124.50 / 每天 ¥3）让违约成本可视化。",
    intent: "拒缴", intent_badge: "ds-badge ds-badge-red", scene: "异议处理",
    adoption: 45, good_count: 3, bad_count: 4, used_count: 28, label: "pending", source: "platform",
    recent_uses: [
      { call_id: 985, agent: "张建华", date: "2026-04-30", was_adopted: false },
    ],
  },
  {
    id: 6, title: "情绪激动·共情转换",
    excerpt: "\"我完全理解您的心情，如果方便的话，能告诉我您最近遇到的主要困难吗？我们可以一起...",
    full_content: "我完全理解您的心情，如果方便的话，能告诉我您最近遇到的主要困难吗？我们可以一起想办法。如果是经济原因我们可以分期，如果是服务问题我们可以一起反馈。您今天愿意聊一聊吗？",
    notes: "高情绪场景的「破冰」话术，核心是先共情再问困难原因。极少配合数字使用。",
    intent: "情绪激动", intent_badge: "ds-badge ds-badge-orange", scene: "异议处理",
    adoption: 91, good_count: 18, bad_count: 0, used_count: 92, label: "good", source: "tenant",
    recent_uses: [
      { call_id: 1027, agent: "刘晓娟", date: "2026-05-07", was_adopted: true },
    ],
  },
];

export function SupervisorScriptLabelsPage() {
  const [scripts, setScripts] = useState<ScriptItem[]>(MOCK_SCRIPTS);
  const [commenting, setCommenting] = useState<ScriptItem | null>(null);
  const [viewing, setViewing] = useState<ScriptItem | null>(null);

  function quickLabel(id: number, label: "good" | "bad") {
    if (label === "bad") {
      const s = scripts.find((x) => x.id === id);
      if (s) setCommenting({ ...s, label });
      return;
    }
    setScripts((prev) => prev.map((x) => (x.id === id ? { ...x, label: "good" } : x)));
  }

  function submitComment(label: "good" | "bad", _note: string) {
    if (commenting) {
      setScripts((prev) => prev.map((x) => (x.id === commenting.id ? { ...x, label } : x)));
    }
    setCommenting(null);
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">话术反馈</div>
          <div className="page-subtitle">对 AI 推送话术进行标注与评价，优化推荐策略</div>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>话术内容</th>
              <th>异议类型</th>
              <th>组内采用率</th>
              <th>督导标注</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {scripts.map((s) => (
              <tr key={s.id}>
                <td className="script-excerpt" title={s.excerpt}>{s.excerpt}</td>
                <td><span className={s.intent_badge}>{s.intent}</span></td>
                <td>
                  <div className="adopt-bar">
                    <div className="adopt-bg">
                      <div
                        className="adopt-fill"
                        style={{
                          width: `${s.adoption}%`,
                          background: s.adoption < 40 ? "var(--color-danger)" : undefined,
                        }}
                      />
                    </div>
                    <span style={{ color: s.adoption < 40 ? "var(--color-danger)" : s.adoption >= 85 ? "var(--color-success)" : undefined }}>
                      {s.adoption}%
                    </span>
                  </div>
                </td>
                <td>
                  {s.label === "good" && <span className="ds-badge ds-badge-green">好话术</span>}
                  {s.label === "bad" && <span className="ds-badge ds-badge-red">差话术</span>}
                  {s.label === "pending" && <span className="ds-badge ds-badge-gray">待标注</span>}
                </td>
                <td>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" onClick={() => setViewing(s)} title="查看完整话术">
                      <Eye className="w-3 h-3" /> 详情
                    </button>
                    {s.label === "pending" ? (
                      <>
                        <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" onClick={() => quickLabel(s.id, "good")}>好话术</button>
                        <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" onClick={() => setCommenting(s)}>差话术</button>
                      </>
                    ) : (
                      <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" onClick={() => setCommenting(s)}>写点评</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {commenting && <CommentModal initial={commenting.label} onClose={() => setCommenting(null)} onSubmit={submitComment} />}
      {viewing && <ScriptDetailModal script={viewing} onClose={() => setViewing(null)} />}
    </div>
  );
}

function ScriptDetailModal({ script, onClose }: { script: ScriptItem; onClose: () => void }) {
  const sourceBadge =
    script.source === "platform"
      ? { className: "ds-badge ds-badge-blue", label: "平台预置" }
      : { className: "ds-badge ds-badge-green", label: "本租户自定义" };
  const labelBadge =
    script.label === "good"
      ? { className: "ds-badge ds-badge-green", label: "好话术" }
      : script.label === "bad"
        ? { className: "ds-badge ds-badge-red", label: "差话术" }
        : { className: "ds-badge ds-badge-gray", label: "待标注" };

  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}
      onClick={onClose}
    >
      <div
        style={{ background: "white", borderRadius: 8, width: 640, maxWidth: "92%", maxHeight: "88vh", display: "flex", flexDirection: "column" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ padding: "14px 16px", borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontWeight: 600, fontSize: 15 }}>{script.title}</span>
            <span className={sourceBadge.className} style={{ fontSize: 11 }}>{sourceBadge.label}</span>
            <span className={labelBadge.className} style={{ fontSize: 11 }}>{labelBadge.label}</span>
          </div>
          <button type="button" onClick={onClose} style={{ border: "none", background: "transparent", cursor: "pointer" }}><X size={18} /></button>
        </div>

        <div style={{ padding: 16, overflowY: "auto", flex: 1 }}>
          {/* badges 行：场景 + 异议类型 */}
          <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
            <span className="ds-badge ds-badge-gray" style={{ fontSize: 11 }}>场景：{script.scene}</span>
            <span className={script.intent_badge} style={{ fontSize: 11 }}>{script.intent}</span>
          </div>

          {/* 完整正文 */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 6 }}>完整话术</div>
            <div style={{ fontSize: 13.5, color: "#1f2937", lineHeight: 1.7, padding: 12, background: "#f9fafb", borderRadius: 6, whiteSpace: "pre-wrap" }}>
              {script.full_content}
            </div>
          </div>

          {/* 督导备注 */}
          {script.notes && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 6 }}>督导备注</div>
              <div style={{ fontSize: 12.5, color: "#78350f", lineHeight: 1.7, padding: 10, background: "#fffbeb", border: "1px solid #fde68a", borderRadius: 6 }}>
                {script.notes}
              </div>
            </div>
          )}

          {/* 三段统计 */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 14 }}>
            <StatBox label="总推送" value={script.used_count} color="var(--color-neutral-700)" />
            <StatBox label="督导好评" value={script.good_count} color="var(--color-success)" />
            <StatBox label="督导差评" value={script.bad_count} color="var(--color-danger)" />
          </div>

          {/* 最近使用 */}
          <div>
            <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 6 }}>最近使用</div>
            {script.recent_uses.length === 0 ? (
              <div style={{ fontSize: 12, color: "var(--color-neutral-400)", padding: 8 }}>暂无</div>
            ) : (
              <div style={{ border: "1px solid #e5e7eb", borderRadius: 6, overflow: "hidden" }}>
                <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
                  <thead style={{ background: "#f9fafb" }}>
                    <tr>
                      <th style={{ padding: "6px 8px", textAlign: "left", fontWeight: 500, color: "#6b7280" }}>通话</th>
                      <th style={{ padding: "6px 8px", textAlign: "left", fontWeight: 500, color: "#6b7280" }}>催收员</th>
                      <th style={{ padding: "6px 8px", textAlign: "left", fontWeight: 500, color: "#6b7280" }}>日期</th>
                      <th style={{ padding: "6px 8px", textAlign: "center", fontWeight: 500, color: "#6b7280" }}>是否采用</th>
                      <th style={{ padding: "6px 8px", textAlign: "center", fontWeight: 500, color: "#6b7280" }}>录音</th>
                    </tr>
                  </thead>
                  <tbody>
                    {script.recent_uses.map((u, i) => (
                      <tr key={u.call_id} style={{ borderTop: i > 0 ? "1px solid #f3f4f6" : "none" }}>
                        <td style={{ padding: "6px 8px", color: "var(--color-primary)" }}>#{u.call_id}</td>
                        <td style={{ padding: "6px 8px" }}>{u.agent}</td>
                        <td style={{ padding: "6px 8px", color: "#6b7280" }}>{u.date}</td>
                        <td style={{ padding: "6px 8px", textAlign: "center", color: u.was_adopted ? "var(--color-success)" : "var(--color-neutral-400)" }}>
                          {u.was_adopted ? "✓" : "✗"}
                        </td>
                        <td style={{ padding: "6px 8px", textAlign: "center" }}>
                          <button type="button" style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--color-primary)", display: "inline-flex", alignItems: "center", gap: 2 }}>
                            <Headphones size={12} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        <div style={{ padding: 12, borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end" }}>
          <button type="button" className="ds-btn ds-btn-secondary" onClick={onClose}>关闭</button>
        </div>
      </div>
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ padding: 10, border: "1px solid #e5e7eb", borderRadius: 6, textAlign: "center" }}>
      <div style={{ fontSize: 11, color: "var(--color-neutral-500)", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 600, color }}>{value}</div>
    </div>
  );
}

function CommentModal({ initial, onClose, onSubmit }: { initial: "good" | "bad" | "pending"; onClose: () => void; onSubmit: (label: "good" | "bad", note: string) => void }) {
  const [label, setLabel] = useState<"good" | "bad">(initial === "bad" ? "bad" : "good");
  const [note, setNote] = useState("");

  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}
      onClick={onClose}
    >
      <div
        style={{ background: "white", borderRadius: 8, width: 460, maxWidth: "92%" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ padding: 16, borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontWeight: 600 }}>话术点评</span>
          <button type="button" onClick={onClose} style={{ border: "none", background: "transparent", cursor: "pointer" }}><X size={18} /></button>
        </div>
        <div style={{ padding: 16 }}>
          <div className="form-group">
            <label className="form-label">标注结果</label>
            <div style={{ display: "flex", gap: 14 }}>
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
                <input type="radio" name="script-tag" checked={label === "good"} onChange={() => setLabel("good")} /> 好话术
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
                <input type="radio" name="script-tag" checked={label === "bad"} onChange={() => setLabel("bad")} /> 差话术
              </label>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">点评内容</label>
            <textarea className="form-control" rows={4} placeholder="请填写具体点评意见，将反馈到话术优化模型..." value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
        </div>
        <div style={{ padding: 16, borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button type="button" className="ds-btn ds-btn-secondary" onClick={onClose}>取消</button>
          <button type="button" className="ds-btn ds-btn-primary" onClick={() => onSubmit(label, note)}>提交点评</button>
        </div>
      </div>
    </div>
  );
}
