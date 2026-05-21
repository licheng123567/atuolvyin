// v2.2 — App-only entry (Android WebView 专用瘦 bundle)。
// vite.config alias 已把 react-router-dom→v6, react-router→v6,
// @refinedev/core→refine-mobile-stub.tsx。
//
// 入口文件不需要 Fast Refresh — 它通过 createRoot().render() 启动 app,
// 不导出任何组件,本身不参与 HMR(任何改动都会全量刷新)。
/* eslint-disable react-refresh/only-export-components */
import { Component, StrictMode, useEffect, type ErrorInfo, type ReactNode } from "react"
import { createRoot } from "react-dom/client"
import { Refine } from "@refinedev/core"
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"

import "./index.css"
import "./styles/design-system.css"
import "./styles/design-system-mobile.css"

import MobileLayout from "./pages/app/_layout"
import MobileHomePage from "./pages/app/home"
import MobileProfilePage from "./pages/app/profile"
import MobileCasesPage from "./pages/app/cases"
import MobileCaseDetailPage from "./pages/app/cases/[id]"
import MobileCallHistoryPage from "./pages/app/call-history"
// v2.4 Module A — App 专属登录页（不复用 PC 双 panel 布局）
import MobileLoginPage from "./pages/app/login"
// v2.4 Module C/D — 3 缺屏 + In-call React WebView
import MobileCallEndPage from "./pages/app/call-end/[id]"
import MobileForceLogoutPage from "./pages/app/force-logout"
import MobileInCallPage from "./pages/app/in-call/[id]"

function beacon(kind: string, extra = ""): void {
  try {
    const img = new Image()
    img.src =
      "http://192.168.31.242:18000/api/v1/_debug/client-error-beacon?kind=" +
      kind +
      (extra ? "&extra=" + encodeURIComponent(extra.slice(0, 800)) : "") +
      "&ts=" +
      Date.now()
  } catch {
    /* ignore */
  }
}

interface ErrBoundaryState { err: Error | null }

class ErrBoundary extends Component<{ children: ReactNode }, ErrBoundaryState> {
  state: ErrBoundaryState = { err: null }
  static getDerivedStateFromError(err: Error): ErrBoundaryState {
    return { err }
  }
  componentDidCatch(err: Error, info: ErrorInfo): void {
    beacon("REACT_THROW", `${err.message} | ${(info.componentStack || "").slice(0, 500)}`)
  }
  render(): ReactNode {
    if (this.state.err) {
      return (
        <div style={{ padding: 20, background: "orange", color: "black", fontSize: 14 }}>
          <h2>React Error</h2>
          <p>{this.state.err.message}</p>
          <pre style={{ whiteSpace: "pre-wrap", fontSize: 11 }}>
            {this.state.err.stack}
          </pre>
        </div>
      )
    }
    return this.props.children
  }
}

function MobileApp() {
  useEffect(() => beacon("MOBILEAPP_USEEFFECT_RAN"), [])
  return (
    <BrowserRouter>
      <Refine>
        <Routes>
          <Route path="/login" element={<MobileLoginPage />} />
          {/* v2.4 — 3 个不在 layout 框架内的全屏页（无底部 tab） */}
          <Route path="/app/in-call/:id" element={<MobileInCallPage />} />
          <Route path="/app/call-end/:id" element={<MobileCallEndPage />} />
          <Route path="/app/force-logout" element={<MobileForceLogoutPage />} />
          <Route path="/app" element={<MobileLayout />}>
            <Route index element={<Navigate to="home" replace />} />
            <Route path="home" element={<MobileHomePage />} />
            <Route path="cases" element={<MobileCasesPage />} />
            <Route path="cases/:id" element={<MobileCaseDetailPage />} />
            <Route path="call-history" element={<MobileCallHistoryPage />} />
            <Route path="profile" element={<MobileProfilePage />} />
            <Route path="*" element={<Navigate to="home" replace />} />
          </Route>
          <Route path="*" element={<Navigate to="/app/home" replace />} />
        </Routes>
      </Refine>
    </BrowserRouter>
  )
}

beacon("BUNDLE_TOP_REACHED")
const rootEl = document.getElementById("root")
if (rootEl) {
  beacon("ABOUT_TO_RENDER")
  createRoot(rootEl).render(
    <StrictMode>
      <ErrBoundary>
        <MobileApp />
      </ErrBoundary>
    </StrictMode>,
  )
  beacon("RENDER_CALL_RETURNED")
}
