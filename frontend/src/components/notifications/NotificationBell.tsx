// Sprint 15.4b — 站内信铃铛（PRD §L412）
// 定时拉 unread-count；点击展开 drawer 显示最近 N 条；mark read / read-all。
import { useCustom, useCustomMutation } from "@refinedev/core";
import { Bell, CheckCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";

interface NotificationItem {
  id: number;
  event_type: string;
  severity: "info" | "warn" | "critical";
  title: string;
  body: string;
  read_at: string | null;
  created_at: string;
}

interface ListResp {
  items: NotificationItem[];
  total: number;
}
interface UnreadCountResp {
  unread: number;
}

const POLL_MS = 30_000;

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);

  const { query: countQuery } = useCustom<UnreadCountResp>({
    url: "users/me/notifications/unread-count",
    method: "get",
    queryOptions: { refetchInterval: POLL_MS },
  });
  const unread = countQuery.data?.data?.unread ?? 0;

  const { query: listQuery, refetch: refetchList } = useCustom<ListResp>({
    url: "users/me/notifications",
    method: "get",
    config: { query: { limit: 20 } },
    queryOptions: { enabled: open },
  });

  const { mutate: mutateAction } = useCustomMutation();

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const markRead = (id: number) => {
    mutateAction(
      {
        url: `users/me/notifications/${id}/read`,
        method: "patch",
        values: {},
      },
      {
        onSuccess: () => {
          refetchList();
          countQuery.refetch();
        },
      },
    );
  };

  const markAllRead = () => {
    mutateAction(
      {
        url: "users/me/notifications/read-all",
        method: "patch",
        values: {},
      },
      {
        onSuccess: () => {
          refetchList();
          countQuery.refetch();
        },
      },
    );
  };

  const items = listQuery.data?.data?.items ?? [];

  return (
    <div className="relative" ref={drawerRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="relative p-2 rounded-md hover:bg-[var(--color-neutral-100)] transition"
        aria-label="通知"
      >
        <Bell className="w-5 h-5 text-[var(--color-neutral-700)]" />
        {unread > 0 && (
          <span className="absolute top-1 right-1 min-w-[16px] h-[16px] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center border border-white">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-96 max-h-[80vh] overflow-auto bg-white border border-[var(--color-neutral-200)] rounded-lg shadow-lg z-50">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-neutral-100)] sticky top-0 bg-white">
            <h3 className="text-sm font-semibold text-[var(--color-neutral-900)]">
              通知中心
            </h3>
            <button
              type="button"
              onClick={markAllRead}
              disabled={unread === 0}
              className="flex items-center gap-1 text-xs text-[var(--color-primary)] hover:underline disabled:opacity-40 disabled:no-underline"
            >
              <CheckCheck className="w-3 h-3" /> 全部标为已读
            </button>
          </div>

          {listQuery.isLoading && (
            <div className="px-4 py-8 text-center text-sm text-[var(--color-neutral-500)]">
              加载中…
            </div>
          )}

          {!listQuery.isLoading && items.length === 0 && (
            <div className="px-4 py-12 text-center text-sm text-[var(--color-neutral-500)]">
              暂无通知
            </div>
          )}

          <ul className="divide-y divide-[var(--color-neutral-100)]">
            {items.map((n) => (
              <li
                key={n.id}
                className={`px-4 py-3 cursor-pointer hover:bg-[var(--color-neutral-50)] ${
                  n.read_at ? "opacity-60" : ""
                }`}
                onClick={() => !n.read_at && markRead(n.id)}
              >
                <div className="flex items-start gap-2">
                  <SeverityDot severity={n.severity} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-[var(--color-neutral-900)] truncate">
                      {n.title}
                    </div>
                    <div className="text-xs text-[var(--color-neutral-600)] mt-0.5 line-clamp-2">
                      {n.body}
                    </div>
                    <div className="text-[11px] text-[var(--color-neutral-400)] mt-1">
                      {new Date(n.created_at).toLocaleString("zh-CN")}
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function SeverityDot({ severity }: { severity: NotificationItem["severity"] }) {
  const cls =
    severity === "critical"
      ? "bg-red-500"
      : severity === "warn"
      ? "bg-amber-500"
      : "bg-blue-400";
  return <span className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${cls}`} />;
}
