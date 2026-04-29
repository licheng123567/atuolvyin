import simpleRestDataProvider from "@refinedev/simple-rest";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:18000";

export const dataProvider = simpleRestDataProvider(`${API_BASE}/api/v1`);
