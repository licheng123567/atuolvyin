"""Sprint 14.3 — 公开 App 下载信息 (PRD §8.2)。

GET /api/v1/public/app-info  无需认证

返回当前部署版本的 APK 下载链接 + 推荐手机要求。
前端 Help 页生成二维码用，引导手机端扫描下载。

部署时通过环境变量 AUTOLUYIN_APK_URL 注入；缺省给开发占位 URL。
"""

from __future__ import annotations

import os

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class AppInfoOut(BaseModel):
    apk_url: str
    apk_version: str
    min_android_version: str
    download_size_mb: float
    notes: str


@router.get("/app-info", response_model=AppInfoOut)
def get_app_info() -> AppInfoOut:
    return AppInfoOut(
        apk_url=os.getenv(
            "AUTOLUYIN_APK_URL",
            "https://example.invalid/autoluyin-app-debug.apk",
        ),
        apk_version=os.getenv("AUTOLUYIN_APK_VERSION", "0.1.0-dev"),
        min_android_version="Android 8.0 (API 26)",
        download_size_mb=32.0,
        notes=(
            "首次安装后请在系统设置中开启「电话」「通话录音」「通知」「相机」"
            "「读取媒体音频」权限。MIUI 设备需额外开启「所有文件访问权限」"
            "以读取通话录音目录。"
        ),
    )
