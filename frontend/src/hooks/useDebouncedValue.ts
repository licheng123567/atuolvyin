// v1.6.5 — 通用 debounce hook，用于搜索框等高频更新场景
//
// 用法：
//   const [keyword, setKeyword] = useState("");
//   const debouncedKeyword = useDebouncedValue(keyword, 300);
//   const { query } = useList({ filters: [{ field: "keyword", operator: "contains", value: debouncedKeyword }] });
import { useEffect, useState } from "react";

export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}
