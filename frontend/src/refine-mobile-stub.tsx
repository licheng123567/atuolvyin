// v2.2 — Refine v5 minimal stub for the mobile bundle.
// Refine v5 + TanStack Query 5 在 Android 6 stock WebView (Chromium 57)
// 模块/组件初始化阶段会 silent-abort（无 JS error，无 beacon）。这个 stub
// 只实现 mobile pages 实际用到的 5 个 hooks，全部用原生 fetch + useState。
// vite.config 的 resolve.alias 只在 mobile build 走这里；PC dev 仍是真 Refine。
import { useEffect, useRef, useState, type ReactNode } from "react"
import { useNavigate } from "react-router-dom"
import { Bridge } from "./lib/jsBridge"

const BACKEND = (): string =>
  (Bridge.getBackendUrl() || "http://localhost:18000").replace(/\/+$/, "")

function authHeaders(): Record<string, string> {
  const token = Bridge.getJwt()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

interface QueryState<T> {
  data: T | undefined
  isLoading: boolean
  isError: boolean
  error: Error | null
  refetch: () => void
}

function useFetcher<T>(deps: unknown[], fetcher: () => Promise<T>): QueryState<T> {
  const [data, setData] = useState<T | undefined>(undefined)
  const [isLoading, setLoading] = useState(true)
  const [isError, setIsError] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [tick, setTick] = useState(0)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setIsError(false)
    setError(null)
    fetcherRef
      .current()
      .then((d) => {
        if (!cancelled) {
          setData(d)
          setLoading(false)
        }
      })
      .catch((e: Error) => {
        if (!cancelled) {
          setIsError(true)
          setError(e)
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])
  return { data, isLoading, isError, error, refetch: () => setTick((t) => t + 1) }
}

// Refine wrapper: just render children. dataProvider/authProvider props ignored
// (we stub the hooks directly using fetch + Bridge).
export function Refine({ children }: { children?: ReactNode }): ReactNode {
  return <>{children}</>
}

interface PaginatedRaw<T> {
  items?: T[]
  total?: number
}

// useList — only the API surface mobile pages use
interface UseListParams {
  resource: string
  dataProviderName?: string
  filters?: Array<{ field: string; operator?: string; value: unknown }>
  pagination?: { current?: number; pageSize?: number }
  sorters?: Array<{ field: string; order?: "asc" | "desc" }>
}

interface UseListResult<T> {
  query: QueryState<{ data: T[]; total: number }>
}

export function useList<T>(params: UseListParams): UseListResult<T> {
  const { resource, filters, pagination, sorters } = params
  const url = (() => {
    const base = `${BACKEND()}/api/v1/${resource}`
    const qs = new URLSearchParams()
    if (pagination?.pageSize) {
      const cur = pagination.current ?? 1
      const start = (cur - 1) * pagination.pageSize
      const end = start + pagination.pageSize
      qs.set("_start", String(start))
      qs.set("_end", String(end))
    }
    if (filters) {
      for (const f of filters) {
        qs.set(f.field, String(f.value))
      }
    }
    if (sorters && sorters[0]) {
      qs.set("_sort", sorters[0].field)
      qs.set("_order", sorters[0].order ?? "asc")
    }
    const q = qs.toString()
    return q ? `${base}?${q}` : base
  })()

  const dep = url
  const q = useFetcher<{ data: T[]; total: number }>([dep], async () => {
    const res = await fetch(url, { headers: authHeaders() })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const raw: unknown = await res.json()
    if (Array.isArray(raw)) {
      return { data: raw as T[], total: raw.length }
    }
    if (raw && typeof raw === "object" && "items" in (raw as object)) {
      const obj = raw as PaginatedRaw<T>
      return { data: obj.items ?? [], total: obj.total ?? (obj.items?.length ?? 0) }
    }
    return { data: [], total: 0 }
  })
  return { query: q }
}

// useOne — single resource by id
interface UseOneParams {
  resource: string
  id: string | number
  dataProviderName?: string
}
interface UseOneResult<T> {
  query: QueryState<{ data: T }>
}
export function useOne<T>(params: UseOneParams): UseOneResult<T> {
  const url = `${BACKEND()}/api/v1/${params.resource}/${params.id}`
  const q = useFetcher<{ data: T }>([url], async () => {
    const res = await fetch(url, { headers: authHeaders() })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = (await res.json()) as T
    return { data }
  })
  return { query: q }
}

// useCustom — arbitrary URL
interface UseCustomParams {
  url: string
  method?: "get" | "post" | "put" | "patch" | "delete"
  config?: { query?: Record<string, unknown>; payload?: unknown }
  dataProviderName?: string
}
interface UseCustomResult<T> {
  query: QueryState<{ data: T }>
}
export function useCustom<T>(params: UseCustomParams): UseCustomResult<T> {
  const method = (params.method ?? "get").toUpperCase()
  const url = (() => {
    const u = params.url.startsWith("http")
      ? params.url
      : `${BACKEND()}/api/v1/${params.url.replace(/^\/+/, "")}`
    if (method === "GET" && params.config?.query) {
      const qs = new URLSearchParams()
      for (const [k, v] of Object.entries(params.config.query)) {
        if (v !== undefined && v !== null) qs.set(k, String(v))
      }
      const q = qs.toString()
      return q ? `${u}?${q}` : u
    }
    return u
  })()
  const dep = `${method} ${url}`
  const q = useFetcher<{ data: T }>([dep], async () => {
    const init: RequestInit = {
      method,
      headers: { ...authHeaders(), "Content-Type": "application/json" },
    }
    if (method !== "GET" && params.config?.payload) {
      init.body = JSON.stringify(params.config.payload)
    }
    const res = await fetch(url, init)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = (await res.json()) as T
    return { data }
  })
  return { query: q }
}

// useGetIdentity —
// v2.3.1 fix: App 端 Compose login（MainActivity）只把 JWT 存到 native AppConfig；
// frontend authProvider.login 从未被调用 → localStorage USER_KEY 永远是空 →
// Profile 头像永远「未登录」。修：本地拿不到时调 /api/v1/users/me 兜底（带 JWT）。
import { authProvider } from "./providers/auth-provider"

interface UseGetIdentityResult<T> {
  data: T | undefined
  isLoading: boolean
}

interface MeResponse {
  id: number
  name: string
  role: string
  tenant_id: number | null
  tenant_name?: string | null
  scope: string
}

export function useGetIdentity<T>(): UseGetIdentityResult<T> {
  const [data, setData] = useState<T | undefined>(undefined)
  const [isLoading, setLoading] = useState(true)
  useEffect(() => {
    let cancelled = false
    const finish = (d: unknown) => {
      if (cancelled) return
      setData(d as T)
      setLoading(false)
    }
    const fetchMe = async () => {
      // 1) 先看 authProvider 缓存（PC 走过 login 的情况）
      if (authProvider.getIdentity) {
        const cached = await Promise.resolve(authProvider.getIdentity({})).catch(
          () => null,
        )
        if (cached) return finish(cached)
      }
      // 2) App Compose login 路径：调后端 /api/v1/users/me 拿用户信息
      const token = Bridge.getJwt()
      if (!token) return finish(undefined)
      try {
        const res = await fetch(`${BACKEND()}/api/v1/users/me`, {
          headers: authHeaders(),
        })
        if (!res.ok) return finish(undefined)
        const me = (await res.json()) as MeResponse
        // 写一份到 localStorage 让 PC dev 路径也能拿到
        try {
          localStorage.setItem(
            "autoluyin_user",
            JSON.stringify({
              id: me.id,
              name: me.name,
              role: me.role,
              tenant_id: me.tenant_id ?? null,
              tenant_name: me.tenant_name ?? null,
              scope: me.scope,
            }),
          )
        } catch {
          /* localStorage 可能在 WebView 禁用 */
        }
        finish(me)
      } catch {
        finish(undefined)
      }
    }
    void fetchMe()
    return () => {
      cancelled = true
    }
  }, [])
  return { data, isLoading }
}

// useLogin — uses authProvider.login
interface UseLoginOptions<R> {
  onSuccess?: (data: R) => void
  onError?: (err: Error) => void
}
interface UseLoginResult<I, R> {
  mutate: (input: I, opts?: UseLoginOptions<R>) => void
  isPending: boolean
  isLoading: boolean
}
export function useLogin<I = unknown, R = unknown>(): UseLoginResult<I, R> {
  const [isPending, setPending] = useState(false)
  const navigate = useNavigate()
  const mutate = (input: I, opts?: UseLoginOptions<R>) => {
    if (!authProvider.login) {
      opts?.onError?.(new Error("authProvider.login not configured"))
      return
    }
    setPending(true)
    Promise.resolve(authProvider.login(input as Parameters<typeof authProvider.login>[0]))
      .then((res) => {
        setPending(false)
        opts?.onSuccess?.(res as R)
        // v0.5.2 — Refine 实际 useLogin 会在成功后跳 redirectTo。stub 必须自己做。
        const r = res as { success?: boolean; redirectTo?: string }
        if (r?.success && r.redirectTo) {
          // App 首页根路径 / 实际重定向到 /app/home（main-mobile Routes catch-all）
          navigate(r.redirectTo === "/" ? "/app/home" : r.redirectTo, {
            replace: true,
          })
        }
      })
      .catch((e: Error) => {
        setPending(false)
        opts?.onError?.(e)
      })
  }
  return { mutate, isPending, isLoading: isPending }
}
