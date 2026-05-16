// v2.3 Module 1 — 共享拨号逻辑（案件列表 inline + 详情页 sticky 按钮共用）
//
// 拨号前会基于 Bridge.getCapability() 做检查：
// - incompatible 设备弹 confirm，让用户知晓「本次通话将无 AI 分析」
// - 用户取消则中止
import { Bridge, type DialPayload } from "../../../lib/jsBridge";

interface DialableCase {
  id: number;
  owner: {
    name: string;
    phone?: string | null;
    phone_masked: string;
  };
}

/**
 * 触发一次案件拨号；返回 true 表示请求已派给 native，false 表示用户取消或数据缺失。
 */
export function dialCase(c: DialableCase): boolean {
  if (!c?.owner) return false;
  const cap = Bridge.getCapability();
  if (cap.capability === "incompatible") {
    const ok = window.confirm(
      `您的设备 (${cap.rom || "未识别"}) 无法保存通话录音，本次通话将无 AI 分析。\n\n是否继续拨号？`,
    );
    if (!ok) return false;
  }
  const phone = c.owner.phone ?? c.owner.phone_masked;
  const payload: DialPayload = {
    case_id: c.id,
    phone,
    owner_name: c.owner.name,
  };
  Bridge.dialCase(payload);
  return true;
}
