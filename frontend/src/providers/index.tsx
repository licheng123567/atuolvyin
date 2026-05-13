import type { DataProvider } from "@refinedev/core";
import simpleRestDataProvider from "@refinedev/simple-rest";
import axios from "axios";
import { getToken } from "./auth-provider";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:18000";

// v1.7.5 — 给 dataProvider 的 axios 实例注入 Authorization 拦截器。
// Refine simple-rest 默认 axiosInstance 不带 auth，导致所有 useList/useOne/
// useCustom 请求 401。这里在每次请求前从 localStorage 读 token 注入。
const httpClient = axios.create();

httpClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

const API_BASE_V1 = `${API_BASE}/api/v1`;
const baseProvider = simpleRestDataProvider(API_BASE_V1, httpClient);

// Bug fix: simple-rest 的 custom() 不自动前缀 apiUrl，导致 useCustom 用相对 URL
// 时被浏览器解析成 `${currentPage}/${url}`。这里包一层自动补上 apiUrl。
export const dataProvider: DataProvider = {
  ...baseProvider,
  custom: async (params: Parameters<typeof baseProvider.custom>[0]) => {
    const url = params.url.startsWith("http")
      ? params.url
      : `${API_BASE_V1}/${params.url.replace(/^\/+/, "")}`;
    return baseProvider.custom({ ...params, url });
  },
};
