import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

vi.mock("../api", () => ({
  useProviderLegalRequest: vi.fn(),
  uploadRequestMaterial: vi.fn(),
  getMaterialDownloadUrl: vi.fn(),
}));
vi.mock("@refinedev/core", () => ({ useGo: () => vi.fn() }));

import {
  useProviderLegalRequest,
  uploadRequestMaterial,
  getMaterialDownloadUrl,
} from "../api";
import { ProviderLegalRequestDetailPage } from "../requests/[id]";

// ─── shared fixture ───────────────────────────────────────────────────────────
const BASE_DETAIL = {
  id: 7, tenant_id: 1, case_id: 1, owner_name: "张三", project_id: 9,
  project_name: "阳光花园", amount_owed: "3000.00", reason: "逾期3月沟通无果",
  status: "pending", reviewer_note: null, reviewed_at: null,
  related_order_id: null, order_status: null,
  created_at: "2026-05-10T14:22:00", updated_at: "2026-05-10T14:22:00",
  materials: [
    {
      id: 3, request_id: 7, filename: "证据.pdf", content_type: "application/pdf",
      size_bytes: 1234, uploaded_by: 5, created_at: "2026-05-10T14:25:00",
    },
  ],
};

function renderPage() {
  render(
    <MemoryRouter initialEntries={["/provider/legal/requests/7"]}>
      <Routes>
        <Route path="/provider/legal/requests/:id" element={<ProviderLegalRequestDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

// ─── tests ────────────────────────────────────────────────────────────────────
describe("ProviderLegalRequestDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders request info and material list (happy path)", () => {
    vi.mocked(useProviderLegalRequest).mockReturnValue({
      detail: BASE_DETAIL,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderPage();
    expect(screen.getByText(/逾期3月沟通无果/)).toBeDefined();
    expect(screen.getByText("证据.pdf")).toBeDefined();
    expect(screen.getByText("待审批")).toBeDefined();
  });

  it("shows loading indicator", () => {
    vi.mocked(useProviderLegalRequest).mockReturnValue({
      detail: undefined,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    });
    renderPage();
    expect(screen.getByText("加载中…")).toBeDefined();
  });

  it("shows not-found message on error state", () => {
    vi.mocked(useProviderLegalRequest).mockReturnValue({
      detail: undefined,
      isLoading: false,
      isError: true,
      refetch: vi.fn(),
    });
    renderPage();
    expect(screen.getByText("未找到请求")).toBeDefined();
  });

  it("shows empty-materials placeholder when materials list is empty", () => {
    vi.mocked(useProviderLegalRequest).mockReturnValue({
      detail: { ...BASE_DETAIL, materials: [] },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderPage();
    expect(screen.getByText(/点击右上角『上传材料』按钮上传/)).toBeDefined();
  });

  it("calls getMaterialDownloadUrl when download button is clicked", async () => {
    vi.mocked(getMaterialDownloadUrl).mockResolvedValue("https://example.com/file.pdf");
    vi.mocked(useProviderLegalRequest).mockReturnValue({
      detail: BASE_DETAIL,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    // stub window.open to avoid jsdom errors
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);

    renderPage();
    const downloadBtn = screen.getByRole("button", { name: "下载" });
    fireEvent.click(downloadBtn);

    await waitFor(() => {
      expect(vi.mocked(getMaterialDownloadUrl)).toHaveBeenCalledWith(7, 3);
    });
    openSpy.mockRestore();
  });

  it("calls uploadRequestMaterial and then refetch when a file is selected", async () => {
    const mockRefetch = vi.fn().mockResolvedValue(undefined);
    vi.mocked(uploadRequestMaterial).mockResolvedValue({
      id: 99, request_id: 7, filename: "新文件.pdf", content_type: "application/pdf",
      size_bytes: 512, uploaded_by: 5, created_at: "2026-05-17T09:00:00",
    });
    vi.mocked(useProviderLegalRequest).mockReturnValue({
      detail: BASE_DETAIL,
      isLoading: false,
      isError: false,
      refetch: mockRefetch,
    });

    renderPage();

    const input = document.querySelector<HTMLInputElement>("input[type='file']");
    if (!input) throw new Error("file input not found");

    fireEvent.change(input, {
      target: { files: [new File(["x"], "新文件.pdf", { type: "application/pdf" })] },
    });

    await waitFor(() => {
      expect(vi.mocked(uploadRequestMaterial)).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(mockRefetch).toHaveBeenCalledTimes(1);
    });
  });

  it("does not upload and shows alert when file exceeds 20MB", async () => {
    const mockRefetch = vi.fn();
    vi.mocked(useProviderLegalRequest).mockReturnValue({
      detail: BASE_DETAIL,
      isLoading: false,
      isError: false,
      refetch: mockRefetch,
    });

    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => undefined);

    renderPage();

    const bigFile = new File(["x".repeat(1)], "big.pdf", { type: "application/pdf" });
    // Override size property since File constructor ignores content size for this check
    Object.defineProperty(bigFile, "size", { value: 21 * 1024 * 1024 });

    const input = document.querySelector<HTMLInputElement>("input[type='file']");
    if (!input) throw new Error("file input not found");

    fireEvent.change(input, { target: { files: [bigFile] } });

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith("文件超过 20MB 上限");
    });
    expect(vi.mocked(uploadRequestMaterial)).not.toHaveBeenCalled();
    expect(mockRefetch).not.toHaveBeenCalled();

    alertSpy.mockRestore();
  });
});
