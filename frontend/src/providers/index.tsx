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

export const dataProvider = simpleRestDataProvider(
  `${API_BASE}/api/v1`,
  httpClient,
);
