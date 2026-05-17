"""api_smoke.py — 11 角色 API 冒烟测试.

用法（容器内）:
    docker exec -e BACKEND_URL=http://localhost:8000 autoluyin-backend python -m scripts.api_smoke

用法（宿主机调用容器内）:
    docker exec autoluyin-backend python -m scripts.api_smoke

环境变量:
    BACKEND_URL — 后端根 URL（默认 http://localhost:8000）
"""
from __future__ import annotations

import os
import sys
from typing import NamedTuple

import httpx

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")

DEMO_PASSWORD = "Demo@123!"

# 角色 → (手机号, 测试端点)
# 平台账号的 role 来自 platform_role 字段（superadmin/ops），无 membership
ROLES: list[tuple[str, str, str]] = [
    ("superadmin",                "13000000000", "/api/v1/super/health/services"),
    ("ops",                       "13000000001", "/api/v1/ops/tenants?page=1"),
    ("admin",                     "13000000002", "/api/v1/admin/dashboard/stats"),
    ("supervisor",                "13000000003", "/api/v1/supervisor/reviews?only_pending=false"),
    ("agent",                     "13000000004", "/api/v1/calls/?page=1"),
    ("agent",                     "13000000005", "/api/v1/calls/?page=1"),
    # 批 3 新增 5 角色
    ("legal",                     "13000000006", "/api/v1/legal/cases?page=1"),
    ("coordinator",               "13000000007", "/api/v1/workorders?page=1"),
    ("project_manager",           "13000000008", "/api/v1/pm/dashboard/property"),
    ("project_manager",           "13000000009", "/api/v1/pm/dashboard/provider"),
    ("admin",                     "13000000010", "/api/v1/provider/dashboard/stats"),
    # 新增服务商催收员 + 督导
    ("agent",                     "13000000011", "/api/v1/calls/?page=1"),
    ("supervisor",                "13000000012", "/api/v1/calls/?page=1"),
]


class SmokeResult(NamedTuple):
    role: str
    phone: str
    login_status: int
    api_endpoint: str
    api_status: int
    passed: bool
    detail: str


def smoke_role(
    client: httpx.Client, role: str, phone: str, endpoint: str
) -> SmokeResult:
    # Step 1: login
    login_url = f"{BASE_URL}/api/v1/auth/login"
    try:
        r = client.post(login_url, json={"phone": phone, "password": DEMO_PASSWORD}, timeout=10)
        login_status = r.status_code
    except httpx.RequestError as exc:
        return SmokeResult(
            role=role, phone=phone,
            login_status=0, api_endpoint=endpoint,
            api_status=0, passed=False,
            detail=f"LOGIN CONNECT ERROR: {exc}",
        )

    if login_status != 200:
        return SmokeResult(
            role=role, phone=phone,
            login_status=login_status, api_endpoint=endpoint,
            api_status=0, passed=False,
            detail=f"LOGIN FAILED: {r.text[:300]}",
        )

    data = r.json()
    token = data.get("access_token", "")
    actual_role = data.get("role", "?")

    # Step 2: call role API
    api_url = f"{BASE_URL}{endpoint}"
    try:
        ar = client.get(api_url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        api_status = ar.status_code
    except httpx.RequestError as exc:
        return SmokeResult(
            role=role, phone=phone,
            login_status=login_status, api_endpoint=endpoint,
            api_status=0, passed=False,
            detail=f"API CONNECT ERROR: {exc}",
        )

    passed = api_status == 200
    if passed:
        detail = f"login_role={actual_role}"
    else:
        detail = f"login_role={actual_role}  API ERROR: {ar.text[:300]}"

    return SmokeResult(
        role=role, phone=phone,
        login_status=login_status, api_endpoint=endpoint,
        api_status=api_status, passed=passed,
        detail=detail,
    )


def print_results(results: list[SmokeResult]) -> int:
    """Print summary table. Return exit code (0=all pass, 1=any fail)."""
    PASS = "✅"
    FAIL = "❌"

    col_role = max(len(r.role) for r in results) + 2
    col_phone = 14
    col_ep = max(len(r.api_endpoint) for r in results) + 2

    header = (
        f"{'角色':<{col_role}}"
        f"{'手机号':<{col_phone}}"
        f"{'登录':>6}"
        f"{'API端点':<{col_ep}}"
        f"{'状态':>6}"
        f"  结果"
    )
    sep = "-" * len(header)
    print("\n" + sep)
    print("API 冒烟测试汇总")
    print(sep)
    print(header)
    print(sep)

    any_fail = False
    for r in results:
        status_icon = PASS if r.passed else FAIL
        row = (
            f"{r.role:<{col_role}}"
            f"{r.phone:<{col_phone}}"
            f"{r.login_status:>6}"
            f"{r.api_endpoint:<{col_ep}}"
            f"{r.api_status:>6}"
            f"  {status_icon}"
        )
        print(row)
        if not r.passed:
            any_fail = True
            print(f"  ↳ DETAIL: {r.detail}")

    print(sep)
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    print(f"通过: {passed}/{total}")
    print(sep + "\n")

    return 1 if any_fail else 0


def main() -> None:
    print(f"API 冒烟测试 — 目标: {BASE_URL}")
    print(f"角色数: {len(ROLES)}")

    results: list[SmokeResult] = []
    with httpx.Client() as client:
        for role, phone, endpoint in ROLES:
            print(f"  测试 [{role}] {phone} → {endpoint} ...", end=" ", flush=True)
            result = smoke_role(client, role, phone, endpoint)
            icon = "✅" if result.passed else "❌"
            print(icon)
            if not result.passed:
                print(f"    DETAIL: {result.detail}")
            results.append(result)

    exit_code = print_results(results)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
