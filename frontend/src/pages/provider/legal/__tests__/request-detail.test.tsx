import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

vi.mock("../api", () => ({
  useProviderLegalRequest: () => ({
    detail: {
      id: 7, tenant_id: 1, case_id: 1, owner_name: "张三", project_id: 9,
      project_name: "阳光花园", amount_owed: "3000.00", reason: "逾期3月沟通无果",
      status: "pending", reviewer_note: null, reviewed_at: null,
      related_order_id: null, order_status: null,
      created_at: "2026-05-10T14:22:00", updated_at: "2026-05-10T14:22:00",
      materials: [
        { id: 3, request_id: 7, filename: "证据.pdf", content_type: "application/pdf",
          size_bytes: 1234, uploaded_by: 5, created_at: "2026-05-10T14:25:00" },
      ],
    },
    isLoading: false, isError: false, refetch: vi.fn(),
  }),
  uploadRequestMaterial: vi.fn(),
  getMaterialDownloadUrl: vi.fn(),
}));
vi.mock("@refinedev/core", () => ({ useGo: () => vi.fn() }));

import { ProviderLegalRequestDetailPage } from "../requests/[id]";

describe("ProviderLegalRequestDetailPage", () => {
  it("renders request info and material list", () => {
    render(
      <MemoryRouter initialEntries={["/provider/legal/requests/7"]}>
        <Routes>
          <Route path="/provider/legal/requests/:id" element={<ProviderLegalRequestDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText(/逾期3月沟通无果/)).toBeDefined();
    expect(screen.getByText("证据.pdf")).toBeDefined();
    expect(screen.getByText("待审批")).toBeDefined();
  });
});
