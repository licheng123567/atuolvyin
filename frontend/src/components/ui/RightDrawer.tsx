// v0.5.6 — RightDrawer 共享组件
//
// 用于复杂表单 / 大量信息展示场景:右侧从屏幕边缘滑出,左边缘可拖动调整宽度,
// 关闭后宽度记 localStorage,下次打开自动还原。详见 docs/UI_PATTERNS_MODAL.md。
//
// 设计要点:
// - 不依赖 shadcn/ui(项目没装),直接基于 @radix-ui/react-dialog 的 portal + a11y
// - 拖动手柄不用 react-resizable-panels(过度抽象),手写 mousedown/mousemove 几行就够
// - 宽度持久化用 drawerKey 区分(不同弹窗各自记)
//
// API:
//   <RightDrawer
//     open={open}
//     onClose={() => setOpen(false)}
//     title="重新分配案件"
//     drawerKey="supervisor-reassign"
//     defaultWidth={520}
//   >
//     <body>...</body>
//   </RightDrawer>

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

const STORAGE_PREFIX = "right-drawer-width-";
const MIN_WIDTH = 360;
const MAX_WIDTH_VW = 0.8; // 80vw

interface RightDrawerProps {
  open: boolean;
  onClose: () => void;
  /** drawer 标题(显示在 header 左侧) */
  title: ReactNode;
  /** drawerKey 用于 localStorage 持久化宽度;同一弹窗用同一 key */
  drawerKey: string;
  /** 默认宽度(px);用户未拖动过时用这个值;有 localStorage 时优先用 */
  defaultWidth?: number;
  /** footer 区域(可选)— 通常放确认/取消按钮 */
  footer?: ReactNode;
  children: ReactNode;
}

function loadSavedWidth(key: string, fallback: number): number {
  if (typeof window === "undefined") return fallback;
  const raw = window.localStorage.getItem(STORAGE_PREFIX + key);
  if (!raw) return fallback;
  const n = Number(raw);
  if (!Number.isFinite(n) || n < MIN_WIDTH) return fallback;
  return n;
}

function saveWidth(key: string, value: number): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_PREFIX + key, String(Math.round(value)));
  } catch {
    /* localStorage 满了 / 隐私模式 — 忽略,不影响渲染 */
  }
}

export function RightDrawer({
  open,
  onClose,
  title,
  drawerKey,
  defaultWidth = 480,
  footer,
  children,
}: RightDrawerProps) {
  const [width, setWidth] = useState<number>(() => loadSavedWidth(drawerKey, defaultWidth));
  const draggingRef = useRef(false);
  const widthRef = useRef(width);
  const drawerKeyRef = useRef(drawerKey);

  // 同步 width/drawerKey 到 ref(供全局 mouseup 持久化时读最新值,不依赖 closure);
  // 走 useEffect 是 react-hooks 严格模式要求(不能 render 期间写 ref)
  useEffect(() => {
    widthRef.current = width;
  }, [width]);
  useEffect(() => {
    drawerKeyRef.current = drawerKey;
  }, [drawerKey]);

  // 注:不在 useEffect 里重读 localStorage — width 初始值已 lazy init 自 loadSavedWidth,
  // drawerKey 是 caller 固定 prop 不会运行时变,无需重新同步。

  // 鼠标拖动:mousemove/mouseup listener 全局注册一次(在 mount 时),用 draggingRef
  // 拨开关。这样避免 listener 引用自身导致 lint 报错,也避免 listener 频繁挂载/卸载。
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!draggingRef.current) return;
      const newWidth = window.innerWidth - e.clientX;
      const max = window.innerWidth * MAX_WIDTH_VW;
      const clamped = Math.max(MIN_WIDTH, Math.min(max, newWidth));
      setWidth(clamped);
      widthRef.current = clamped;
    };
    const onUp = () => {
      if (!draggingRef.current) return;
      draggingRef.current = false;
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      saveWidth(drawerKeyRef.current, widthRef.current);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, []);

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    draggingRef.current = true;
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
  };

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="right-drawer-overlay" />
        <Dialog.Content className="right-drawer" style={{ width }}>
          <div
            className="right-drawer-resizer"
            onMouseDown={handleMouseDown}
            title="左右拖动调整宽度"
            aria-label="调整宽度"
          />
          <div className="right-drawer-header">
            <Dialog.Title asChild>
              <h2 className="right-drawer-title">{title}</h2>
            </Dialog.Title>
            <Dialog.Close asChild>
              <button
                type="button"
                className="right-drawer-close"
                aria-label="关闭"
                onClick={onClose}
              >
                <X className="w-5 h-5" />
              </button>
            </Dialog.Close>
          </div>
          <div className="right-drawer-body">{children}</div>
          {footer && <div className="right-drawer-footer">{footer}</div>}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
