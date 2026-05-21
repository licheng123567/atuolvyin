// v1.5 S18.4 — 全角色个人中心
import { useCustom, useCustomMutation } from "@refinedev/core";
import { Eye, EyeOff, Mail, Phone, Save, Shield, User } from "lucide-react";
import { useState } from "react";

interface MeOut {
  id: number;
  name: string;
  role: string;
  tenant_id: number | null;
  tenant_name: string | null;
  phone_masked: string;
  email: string | null;
  has_password: boolean;
  login_method: string;
}

interface LoginHistoryItem {
  device_type: string;
  created_at: string;
  updated_at: string;
}

// v0.5.6 — ROLE_LABELS 已迁出到 src/lib/roleLabel.ts;/me 当前用户视角,scope 不定 → any
import { roleLabelAny } from "../../lib/roleLabel";
const ROLE_LABELS = (r: string) => roleLabelAny(r);

export function MePage() {
  const { query: meQuery } = useCustom<MeOut>({ url: "me", method: "get" });
  const me = meQuery.data?.data;

  return (
    <div style={{ maxWidth: 720, padding: "16px 0" }}>
      <h1 className="page-title" style={{ marginBottom: 24 }}>
        我的账号
      </h1>

      {meQuery.isLoading && <div className="text-muted">加载中…</div>}
      {me && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <BasicInfoSection me={me} onChanged={() => meQuery.refetch()} />
          <SecuritySection me={me} onChanged={() => meQuery.refetch()} />
          <ContactSection me={me} onChanged={() => meQuery.refetch()} />
          <LoginHistorySection />
        </div>
      )}
    </div>
  );
}

// ─── 基本信息 ──────────────────────────────────────

function BasicInfoSection({
  me,
  onChanged,
}: {
  me: MeOut;
  onChanged: () => void;
}) {
  const [name, setName] = useState(me.name);
  const [editing, setEditing] = useState(false);
  const { mutate: update, mutation } = useCustomMutation();

  function save() {
    update(
      { url: "me", method: "patch", values: { name: name.trim() } },
      { onSuccess: () => { setEditing(false); onChanged(); } },
    );
  }

  return (
    <div className="ds-card">
      <div className="card-header">
        <span className="card-title">
          <User className="w-4 h-4" style={{ display: "inline", marginRight: 6, verticalAlign: "-3px" }} />
          基本信息
        </span>
      </div>
      <div className="card-body" style={{ display: "grid", gridTemplateColumns: "120px 1fr", rowGap: 14, columnGap: 16, alignItems: "center" }}>
        <span className="text-muted" style={{ fontSize: 13 }}>姓名</span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {editing ? (
            <>
              <input className="form-control" value={name} onChange={(e) => setName(e.target.value)} maxLength={50} style={{ maxWidth: 280 }} />
              <button type="button" className="ds-btn ds-btn-primary ds-btn-sm" disabled={mutation.isPending} onClick={save}>
                <Save className="w-3.5 h-3.5" />
                保存
              </button>
              <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" onClick={() => { setName(me.name); setEditing(false); }}>取消</button>
            </>
          ) : (
            <>
              <span>{me.name}</span>
              <button type="button" className="ds-btn ds-btn-ghost ds-btn-sm" onClick={() => setEditing(true)}>修改</button>
            </>
          )}
        </div>

        <span className="text-muted" style={{ fontSize: 13 }}>角色</span>
        <span>{ROLE_LABELS(me.role)}</span>

        <span className="text-muted" style={{ fontSize: 13 }}>所属</span>
        <span>{me.tenant_name ?? <span className="text-muted">—（平台账号）</span>}</span>

        <span className="text-muted" style={{ fontSize: 13 }}>登录偏好</span>
        <span style={{ fontSize: 13, color: "#6b7280" }}>
          {me.login_method === "otp" ? "手机验证码（未设密码）" : "账号密码"}
        </span>
      </div>
    </div>
  );
}

// ─── 安全 / 密码 ───────────────────────────────────

function SecuritySection({
  me,
  onChanged,
}: {
  me: MeOut;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [showOld, setShowOld] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const { mutate: setPwd, mutation } = useCustomMutation();

  function submit() {
    setError(null);
    if (newPwd.length < 8) {
      setError("新密码至少 8 位");
      return;
    }
    setPwd(
      {
        url: "me/password",
        method: "post",
        values: {
          current_password: me.has_password ? oldPwd : null,
          new_password: newPwd,
        },
      },
      {
        onSuccess: () => {
          setDone(true);
          setOldPwd("");
          setNewPwd("");
          onChanged();
        },
        onError: (e) => {
          const code = (e as { response?: { data?: { detail?: { code?: string; message?: string } } } }).response?.data?.detail;
          setError(code?.message ?? "设置失败，请重试");
        },
      },
    );
  }

  return (
    <div className="ds-card">
      <div className="card-header">
        <span className="card-title">
          <Shield className="w-4 h-4" style={{ display: "inline", marginRight: 6, verticalAlign: "-3px" }} />
          密码
        </span>
      </div>
      <div className="card-body">
        {!open ? (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 14 }}>
              {me.has_password ? "已设置密码" : "尚未设置密码（当前用 OTP 登录）"}
            </span>
            <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" onClick={() => { setOpen(true); setDone(false); }}>
              {me.has_password ? "修改密码" : "设置密码"}
            </button>
          </div>
        ) : done ? (
          <div style={{ color: "#057a55", fontSize: 14 }}>
            ✅ 密码已更新。下次登录可使用新密码。
            <button type="button" className="ds-btn ds-btn-ghost ds-btn-sm" style={{ marginLeft: 12 }} onClick={() => { setOpen(false); setDone(false); }}>关闭</button>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 400 }}>
            {me.has_password && (
              <div>
                <label className="form-label">当前密码</label>
                <div style={{ position: "relative" }}>
                  <input className="form-control" type={showOld ? "text" : "password"} value={oldPwd} onChange={(e) => setOldPwd(e.target.value)} />
                  <button type="button" onClick={() => setShowOld((v) => !v)} style={{ position: "absolute", right: 8, top: 8, border: "none", background: "transparent", cursor: "pointer", color: "#9ca3af" }}>
                    {showOld ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            )}
            <div>
              <label className="form-label">新密码（≥ 8 位）</label>
              <div style={{ position: "relative" }}>
                <input className="form-control" type={showNew ? "text" : "password"} value={newPwd} onChange={(e) => setNewPwd(e.target.value)} />
                <button type="button" onClick={() => setShowNew((v) => !v)} style={{ position: "absolute", right: 8, top: 8, border: "none", background: "transparent", cursor: "pointer", color: "#9ca3af" }}>
                  {showNew ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            {error && <div style={{ color: "#e02424", fontSize: 12 }}>{error}</div>}
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" className="ds-btn ds-btn-primary" disabled={mutation.isPending} onClick={submit}>
                {mutation.isPending ? "提交中…" : "保存"}
              </button>
              <button type="button" className="ds-btn ds-btn-secondary" onClick={() => { setOpen(false); setOldPwd(""); setNewPwd(""); setError(null); }}>取消</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── 联系方式（手机 + 邮箱）──────────────────────

function ContactSection({
  me,
  onChanged,
}: {
  me: MeOut;
  onChanged: () => void;
}) {
  const [phoneStep, setPhoneStep] = useState<0 | 1 | 2>(0); // 0=idle, 1=旧手机已发码, 2=新手机已发码
  const [oldOtp, setOldOtp] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [newOtp, setNewOtp] = useState("");
  const [phoneHint, setPhoneHint] = useState<string | null>(null);
  const [phoneErr, setPhoneErr] = useState<string | null>(null);
  const { mutate: phoneAction, mutation: phoneMutation } = useCustomMutation();

  // 邮箱换绑状态机：idle → form（输入新邮箱）→ verify-new（首次绑定，单 OTP）/ verify-both（已绑定，双 OTP）
  type EmailStep = "idle" | "form" | "verify-new" | "verify-both";
  const [emailStep, setEmailStep] = useState<EmailStep>("idle");
  const [newEmail, setNewEmail] = useState("");
  const [emailOldOtp, setEmailOldOtp] = useState("");
  const [emailNewOtp, setEmailNewOtp] = useState("");
  const [emailHint, setEmailHint] = useState<string | null>(null);
  const [emailErr, setEmailErr] = useState<string | null>(null);
  const [emailDone, setEmailDone] = useState(false);
  const { mutate: emailAction, mutation: emailMutation } = useCustomMutation();

  function startPhoneChange() {
    setPhoneErr(null);
    setPhoneHint(null);
    phoneAction(
      { url: "me/phone/change-request", method: "post", values: {} },
      {
        onSuccess: (resp) => {
          const data = (resp as { data?: { dev_code?: string } }).data;
          setPhoneStep(1);
          setPhoneHint(data?.dev_code ? `开发模式：旧手机验证码 ${data.dev_code}` : "已发送至当前手机，5 分钟内有效");
        },
        onError: () => setPhoneErr("发送失败，请稍后重试"),
      },
    );
  }

  function sendNewPhoneOtp() {
    setPhoneErr(null);
    if (!/^1[3-9]\d{9}$/.test(newPhone)) {
      setPhoneErr("新手机号格式无效");
      return;
    }
    phoneAction(
      { url: "me/phone/change-send-new", method: "post", values: { new_phone: newPhone } },
      {
        onSuccess: (resp) => {
          const data = (resp as { data?: { dev_code?: string } }).data;
          setPhoneStep(2);
          setPhoneHint(data?.dev_code ? `开发模式：新手机验证码 ${data.dev_code}` : "已发送至新手机，5 分钟内有效");
        },
        onError: (e) => {
          const code = (e as { response?: { data?: { detail?: { message?: string } } } }).response?.data?.detail?.message;
          setPhoneErr(code ?? "发送失败");
        },
      },
    );
  }

  function confirmPhoneChange() {
    setPhoneErr(null);
    phoneAction(
      {
        url: "me/phone/change-confirm",
        method: "post",
        values: { old_otp: oldOtp, new_phone: newPhone, new_otp: newOtp },
      },
      {
        onSuccess: () => {
          setPhoneStep(0);
          setOldOtp(""); setNewPhone(""); setNewOtp(""); setPhoneHint("✅ 手机号已更新");
          onChanged();
        },
        onError: (e) => {
          const code = (e as { response?: { data?: { detail?: { message?: string } } } }).response?.data?.detail?.message;
          setPhoneErr(code ?? "校验失败");
        },
      },
    );
  }

  function startEmailChange() {
    setEmailErr(null);
    setEmailHint(null);
    setEmailDone(false);
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(newEmail)) {
      setEmailErr("邮箱格式无效");
      return;
    }
    emailAction(
      { url: "me/email/change-request", method: "post", values: { new_email: newEmail } },
      {
        onSuccess: (resp) => {
          const data = (resp as { data?: { requires_old_otp?: boolean; dev_code_old?: string; dev_code_new?: string } }).data;
          const requiresOld = !!data?.requires_old_otp;
          setEmailStep(requiresOld ? "verify-both" : "verify-new");
          const hints: string[] = [];
          if (data?.dev_code_old) hints.push(`旧邮箱验证码 ${data.dev_code_old}`);
          if (data?.dev_code_new) hints.push(`新邮箱验证码 ${data.dev_code_new}`);
          setEmailHint(
            hints.length ? `开发模式：${hints.join("，")}` : "验证码已发送，5 分钟内有效",
          );
        },
        onError: (e) => {
          const msg = (e as { response?: { data?: { detail?: { message?: string } } } }).response?.data?.detail?.message;
          setEmailErr(msg ?? "发送失败");
        },
      },
    );
  }

  function confirmEmailChange() {
    setEmailErr(null);
    const values: Record<string, string> = { new_email: newEmail, new_otp: emailNewOtp };
    if (emailStep === "verify-both") values.old_otp = emailOldOtp;
    emailAction(
      { url: "me/email/change-confirm", method: "post", values },
      {
        onSuccess: () => {
          setEmailStep("idle");
          setNewEmail(""); setEmailOldOtp(""); setEmailNewOtp("");
          setEmailDone(true);
          setEmailHint(null);
          onChanged();
        },
        onError: (e) => {
          const msg = (e as { response?: { data?: { detail?: { message?: string } } } }).response?.data?.detail?.message;
          setEmailErr(msg ?? "校验失败");
        },
      },
    );
  }

  return (
    <div className="ds-card">
      <div className="card-header">
        <span className="card-title">联系方式</span>
      </div>
      <div className="card-body" style={{ display: "grid", gridTemplateColumns: "120px 1fr", rowGap: 16, columnGap: 16 }}>
        {/* 手机 */}
        <span className="text-muted" style={{ fontSize: 13 }}>
          <Phone className="w-3.5 h-3.5" style={{ display: "inline", marginRight: 4, verticalAlign: "-2px" }} />
          手机号
        </span>
        <div>
          {phoneStep === 0 && (
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span style={{ fontFamily: "monospace" }}>{me.phone_masked}</span>
              <button type="button" className="ds-btn ds-btn-ghost ds-btn-sm" onClick={startPhoneChange} disabled={phoneMutation.isPending}>换绑手机</button>
              {phoneHint && phoneHint.startsWith("✅") && <span style={{ color: "#057a55", fontSize: 12 }}>{phoneHint}</span>}
            </div>
          )}
          {phoneStep === 1 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8, maxWidth: 360 }}>
              {phoneHint && <span style={{ fontSize: 12, color: "#6b7280" }}>{phoneHint}</span>}
              <input className="form-control" placeholder="旧手机收到的验证码" value={oldOtp} onChange={(e) => setOldOtp(e.target.value.replace(/\D/g, ""))} maxLength={8} style={{ fontFamily: "monospace", letterSpacing: 4, textAlign: "center" }} />
              <input className="form-control" placeholder="新手机号 11 位" value={newPhone} onChange={(e) => setNewPhone(e.target.value)} maxLength={11} />
              <div style={{ display: "flex", gap: 8 }}>
                <button type="button" className="ds-btn ds-btn-primary ds-btn-sm" disabled={phoneMutation.isPending || !oldOtp || !newPhone} onClick={sendNewPhoneOtp}>发送新手机验证码</button>
                <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" onClick={() => { setPhoneStep(0); setPhoneHint(null); setPhoneErr(null); }}>取消</button>
              </div>
            </div>
          )}
          {phoneStep === 2 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8, maxWidth: 360 }}>
              {phoneHint && <span style={{ fontSize: 12, color: "#6b7280" }}>{phoneHint}</span>}
              <input className="form-control" placeholder="新手机收到的验证码" value={newOtp} onChange={(e) => setNewOtp(e.target.value.replace(/\D/g, ""))} maxLength={8} style={{ fontFamily: "monospace", letterSpacing: 4, textAlign: "center" }} />
              <div style={{ display: "flex", gap: 8 }}>
                <button type="button" className="ds-btn ds-btn-primary ds-btn-sm" disabled={phoneMutation.isPending || !newOtp} onClick={confirmPhoneChange}>确认换绑</button>
                <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" onClick={() => { setPhoneStep(0); setPhoneHint(null); setPhoneErr(null); }}>取消</button>
              </div>
            </div>
          )}
          {phoneErr && <span style={{ color: "#e02424", fontSize: 12, display: "block", marginTop: 4 }}>{phoneErr}</span>}
        </div>

        {/* 邮箱 */}
        <span className="text-muted" style={{ fontSize: 13 }}>
          <Mail className="w-3.5 h-3.5" style={{ display: "inline", marginRight: 4, verticalAlign: "-2px" }} />
          邮箱
        </span>
        <div>
          {emailStep === "idle" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8, maxWidth: 360 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span>{me.email ?? <span className="text-muted">未绑定</span>}</span>
                <button
                  type="button"
                  className="ds-btn ds-btn-ghost ds-btn-sm"
                  onClick={() => {
                    setNewEmail(""); setEmailErr(null); setEmailDone(false);
                    setEmailStep("form");
                  }}
                >
                  {me.email ? "换绑邮箱" : "绑定邮箱"}
                </button>
                {emailDone && <span style={{ color: "#057a55", fontSize: 12 }}>✅ 已更新</span>}
              </div>
            </div>
          )}
          {emailStep === "form" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8, maxWidth: 360 }}>
              <input
                className="form-control"
                type="email"
                placeholder="example@company.com"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value.toLowerCase())}
                maxLength={120}
              />
              {emailErr && <span style={{ color: "#e02424", fontSize: 12 }}>{emailErr}</span>}
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="button"
                  className="ds-btn ds-btn-primary ds-btn-sm"
                  disabled={emailMutation.isPending || !newEmail}
                  onClick={startEmailChange}
                >
                  发送验证码
                </button>
                <button
                  type="button"
                  className="ds-btn ds-btn-secondary ds-btn-sm"
                  onClick={() => { setEmailStep("idle"); setEmailErr(null); }}
                >
                  取消
                </button>
              </div>
            </div>
          )}
          {(emailStep === "verify-new" || emailStep === "verify-both") && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8, maxWidth: 360 }}>
              {emailHint && <span style={{ fontSize: 12, color: "#6b7280" }}>{emailHint}</span>}
              <div style={{ fontSize: 12, color: "#6b7280" }}>
                目标邮箱：<span style={{ fontFamily: "monospace" }}>{newEmail}</span>
              </div>
              {emailStep === "verify-both" && (
                <input
                  className="form-control"
                  placeholder="旧邮箱收到的验证码"
                  value={emailOldOtp}
                  onChange={(e) => setEmailOldOtp(e.target.value.replace(/\D/g, ""))}
                  maxLength={8}
                  style={{ fontFamily: "monospace", letterSpacing: 4, textAlign: "center" }}
                />
              )}
              <input
                className="form-control"
                placeholder="新邮箱收到的验证码"
                value={emailNewOtp}
                onChange={(e) => setEmailNewOtp(e.target.value.replace(/\D/g, ""))}
                maxLength={8}
                style={{ fontFamily: "monospace", letterSpacing: 4, textAlign: "center" }}
              />
              {emailErr && <span style={{ color: "#e02424", fontSize: 12 }}>{emailErr}</span>}
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="button"
                  className="ds-btn ds-btn-primary ds-btn-sm"
                  disabled={
                    emailMutation.isPending ||
                    !emailNewOtp ||
                    (emailStep === "verify-both" && !emailOldOtp)
                  }
                  onClick={confirmEmailChange}
                >
                  确认换绑
                </button>
                <button
                  type="button"
                  className="ds-btn ds-btn-secondary ds-btn-sm"
                  onClick={() => { setEmailStep("idle"); setEmailErr(null); setEmailHint(null); }}
                >
                  取消
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── 登录历史 ──────────────────────────────────────

function LoginHistorySection() {
  const { query } = useCustom<LoginHistoryItem[]>({ url: "me/login-history", method: "get" });
  const items = query.data?.data ?? [];
  return (
    <div className="ds-card">
      <div className="card-header">
        <span className="card-title">最近登录</span>
        <span className="text-sm text-muted">最近 10 次</span>
      </div>
      <div className="card-body" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr>
              <th>设备类型</th>
              <th>首次登录</th>
              <th>最近活跃</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading && <tr><td colSpan={3} style={{ textAlign: "center", padding: 24, color: "#9ca3af" }}>加载中…</td></tr>}
            {!query.isLoading && items.length === 0 && <tr><td colSpan={3} style={{ textAlign: "center", padding: 24, color: "#9ca3af" }}>暂无登录记录</td></tr>}
            {items.map((it, idx) => (
              <tr key={idx}>
                <td>
                  <span className={it.device_type === "pc" ? "ds-badge ds-badge-blue" : "ds-badge ds-badge-green"}>
                    {it.device_type === "pc" ? "PC 端" : "移动端"}
                  </span>
                </td>
                <td style={{ fontSize: 12, color: "#6b7280" }}>{new Date(it.created_at).toLocaleString("zh-CN")}</td>
                <td style={{ fontSize: 12, color: "#6b7280" }}>{new Date(it.updated_at).toLocaleString("zh-CN")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

