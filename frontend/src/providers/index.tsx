import type { DataProvider } from "@refinedev/core";
import simpleRestDataProvider from "@refinedev/simple-rest";
import axios from "axios";
import { Bridge } from "../lib/jsBridge";

// v2.2 — Android WebView 内 backend URL 来自 AndroidBridge.getBackendUrl()
// （onboarding 阶段用户配置的后端地址），PC dev 走 VITE_API_BASE 环境变量。
const API_BASE =
  Bridge.getBackendUrl() ??
  (import.meta.env.VITE_API_BASE as string | undefined) ??
  "http://localhost:18000";

// v1.7.5 — 给 dataProvider 的 axios 实例注入 Authorization 拦截器。
// v2.2 修复：原先只读 localStorage，WebView 内 token 在 AndroidBridge / __JWT__
// 而非 localStorage，导致所有 useList/useOne/useCustom 401。改用 Bridge.getJwt
// 多源回退（AndroidBridge → window.__JWT__ → localStorage）。
const httpClient = axios.create();

httpClient.interceptors.request.use((config) => {
  const token = Bridge.getJwt();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

const API_BASE_V1 = `${API_BASE}/api/v1`;
const baseProvider = simpleRestDataProvider(API_BASE_V1, httpClient);

// v2.2 — Refine simple-rest 默认期望 response body 是 array + x-total-count header。
// 我们后端返回 PaginatedResponse 形状 `{items, total, page, page_size}`。
// 包一层 getList，把 {items, total} 转换成 Refine 期望的 {data, total}。
const wrappedGetList = (async (params) => {
  const result = await baseProvider.getList(params);
  const raw: unknown = result.data;
  if (Array.isArray(raw)) {
    return result;
  }
  if (raw && typeof raw === "object" && "items" in raw) {
    const obj = raw as { items: unknown[]; total?: number };
    return {
      data: obj.items as typeof result.data,
      total: obj.total ?? obj.items.length,
    };
  }
  return result;
}) as DataProvider["getList"];

// Bug fix: simple-rest 的 custom() 不自动前缀 apiUrl，导致 useCustom 用相对 URL
// 时被浏览器解析成 `${currentPage}/${url}`。这里包一层自动补上 apiUrl。
export const dataProvider: DataProvider = {
  ...baseProvider,
  getList: wrappedGetList,
  custom: async (params: Parameters<NonNullable<typeof baseProvider.custom>>[0]) => {
    const url = params.url.startsWith("http")
      ? params.url
      : `${API_BASE_V1}/${params.url.replace(/^\/+/, "")}`;
    return baseProvider.custom!({ ...params, url });
  },
};
