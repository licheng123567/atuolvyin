// v2.1 Sprint Task 7 — 坐席设备能力列表（admin / supervisor / superadmin 可见）
//
// 数据源：GET /api/v1/admin/agent-devices?page=&page_size=&capability=&q=
// 用途：让物业管理员/督导一眼看出哪些坐席机器不支持系统级通话录音 → 实时 AI 不可用，需要换机
import { useCustom } from "@refinedev/core";
import { Smartphone } from "lucide-react";
import { useState } from "react";
import { PaginationBar } from "../../../components/ui/PaginationBar";
import { SearchInput } from "../../../components/ui/SearchInput";
import { useDebouncedValue } from "../../../hooks/useDebouncedValue";

const PAGE_SIZE = 20;

type Capability = "realtime" | "post_upload" | "incompatible";

interface AgentDeviceItem {
  user_id: number;
  user_name: string;
  role: string;
  device_id: string;
  manufacturer: string | null;
  model: string | null;
  android_version: string | null;
  rom_label: string | null;
  latest_capability: Capability | string;
  latest_self_check_at: string;
  actual_recording_works: boolean | null;
  status_label: string;
}

interface AgentDevicesResp {
  items: AgentDeviceItem[];
  total: number;
  page: number;
  page_size: number;
}

const CAPABILITY_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "全部录音模式" },
  { value: "realtime", label: "实时可用" },
  { value: "post_upload", label: "事后上传" },
  { value: "incompatible", label: "录音不可用" },
];

const CAPABILITY_BADGE: Record<string, { label: string; cls: string }> = {
  realtime: { label: "实时可用", cls: "ds-badge ds-badge-green" },
  post_upload: { label: "事后上传", cls: "ds-badge ds-badge-orange" },
  incompatible: { label: "录音不可用", cls: "ds-badge ds-badge-red" },
};

const ROLE_LABEL: Record<string, string> = {
  admin: "管理员",
  supervisor: "督导",
  agent: "催收员",
  legal: "法务对接人",
  workorder: "协调员",
  coordinator: "协调员",
  project_manager: "项目经理",
  superadmin: "平台超管",
  ops: "平台运营",
};

export function AdminAgentDevicesPage() {
  const [page, setPage] = useState(1);
  const [capability, setCapability] = useState("");
  const [q, setQ] = useState("");
  const debouncedQ = useDebouncedValue(q, 300);

  const queryParams: Record<string, string | number> = {
    page,
    page_size: PAGE_SIZE,
  };
  if (capability) queryParams.capability = capability;
  if (debouncedQ.trim()) queryParams.q = debouncedQ.trim();

  const { query } = useCustom<AgentDevicesResp>({
    url: "admin/agent-devices",
    method: "get",
    config: { query: queryParams },
  });

  const data = query.data?.data;
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const isLoading = query.isLoading;

  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Smartphone
            style={{ color: "var(--color-primary)", width: 22, height: 22 }}
          />
          <div>
            <h1 className="page-title">坐席设备能力</h1>
            <div className="page-subtitle">
              各坐席手机的录音能力 · 共 {total} 台
              <span style={{ marginLeft: 12, color: "#9ca3af", fontSize: 12 }}>
                · Android 10+ 部分机型不支持系统级通话录音 → 实时 AI 不可用，需联系坐席换机
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="table-wrap">
        <div className="table-toolbar">
          <SearchInput
            value={q}
            onChange={(v) => {
              setQ(v);
              setPage(1);
            }}
            placeholder="搜索姓名 / 设备 ID / 型号"
            width={240}
          />
          <select
            className="form-control"
            style={{ width: 150 }}
            value={capability}
            onChange={(e) => {
              setCapability(e.target.value);
              setPage(1);
            }}
          >
            {CAPABILITY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        <table>
          <thead>
            <tr>
              <th>坐席</th>
              <th>角色</th>
              <th>设备</th>
              <th>Android</th>
              <th>ROM</th>
              <th>录音模式</th>
              <th>实测</th>
              <th>上次自检</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td
                  colSpan={8}
                  style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}
                >
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td
                  colSpan={8}
                  style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}
                >
                  暂无坐席设备记录
                </td>
              </tr>
            )}
            {!isLoading &&
              items.map((it) => {
                const badge =
                  CAPABILITY_BADGE[it.latest_capability] ?? {
                    label: it.latest_capability,
                    cls: "ds-badge ds-badge-gray",
                  };
                return (
                  <tr key={`${it.user_id}-${it.device_id}`}>
                    <td>
                      <strong>{it.user_name}</strong>
                    </td>
                    <td>{ROLE_LABEL[it.role] ?? it.role}</td>
                    <td>
                      <div>
                        {it.manufacturer ?? "—"} {it.model ?? ""}
                      </div>
                      <div
                        style={{
                          fontFamily: "var(--font-mono, monospace)",
                          fontSize: 11,
                          color: "var(--color-neutral-500)",
                        }}
                      >
                        {it.device_id}
                      </div>
                    </td>
                    <td>{it.android_version ?? "—"}</td>
                    <td>{it.rom_label ?? "—"}</td>
                    <td>
                      <span className={badge.cls}>{badge.label}</span>
                    </td>
                    <td>
                      {it.actual_recording_works === true && (
                        <span style={{ color: "var(--color-success)", fontWeight: 600 }}>
                          ✓
                        </span>
                      )}
                      {it.actual_recording_works === false && (
                        <span style={{ color: "var(--color-danger)", fontWeight: 600 }}>
                          ✗
                        </span>
                      )}
                      {it.actual_recording_works == null && (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td
                      style={{
                        fontFamily: "var(--font-mono, monospace)",
                        fontSize: 12,
                      }}
                    >
                      {new Date(it.latest_self_check_at).toLocaleString("zh-CN")}
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>

        <PaginationBar
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          onPageChange={setPage}
        />
      </div>
    </div>
  );
}

export default AdminAgentDevicesPage;
