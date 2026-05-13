"""Xiaomi MiPush HTTP backend — production use only."""

from __future__ import annotations

import json
import logging

import httpx

logger = logging.getLogger(__name__)


class XiaomiMiPushClient:
    URL = "https://api.xmpush.xiaomi.com/v3/message/regid"

    def __init__(self, app_secret: str, package_name: str) -> None:
        if not app_secret:
            raise RuntimeError("MIPUSH_APP_SECRET is required for xiaomi backend")
        self._app_secret = app_secret
        self._package_name = package_name

    async def send_to_user(
        self,
        reg_id: str,
        payload: dict,
        title: str,
        description: str,
    ) -> None:
        async with httpx.AsyncClient(timeout=5) as cli:
            resp = await cli.post(
                self.URL,
                headers={"Authorization": f"key={self._app_secret}"},
                data={
                    "registration_id": reg_id,
                    "restricted_package_name": self._package_name,
                    "payload": json.dumps(payload),
                    "title": title,
                    "description": description,
                    "pass_through": "0",
                    "notify_type": "-1",
                },
            )
            resp.raise_for_status()
            body = resp.json()
            if body.get("result") != "ok":
                logger.error("mipush failed: %s", body)
                raise RuntimeError(f"MiPush API error: {body}")
