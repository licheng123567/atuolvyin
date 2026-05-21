// 督导班次 / 排班 — v1.6 接后端持久化
import { useCustom, useCustomMutation, useInvalidate } from "@refinedev/core";
import { Calendar, Clock, Crown, Lock, UserCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { HelpPanel } from "../../../components/ui/HelpPanel";
import { SearchableSelect } from "../../../components/ui/SearchableSelect";

interface ShiftRow {
  date: string;
  morning: string;
  afternoon: string;
  evening: string;
}

type Slot = "morning" | "afternoon" | "evening";

interface ShiftsResp {
  tenant_id: number;
  is_shift_lead: boolean;
  current_user_name: string;
  supervisors: string[];
  shifts: ShiftRow[];
}

function slotLabel(slot: Slot): string {
  return slot === "morning" ? "上午班" : slot === "afternoon" ? "下午班" : "晚间班";
}

export function SupervisorShiftsPage() {
  const { query } = useCustom<ShiftsResp>({
    url: "supervisor/shifts",
    method: "get",
  });
  const data = query.data?.data;
  const [draft, setDraft] = useState<ShiftRow[] | null>(null);
  const [swapTarget, setSwapTarget] = useState<{ date: string; slot: Slot; current: string } | null>(null);
  const today = new Date().toISOString().slice(0, 10);
  const invalidate = useInvalidate();

  const { mutate: saveShifts, mutation: saveMut } = useCustomMutation();
  const { mutate: submitSwap, mutation: swapMut } = useCustomMutation();

  // 当后端 shifts 加载完成时，初始化 draft
  useEffect(() => {
    if (data && draft === null) setDraft(data.shifts);
  }, [data, draft]);

  if (query.isLoading) {
    return <div style={{ padding: 24, color: "var(--color-neutral-400)" }}>加载排班…</div>;
  }
  if (!data) {
    return <div style={{ padding: 24, color: "var(--color-danger)" }}>加载失败</div>;
  }

  const currentName = data.current_user_name;
  const isLead = data.is_shift_lead;
  const supervisors = data.supervisors;
  const dataShifts = data.shifts;
  const shifts = draft ?? dataShifts;
  const dirty = JSON.stringify(shifts) !== JSON.stringify(dataShifts);

  const currentHour = new Date().getHours();
  const currentSlot: Slot = currentHour < 12 ? "morning" : currentHour < 18 ? "afternoon" : "evening";
  const todayShift = shifts.find((s) => s.date === today);
  const currentDuty = todayShift ? todayShift[currentSlot] : "—";

  function update(date: string, slot: Slot, value: string) {
    setDraft((prev) => (prev ?? dataShifts).map((s) => s.date === date ? { ...s, [slot]: value } : s));
  }

  function save() {
    saveShifts(
      { url: "supervisor/shifts", method: "post", values: { shifts } },
      {
        onSuccess: () => {
          invalidate({ resource: "supervisor/shifts", invalidates: ["all"] });
          alert("排班已保存");
        },
        onError: (e) => {
          const detail = (e as { response?: { data?: { detail?: { message?: string } } } })?.response?.data?.detail;
          alert(detail?.message ?? "保存失败");
        },
      },
    );
  }

  function doSwap(target: typeof swapTarget, swapWith: string) {
    if (!target) return;
    submitSwap(
      {
        url: "supervisor/shifts/swap-request",
        method: "post",
        values: { date: target.date, slot: target.slot, swap_with: swapWith },
      },
      {
        onSuccess: () => {
          alert(`已向 ${swapWith} 发送调班申请：${target.date} ${slotLabel(target.slot)}`);
          setSwapTarget(null);
        },
        onError: (e) => {
          const detail = (e as { response?: { data?: { detail?: { message?: string } } } })?.response?.data?.detail;
          alert(detail?.message ?? "提交失败");
        },
      },
    );
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">值班排班</div>
          <div className="page-subtitle">多督导轮值时定 schedule，风控事件 / 升级案件自动派给当前值班督导</div>
        </div>
        {isLead && dirty && (
          <button type="button" className="ds-btn ds-btn-primary" onClick={save} disabled={saveMut.isPending}>
            {saveMut.isPending ? "保存中…" : "保存修改"}
          </button>
        )}
      </div>

      <HelpPanel
        tone="info"
        dismissKey="/supervisor/shifts"
        title="排班权责"
        bullets={[
          <><strong>组长</strong>：唯一可编辑全员排班的督导（物业管理员标记 user_account.preferences.is_shift_lead = true）</>,
          <><strong>普通督导</strong>：不能编辑别人的格子；可对自己已排的班次发起「调班申请」（顶班人在小程序确认后生效）</>,
          <><strong>物业管理员</strong>：只读 + 审计（仅在出现空班次告警时介入）</>,
          <><strong>三时段轮值</strong>：上午 9-12 / 下午 13-18 / 晚间 18-21（晚 21 后业主电话不打，无需值班）</>,
          <><strong>自动路由</strong>：风控告警 / 升级案件 / 承诺催付到期 都按当前时段值班人派单；非值班督导 App 不响</>,
        ]}
        footer={
          <>
            📌 当前角色 <strong>{currentName}</strong>{isLead ? "（组长，可编辑全员）" : "（普通督导，仅可对自己的格子发起调班申请）"}。
          </>
        }
      />

      <div className="status-bar">
        <div className="status-bar-item" style={{ color: "var(--color-success)" }}>
          <UserCheck className="w-4 h-4" /> 当前值班 <strong>{currentDuty || "—"}</strong>（{slotLabel(currentSlot)}）
        </div>
        <div className="status-bar-item">
          <Calendar className="w-4 h-4" /> 今日 <strong>{today}</strong>
        </div>
        <div className="status-bar-item">
          <Clock className="w-4 h-4" /> 现在 <strong>{String(new Date().getHours()).padStart(2, "0")}:{String(new Date().getMinutes()).padStart(2, "0")}</strong>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>日期</th>
              <th>上午班 09:00-12:00</th>
              <th>下午班 13:00-18:00</th>
              <th>晚间班 18:00-21:00</th>
            </tr>
          </thead>
          <tbody>
            {shifts.map((s) => (
              <tr key={s.date} style={s.date === today ? { background: "#eff6ff" } : {}}>
                <td>
                  <strong>{s.date}</strong>
                  {s.date === today && <span className="ds-badge ds-badge-blue" style={{ fontSize: 10, marginLeft: 6 }}>今日</span>}
                </td>
                {(["morning", "afternoon", "evening"] as const).map((slot) => {
                  const occupant = s[slot];
                  const isMine = occupant === currentName;
                  if (isLead) {
                    return (
                      <td key={slot}>
                        <SearchableSelect
                          value={occupant}
                          onChange={(v) => update(s.date, slot, String(v))}
                          placeholder="未排班"
                          options={supervisors.map((sv) => ({ value: sv, label: sv }))}
                          style={{ width: "100%" }}
                        />
                      </td>
                    );
                  }
                  return (
                    <td key={slot}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}>
                        <span style={{ fontSize: 13, color: isMine ? "var(--color-primary)" : "#374151", fontWeight: isMine ? 600 : 400 }}>
                          {occupant || <span style={{ color: "var(--color-neutral-400)" }}>未排班</span>}
                          {isMine && <span style={{ fontSize: 10, marginLeft: 4, color: "var(--color-primary)" }}>· 我</span>}
                        </span>
                        {isMine ? (
                          <button
                            type="button"
                            className="ds-btn ds-btn-ghost ds-btn-sm"
                            style={{ fontSize: 11, padding: "2px 6px" }}
                            onClick={() => setSwapTarget({ date: s.date, slot, current: occupant })}
                          >
                            调班
                          </button>
                        ) : (
                          <Lock size={12} style={{ color: "var(--color-neutral-300)" }} />
                        )}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: 12, fontSize: 12, color: "var(--color-neutral-500)", display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
        <Crown size={12} style={{ color: "var(--color-warning)" }} />
        v1.7：每周日 21:00 系统按公平算法（轮值 + 上周缺勤平衡）生成下周草稿；空班次自动通知 admin。
      </div>

      {swapTarget && (
        <SwapModal
          target={swapTarget}
          supervisors={supervisors}
          onClose={() => setSwapTarget(null)}
          onConfirm={(swapWith) => doSwap(swapTarget, swapWith)}
          isPending={swapMut.isPending}
        />
      )}
    </div>
  );
}

function SwapModal({ target, supervisors, onClose, onConfirm, isPending }: {
  target: { date: string; slot: Slot; current: string };
  supervisors: string[];
  onClose: () => void;
  onConfirm: (agent: string) => void;
  isPending: boolean;
}) {
  const [agent, setAgent] = useState("");
  const candidates = supervisors.filter((n) => n !== target.current);
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }} onClick={onClose}>
      <div style={{ background: "white", borderRadius: 8, width: 440, maxWidth: "92%" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ padding: 16, borderBottom: "1px solid #e5e7eb" }}>
          <span style={{ fontWeight: 600 }}>调班申请：{target.date} · {slotLabel(target.slot)}</span>
        </div>
        <div style={{ padding: 16 }}>
          <p style={{ fontSize: 13, color: "#374151", marginBottom: 12, lineHeight: 1.7 }}>
            申请把这班次顶给：
          </p>
          <SearchableSelect
            value={agent}
            onChange={(v) => setAgent(String(v))}
            placeholder="请选择顶班人"
            options={candidates.map((n) => ({ value: n, label: n }))}
          />
          <div style={{ background: "#fffbeb", padding: 10, borderRadius: 6, fontSize: 12, color: "#78350f", marginTop: 12 }}>
            ⚠ 顶班人需在小程序点「同意」才生效；本周内调班自动通知物业 admin。
          </div>
        </div>
        <div style={{ padding: 16, borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button type="button" className="ds-btn ds-btn-secondary" onClick={onClose} disabled={isPending}>取消</button>
          <button type="button" className="ds-btn ds-btn-primary" disabled={!agent || isPending} onClick={() => onConfirm(agent)}>
            {isPending ? "提交中…" : "提交申请"}
          </button>
        </div>
      </div>
    </div>
  );
}
