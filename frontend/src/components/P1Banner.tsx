// 共享：v1.1 占位提示 banner（对应 ui/*.html 的 .p1-banner）
import { AlertTriangle } from "lucide-react";
import type { ReactNode } from "react";

export function P1Banner({ children }: { children: ReactNode }) {
  return (
    <div className="p1-banner">
      <AlertTriangle className="w-4 h-4" />
      <div>{children}</div>
    </div>
  );
}
