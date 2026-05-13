"""v2.1 — 设备录音能力静态矩阵 + 派生函数 (PRD § 8.4)。

判定流程：
  1. derive_rom_family(manufacturer) → "miui" / "emui" / "coloros" / "originos" / "aosp_international"
  2. parse_android_major(android_version) → int (e.g. "9.0" → 9, "10" → 10)
  3. CAPABILITY_MATRIX[(rom_family, android_major)] → CapabilityLevel
  4. 国际/海外品牌（manufacturer == "Google" 等）一律视为 aosp_international → 降级

如果 last_recording_scan_failed=True，调用方应直接降级 incompatible（覆盖矩阵）。
此降级逻辑放在调用方（self-check endpoint），本 service 只做静态判定。
"""
from __future__ import annotations

from typing import Literal

CapabilityLevel = Literal["realtime", "post_upload", "incompatible"]

# ROM family 识别（manufacturer 字段从 Build.MANUFACTURER 来，全小写比较）
_ROM_FAMILY_MAP: dict[str, str] = {
    "xiaomi": "miui",
    "redmi": "miui",
    "blackshark": "miui",
    "huawei": "emui",
    # 早期荣耀也算 emui，2020+ 独立后实际是 magic os 但兼容 emui 行为
    "honor": "emui",
    "oppo": "coloros",
    "realme": "coloros",
    # 2021+ OnePlus 用 ColorOS
    "oneplus": "coloros",
    "vivo": "originos",
    "iqoo": "originos",
    "google": "aosp_international",
    "pixel": "aosp_international",
    # 海外/国际版默认；国行三星 (sm-* 国内型号) 可能保留录音但简化处理
    "samsung": "aosp_international",
    "motorola": "aosp_international",
    "sony": "aosp_international",
    "nokia": "aosp_international",
}

# (rom_family, android_major) → CapabilityLevel
# 矩阵 1:1 对齐 PRD § 8.4.2
_CAPABILITY_MATRIX: dict[tuple[str, int], CapabilityLevel] = {}

# 国行 ROM 家族：6/7/8/9/10 全 realtime；11+ 退化到 post_upload
for _rom in ("miui", "emui", "coloros", "originos"):
    _CAPABILITY_MATRIX[(_rom, 6)] = "realtime"
    _CAPABILITY_MATRIX[(_rom, 7)] = "realtime"
    _CAPABILITY_MATRIX[(_rom, 8)] = "realtime"
    _CAPABILITY_MATRIX[(_rom, 9)] = "realtime"
    _CAPABILITY_MATRIX[(_rom, 10)] = "realtime"
    _CAPABILITY_MATRIX[(_rom, 11)] = "post_upload"
    _CAPABILITY_MATRIX[(_rom, 12)] = "post_upload"
    _CAPABILITY_MATRIX[(_rom, 13)] = "post_upload"
    _CAPABILITY_MATRIX[(_rom, 14)] = "post_upload"
    _CAPABILITY_MATRIX[(_rom, 15)] = "post_upload"

# 海外/Pixel 系：6/7 realtime（早期 AOSP 无封禁），8+ incompatible
for _ver in (6, 7):
    _CAPABILITY_MATRIX[("aosp_international", _ver)] = "realtime"
for _ver in (8, 9, 10, 11, 12, 13, 14, 15):
    _CAPABILITY_MATRIX[("aosp_international", _ver)] = "incompatible"


def derive_rom_family(manufacturer: str | None) -> str:
    """从 Build.MANUFACTURER 推断 ROM 家族。空 / 未知 → 'aosp_international'。"""
    if not manufacturer:
        return "aosp_international"
    key = manufacturer.strip().lower()
    return _ROM_FAMILY_MAP.get(key, "aosp_international")


def parse_android_major(android_version: str | None) -> int | None:
    """'9.0' → 9, '10' → 10, '14.0.1' → 14。失败返回 None。"""
    if not android_version:
        return None
    try:
        major_str = android_version.strip().split(".")[0]
        major = int(major_str)
        if 1 <= major <= 99:
            return major
    except (ValueError, IndexError):
        pass
    return None


def derive_capability(
    manufacturer: str | None,
    android_version: str | None,
) -> CapabilityLevel:
    """静态矩阵判定。任何识别失败默认 'post_upload'（保守不极端，让 UI 提示 + 用户自报）。"""
    family = derive_rom_family(manufacturer)
    major = parse_android_major(android_version)
    if major is None:
        # 无法解析 Android 版本：保守按 post_upload 让用户知情但不阻断
        return "post_upload"
    if major < 6:
        # 太老的 Android (< 6) 没在 PRD 矩阵；保守降级
        return "post_upload"
    if major > 15:
        # 矩阵未覆盖的未来版本：用最新行 (15) 兜底
        major = 15
    return _CAPABILITY_MATRIX.get((family, major), "post_upload")


def derive_rom_label(
    manufacturer: str | None,
    model: str | None,
    android_version: str | None,
) -> str:
    """生成展示用的 ROM 标签。如 'MIUI on Xiaomi Mi 9 (Android 10.0)'。"""
    family = derive_rom_family(manufacturer)
    family_display = {
        "miui": "MIUI",
        "emui": "EMUI",
        "coloros": "ColorOS",
        "originos": "OriginOS",
        "aosp_international": "AOSP",
    }.get(family, family.upper())
    parts: list[str] = [family_display]
    if model:
        parts.append(f"on {manufacturer or '?'} {model}".strip())
    if android_version:
        parts.append(f"(Android {android_version})")
    return " ".join(parts)
