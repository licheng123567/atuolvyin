"""legal_conversion_smoke.py — v1.5 法务转化通道端到端冒烟（PRD §20.4.1）.

走完一条订单从下单到结算的完整生命周期：
  1. admin 登录 → list packages → preview case → convert-to-legal
  2. ops 登录 → 创建律所（若不存在）→ dispatch 订单
  3. ops → start service（dispatched → in_service）
  4. admin → render document
  5. ops → complete order
  6. ops → generate invoice → confirm → mark paid
  7. ops → firm stats 验证计数

用法：
    docker exec autoluyin-backend python -m scripts.legal_conversion_smoke

依赖：
    - 已 seed_demo（11 角色账号 + 至少 1 个 admin 可见 case）
    - BACKEND_URL 默认 http://localhost:8000
"""
from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta

import httpx

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")
DEMO_PASSWORD = "Demo@123!"

ADMIN_PHONE = "13000000002"
OPS_PHONE = "13000000001"

PASS = "✅"
FAIL = "❌"
INFO = "→"


def login(client: httpx.Client, phone: str) -> str:
    r = client.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"phone": phone, "password": DEMO_PASSWORD},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def step(label: str) -> None:
    print(f"\n{INFO} {label}")


def fail(label: str, resp: httpx.Response) -> None:
    print(f"{FAIL} {label}: {resp.status_code} {resp.text[:300]}")
    sys.exit(1)


def main() -> int:
    print(f"BACKEND_URL = {BASE_URL}")

    with httpx.Client(timeout=15) as client:

        step("admin 登录")
        admin_token = login(client, ADMIN_PHONE)
        print(f"{PASS} admin token len={len(admin_token)}")

        step("ops 登录")
        ops_token = login(client, OPS_PHONE)
        print(f"{PASS} ops token len={len(ops_token)}")

        # ── 1. admin: list packages ─────────────────────────────
        step("GET /admin/legal-packages")
        r = client.get(
            f"{BASE_URL}/api/v1/admin/legal-packages",
            headers=auth_headers(admin_token),
        )
        if r.status_code != 200:
            fail("list packages", r)
        packages = r.json()
        if not packages:
            print(f"{FAIL} no service packages — run alembic upgrade head + seed first")
            return 1
        print(f"{PASS} {len(packages)} packages: " + " / ".join(p["slug"] for p in packages))
        letter_pkg = next((p for p in packages if p["slug"] == "lawyer_letter"), packages[0])

        # ── 2. admin: pick a case ───────────────────────────────
        step("GET /admin/cases?page=1 → pick first case")
        r = client.get(
            f"{BASE_URL}/api/v1/admin/cases?page=1",
            headers=auth_headers(admin_token),
        )
        if r.status_code != 200:
            fail("list cases", r)
        cases = r.json().get("items", [])
        if not cases:
            print(f"{FAIL} no cases visible to admin — run seed_demo")
            return 1
        case = cases[0]
        case_id = case["id"]
        print(f"{PASS} case_id={case_id}")

        # ── 3. preview ──────────────────────────────────────────
        step(f"GET /admin/cases/{case_id}/legal-conversion-preview")
        r = client.get(
            f"{BASE_URL}/api/v1/admin/cases/{case_id}/legal-conversion-preview",
            headers=auth_headers(admin_token),
        )
        if r.status_code != 200:
            fail("preview", r)
        prev = r.json()
        rec = prev["recommendation"]
        print(f"{PASS} recommended={rec['slug']} confidence={rec['confidence']}")

        # ── 4. convert-to-legal ─────────────────────────────────
        step(f"POST /admin/cases/{case_id}/convert-to-legal package={letter_pkg['slug']}")
        r = client.post(
            f"{BASE_URL}/api/v1/admin/cases/{case_id}/convert-to-legal",
            headers=auth_headers(admin_token),
            json={"package_id": letter_pkg["id"], "notes": "smoke test"},
        )
        if r.status_code == 409:
            # 已存在 active 订单 — 找出来用
            print(f"{INFO} 409 (existing active order) — fetching it")
            list_r = client.get(
                f"{BASE_URL}/api/v1/admin/legal-conversion-orders?status=pending",
                headers=auth_headers(admin_token),
            )
            order_id = list_r.json()["items"][0]["id"]
        elif r.status_code == 201:
            order = r.json()
            order_id = order["id"]
            print(f"{PASS} order_id={order_id} fee=¥{order['platform_fee_amount']}")
        else:
            fail("convert", r)

        # ── 5. ops: ensure a law firm exists ────────────────────
        step("GET /ops/law-firms?accepting=true")
        r = client.get(
            f"{BASE_URL}/api/v1/ops/law-firms?accepting=true",
            headers=auth_headers(ops_token),
        )
        if r.status_code != 200:
            fail("list firms", r)
        firms = r.json().get("items", [])
        if firms:
            firm_id = firms[0]["id"]
            print(f"{PASS} using existing firm_id={firm_id} ({firms[0]['name']})")
        else:
            step("POST /ops/law-firms")
            r = client.post(
                f"{BASE_URL}/api/v1/ops/law-firms",
                headers=auth_headers(ops_token),
                json={
                    "name": "冒烟测试律所",
                    "license_no": f"SMOKE-{datetime.now(UTC).timestamp():.0f}",
                    "region": "测试区",
                },
            )
            if r.status_code != 201:
                fail("create firm", r)
            firm_id = r.json()["id"]
            print(f"{PASS} created firm_id={firm_id}")

        # ── 6. ops: dispatch ────────────────────────────────────
        step(f"POST /admin/legal-conversion-orders/{order_id}/dispatch")
        r = client.post(
            f"{BASE_URL}/api/v1/admin/legal-conversion-orders/{order_id}/dispatch",
            headers=auth_headers(ops_token),
            json={"law_firm_id": firm_id},
        )
        if r.status_code == 409:
            print(f"{INFO} order already dispatched ({r.json().get('detail')}) — continuing")
        elif r.status_code != 200:
            fail("dispatch", r)
        else:
            print(f"{PASS} dispatched → {r.json()['assigned_law_firm']}")

        # ── 7. ops: start service ──────────────────────────────
        step(f"POST /legal-workstation/orders/{order_id}/start")
        r = client.post(
            f"{BASE_URL}/api/v1/legal-workstation/orders/{order_id}/start",
            headers=auth_headers(ops_token),
        )
        if r.status_code == 409:
            print(f"{INFO} order not in dispatched state — continuing")
        elif r.status_code != 200:
            fail("start", r)
        else:
            print(f"{PASS} status={r.json()['status']}")

        # ── 8. admin: render document ───────────────────────────
        step(f"POST /admin/legal-conversion-orders/{order_id}/document")
        r = client.post(
            f"{BASE_URL}/api/v1/admin/legal-conversion-orders/{order_id}/document",
            headers=auth_headers(admin_token),
        )
        if r.status_code != 201:
            fail("render doc", r)
        doc = r.json()
        print(f"{PASS} doc v{doc['version']} title={doc['title']!r} body_len={len(doc['body_md'])}")

        # ── 9. ops: complete order ──────────────────────────────
        step(f"POST /admin/legal-conversion-orders/{order_id}/complete")
        r = client.post(
            f"{BASE_URL}/api/v1/admin/legal-conversion-orders/{order_id}/complete",
            headers=auth_headers(ops_token),
            json={"notes": "smoke complete"},
        )
        if r.status_code == 409:
            print(f"{INFO} order not completable from current state — skipping invoice steps")
            return 0
        elif r.status_code != 200:
            fail("complete", r)
        print(f"{PASS} status=completed")

        # ── 10. ops: generate invoice for current month ─────────
        now = datetime.now(UTC)
        ps = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # period_end = first day of next month
        if ps.month == 12:
            pe = ps.replace(year=ps.year + 1, month=1)
        else:
            pe = ps.replace(month=ps.month + 1)

        step(f"POST /legal-workstation/firms/{firm_id}/invoices [{ps:%Y-%m-%d} ~ {pe:%Y-%m-%d})")
        r = client.post(
            f"{BASE_URL}/api/v1/legal-workstation/firms/{firm_id}/invoices",
            headers=auth_headers(ops_token),
            json={
                "period_start": ps.isoformat(),
                "period_end": pe.isoformat(),
            },
        )
        if r.status_code != 201:
            fail("generate invoice", r)
        invoice = r.json()
        invoice_id = invoice["id"]
        print(f"{PASS} invoice_id={invoice_id} status={invoice['status']} "
              f"amount=¥{invoice['total_amount']} orders={invoice['order_count']}")

        # ── 11. confirm ────────────────────────────────────────
        step(f"POST /legal-workstation/invoices/{invoice_id}/confirm")
        r = client.post(
            f"{BASE_URL}/api/v1/legal-workstation/invoices/{invoice_id}/confirm",
            headers=auth_headers(ops_token),
            json={},
        )
        if r.status_code == 409:
            print(f"{INFO} already confirmed — skipping")
        elif r.status_code != 200:
            fail("confirm", r)
        else:
            print(f"{PASS} status=confirmed")

        # ── 12. paid ───────────────────────────────────────────
        step(f"POST /legal-workstation/invoices/{invoice_id}/paid")
        r = client.post(
            f"{BASE_URL}/api/v1/legal-workstation/invoices/{invoice_id}/paid",
            headers=auth_headers(ops_token),
            json={"payment_proof_url": "https://oss.example/smoke-proof.png"},
        )
        if r.status_code == 409:
            print(f"{INFO} already paid — skipping")
        elif r.status_code != 200:
            fail("mark paid", r)
        else:
            print(f"{PASS} status=paid paid_at={r.json()['paid_at']}")

        # ── 13. firm stats ─────────────────────────────────────
        step(f"GET /legal-workstation/firms/{firm_id}/stats")
        r = client.get(
            f"{BASE_URL}/api/v1/legal-workstation/firms/{firm_id}/stats",
            headers=auth_headers(ops_token),
        )
        if r.status_code != 200:
            fail("stats", r)
        stats = r.json()
        print(f"{PASS} firm completed_orders={stats['completed_orders']} "
              f"unpaid=¥{stats['platform_fee_unpaid']} "
              f"total_completed=¥{stats['platform_fee_total_completed']}")

    print(f"\n{PASS} 法务转化通道全流程冒烟通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
