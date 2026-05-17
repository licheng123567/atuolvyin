import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useProviderLegalRequests } from "../api";

vi.mock("../api", () => ({ useProviderLegalRequests: vi.fn() }));
vi.mock("@refinedev/core", () => ({ useGo: () => vi.fn() }));

import { ProviderLegalRequestsPage } from "../requests/index";

const ROW = {
  id: 7, tenant_id: 1, case_id: 1, owner_name: "张三", project_id: 9,
  project_name: "阳光花园", amount_owed: "3000.00", reason: "逾期3月沟通无果",
  status: "pending", reviewer_note: null, reviewed_at: null,
  related_order_id: null, order_status: null,
  created_at: "2026-05-10T14:22:00", updated_at: "2026-05-10T14:22:00",
};

describe("ProviderLegalRequestsPage", () => {
  it("renders request row with status badge", () => {
    vi.mocked(useProviderLegalRequests).mockReturnValue({
      items: [ROW], total: 1, isLoading: false, isError: false,
    });
    render(<MemoryRouter><ProviderLegalRequestsPage /></MemoryRouter>);
    expect(screen.getByText("张三")).toBeDefined();
    expect(screen.getByText("待审批")).toBeDefined();
  });

  it("shows loading indicator", () => {
    vi.mocked(useProviderLegalRequests).mockReturnValue({
      items: [], total: 0, isLoading: true, isError: false,
    });
    render(<MemoryRouter><ProviderLegalRequestsPage /></MemoryRouter>);
    expect(screen.getByText("加载中…")).toBeDefined();
  });

  it("shows empty state", () => {
    vi.mocked(useProviderLegalRequests).mockReturnValue({
      items: [], total: 0, isLoading: false, isError: false,
    });
    render(<MemoryRouter><ProviderLegalRequestsPage /></MemoryRouter>);
    expect(screen.getByText("暂无转化请求")).toBeDefined();
  });
});
