from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    admin,
    admin_agent_devices,
    admin_cases,
    admin_compliance,
    admin_dashboard,
    admin_legal_conversion,
    admin_legal_internal_config,
    admin_project_members,
    admin_projects,
    admin_provider_recommendation,
    admin_providers,
    admin_reports,
    admin_risk_keywords,
    admin_scripts,
    admin_settings,
    admin_settlements,
    admin_suggestion_config,
    agent_cases,
    agent_me,
    auth,
    auth_extras,
    calls,
    calls_v1,
    devices,
    devices_v1,
    discount_offers,
    lawfirm_orders,
    lawyer_orders,
    legal_cases,
    legal_conversion_requests,
    legal_documents,
    legal_internal_orders,
    legal_workstation,
    ops,
    ops_extras,
    ops_law_firms,
    ops_legal_packages,
    ops_providers,
    pm_dashboard,
    provider_admin,
    provider_cases,
    provider_legal,
    provider_scripts,
    provider_termination,
    public_app_info,
    public_payment,
    public_verify,
    recordings,
    super_audit,
    super_config,
    super_cost,
    super_health,
    super_plans,
    supervisor,
    supervisor_actions,
    supervisor_case_detail,
    supervisor_escalated,
    supervisor_extras,
    supervisor_labels,
    supervisor_live,
    supervisor_review,
    supervisor_shifts,
    supervisor_team_stats,
    tasks,
    tenant_legal_orders,
    user_preferences,
    users,
    work_orders,
    ws_calls,
    ws_supervisor,
)
from app.api import (
    me as me_api,
)
from app.api import (
    notifications as notifications_api,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    from app.core.crypto import _get_key
    from app.services.call_lifecycle import heartbeat_cleanup_loop
    from app.services.discount_expiry import discount_expiry_loop

    try:
        _get_key()
    except RuntimeError as exc:
        import sys

        print(f"FATAL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    # Sprint 14.2 — 启动通话心跳超时清理后台任务（90s 无心跳 → call.aborted）
    cleanup_task = asyncio.create_task(heartbeat_cleanup_loop())
    # v1.6 — 减免 offer 7 天有效期自动失效（每小时扫一次）
    discount_expiry_task = asyncio.create_task(discount_expiry_loop())
    try:
        yield
    finally:
        for task in (cleanup_task, discount_expiry_task):
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task


app = FastAPI(
    title="有证慧催 API",
    version="0.1.0",
    description="autoluyin MVP backend",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    # v2.2 — 兼容 LAN dev：localhost 任意端口 + 内网 IP（10/192.168/172.16-31）
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|host\.docker\.internal)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Error handlers ────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": f"ERR_{exc.status_code}", "message": str(exc.detail)},
    )


@app.middleware("http")
async def log_unauthorized(request: Request, call_next):
    # v2.2 调试：401 时打印 Authorization 头是否存在 + Origin
    response = await call_next(request)
    if response.status_code == 401 and "/agent/" in request.url.path:
        import logging
        auth = request.headers.get("authorization", "")
        origin = request.headers.get("origin", "")
        logging.warning(
            "AUTH401 path=%s authHdr=%s origin=%s",
            request.url.path,
            "Bearer:" + auth[7:19] + "..." if auth.startswith("Bearer ") else f"<{auth[:20]}>",
            origin,
        )
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    # v2.2 临时日志：打印 422 来源（path/loc/收到的 body），用于真机调试
    import logging
    # multipart 请求的流已被 FastAPI 解析消耗，不能再读 body；只对 JSON 请求记录原始 body
    content_type = request.headers.get("content-type", "")
    if "multipart/" in content_type or "application/x-www-form-urlencoded" in content_type:
        body_preview = "<multipart/form — body not logged>"
    else:
        try:
            body_bytes = await request.body()
            body_preview = body_bytes[:400].decode("utf-8", errors="replace") if body_bytes else ""
        except RuntimeError:
            body_preview = "<body unavailable>"
    logging.warning(
        "VAL_422 path=%s loc=%s msg=%s body=%s",
        request.url.path, first.get("loc"), first.get("msg"), body_preview,
    )
    loc = first.get("loc", ())
    loc_str = ".".join(str(x) for x in loc[1:]) if len(loc) > 1 else "?"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "ERR_VALIDATION",
            "message": f"[{loc_str}] {first.get('msg', 'Validation error')}",
        },
    )


# v2.2 临时调试端点：让 Android stock WebView 把客户端 JS 错误 POST 上来
# Chromium 53 没有 console 也没有 USB inspect 时，白屏只能这样捕获。
@app.post("/api/v1/_debug/client-error")
async def _debug_client_error(request: Request) -> dict:
    import logging
    try:
        body = await request.json()
    except Exception:
        body = {"raw": (await request.body()).decode("utf-8", errors="replace")[:1000]}
    logging.warning("CLIENT_JS_ERR %s", body)
    return {"received": True}


# 信标 GET（不触发 CORS preflight，用 Image src 调用）
@app.get("/api/v1/_debug/client-error-beacon")
async def _debug_client_error_beacon(request: Request) -> dict:
    import logging
    logging.warning("CLIENT_BEACON %s ua=%s", dict(request.query_params), request.headers.get("user-agent", "?"))
    return {"received": True}


# ── Routers ───────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(auth_extras.router, prefix="/api/v1/auth", tags=["auth-extras"])
app.include_router(me_api.router, prefix="/api/v1", tags=["me"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(ops.router, prefix="/api/v1/ops", tags=["ops"])
app.include_router(ops_providers.router, prefix="/api/v1/ops", tags=["ops-providers"])
app.include_router(ops_extras.router, prefix="/api/v1/ops", tags=["ops-extras"])
app.include_router(ops_law_firms.router, prefix="/api/v1/ops", tags=["ops-law-firms"])
app.include_router(
    ops_legal_packages.router, prefix="/api/v1/ops", tags=["ops-legal-packages"]
)
app.include_router(
    legal_workstation.router, prefix="/api/v1/legal-workstation", tags=["legal-workstation"]
)
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(admin_cases.router, prefix="/api/v1/admin", tags=["admin-cases"])
app.include_router(
    admin_legal_conversion.router, prefix="/api/v1/admin", tags=["admin-legal-conversion"]
)
app.include_router(
    admin_legal_internal_config.router, prefix="/api/v1/admin", tags=["admin-legal-internal-config"]
)
app.include_router(
    legal_conversion_requests.router, prefix="/api/v1", tags=["legal-conversion-requests"]
)
app.include_router(
    legal_internal_orders.router, prefix="/api/v1/legal", tags=["legal-internal-orders"]
)
app.include_router(admin_projects.router, prefix="/api/v1/admin", tags=["admin-projects"])
app.include_router(
    admin_project_members.router,
    prefix="/api/v1/admin",
    tags=["admin-project-members"],
)
app.include_router(admin_risk_keywords.router, prefix="/api/v1/admin", tags=["admin-risk-keywords"])
app.include_router(supervisor.router, prefix="/api/v1/supervisor", tags=["supervisor"])
app.include_router(agent_cases.router, prefix="/api/v1/agent", tags=["agent"])
app.include_router(agent_me.router, prefix="/api/v1/agent", tags=["agent-me"])
app.include_router(devices_v1.router, prefix="/api/v1/devices", tags=["devices-v1"])
app.include_router(calls_v1.router, prefix="/api/v1/calls", tags=["calls-v1"])
app.include_router(public_verify.router, prefix="/api/v1/public", tags=["public-verify"])
app.include_router(public_app_info.router, prefix="/api/v1/public", tags=["public-app-info"])
app.include_router(
    public_payment.router, prefix="/api/v1/public", tags=["public-payment"]
)
app.include_router(user_preferences.router, prefix="/api/v1/users", tags=["user-preferences"])
app.include_router(notifications_api.router, prefix="/api/v1/users", tags=["notifications"])
# Legacy PoC routers (Sprint 1 migrates these to ORM + /api/v1/ prefix)
app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(calls.router, prefix="/api/calls", tags=["calls"])
app.include_router(recordings.router, prefix="/api/recordings", tags=["recordings"])
app.include_router(ws_calls.router)  # no prefix — /ws/calls/{id} stays as-is
app.include_router(ws_supervisor.router)  # /ws/supervisor
app.include_router(admin_scripts.router, prefix="/api/v1/admin", tags=["admin-scripts"])
app.include_router(admin_dashboard.router, prefix="/api/v1/admin", tags=["admin-dashboard"])
app.include_router(
    admin_agent_devices.router,
    prefix="/api/v1/admin",
    tags=["admin-agent-devices"],
)
app.include_router(
    supervisor_labels.router, prefix="/api/v1/supervisor", tags=["supervisor-labels"]
)
app.include_router(
    supervisor_review.router, prefix="/api/v1/supervisor", tags=["supervisor-review"]
)
app.include_router(supervisor_live.router, prefix="/api/v1/supervisor", tags=["supervisor-live"])
app.include_router(
    supervisor_extras.router, prefix="/api/v1/supervisor", tags=["supervisor-extras"]
)
app.include_router(
    supervisor_case_detail.router, prefix="/api/v1/supervisor", tags=["supervisor-case-detail"]
)
app.include_router(
    supervisor_actions.router, prefix="/api/v1/supervisor", tags=["supervisor-actions"]
)
app.include_router(
    supervisor_shifts.router, prefix="/api/v1/supervisor", tags=["supervisor-shifts"]
)
app.include_router(
    supervisor_team_stats.router, prefix="/api/v1/supervisor", tags=["supervisor-team-stats"]
)
app.include_router(
    supervisor_escalated.router, prefix="/api/v1/supervisor", tags=["supervisor-escalated"]
)
app.include_router(lawfirm_orders.router, prefix="/api/v1/lawfirm", tags=["lawfirm-orders"])
app.include_router(lawyer_orders.router, prefix="/api/v1/lawyer", tags=["lawyer-orders"])
app.include_router(tenant_legal_orders.router, prefix="/api/v1/legal", tags=["tenant-legal-orders"])
# v1.6 — 协商打折 / 减免审批
app.include_router(discount_offers.router, prefix="/api/v1", tags=["discount-offers"])
app.include_router(
    admin_suggestion_config.router, prefix="/api/v1/admin", tags=["suggestion-config"]
)
app.include_router(admin_settlements.router, prefix="/api/v1/admin", tags=["admin-settlements"])
app.include_router(admin_providers.router, prefix="/api/v1/admin", tags=["admin-providers"])
app.include_router(
    admin_provider_recommendation.router,
    prefix="/api/v1/admin",
    tags=["admin-provider-recommendation"],
)
app.include_router(admin_reports.router, prefix="/api/v1/admin", tags=["admin-reports"])
app.include_router(admin_compliance.router, prefix="/api/v1/admin", tags=["admin-compliance"])
app.include_router(admin_settings.router, prefix="/api/v1/admin", tags=["admin-settings"])
app.include_router(legal_cases.router, prefix="/api/v1/legal", tags=["legal"])
app.include_router(legal_documents.router, prefix="/api/v1/legal", tags=["legal-documents"])
app.include_router(
    provider_legal.router, prefix="/api/v1/provider/legal", tags=["provider-legal"]
)
app.include_router(work_orders.router, prefix="/api/v1/workorders", tags=["workorders"])
app.include_router(pm_dashboard.router, prefix="/api/v1/pm", tags=["pm"])
app.include_router(provider_admin.router, prefix="/api/v1/provider", tags=["provider"])
app.include_router(provider_cases.router, prefix="/api/v1/provider", tags=["provider-cases"])
app.include_router(provider_scripts.router, prefix="/api/v1/provider", tags=["provider-scripts"])
app.include_router(
    provider_termination.admin_router,
    prefix="/api/v1/admin",
    tags=["provider-termination"],
)
app.include_router(
    provider_termination.provider_router,
    prefix="/api/v1/provider",
    tags=["provider-termination"],
)
app.include_router(super_audit.router, prefix="/api/v1/super", tags=["super-audit"])
app.include_router(super_health.router, prefix="/api/v1/super", tags=["super-health"])
app.include_router(super_cost.router, prefix="/api/v1/super", tags=["super-cost"])
app.include_router(super_plans.router, prefix="/api/v1/super", tags=["super-plans"])
app.include_router(super_config.router, prefix="/api/v1/super", tags=["super-config"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
