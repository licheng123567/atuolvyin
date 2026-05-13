"""v2.1 Task 1 单元测试 — 静态矩阵覆盖 8 个典型机型 + 边界 case。"""
from __future__ import annotations

import pytest

from app.services.device_capability import (
    derive_capability,
    derive_rom_family,
    derive_rom_label,
    parse_android_major,
)


class TestDeriveRomFamily:
    @pytest.mark.parametrize(
        "mfr,expected",
        [
            ("Xiaomi", "miui"),
            ("xiaomi", "miui"),
            ("Redmi", "miui"),
            ("HUAWEI", "emui"),
            ("HONOR", "emui"),
            ("OPPO", "coloros"),
            ("realme", "coloros"),
            ("vivo", "originos"),
            ("iQOO", "originos"),
            ("Google", "aosp_international"),
            ("Samsung", "aosp_international"),
            ("UnknownBrand", "aosp_international"),
            (None, "aosp_international"),
            ("", "aosp_international"),
        ],
    )
    def test_rom_family_recognition(self, mfr, expected):
        assert derive_rom_family(mfr) == expected


class TestParseAndroidMajor:
    @pytest.mark.parametrize(
        "ver,expected",
        [
            ("9", 9),
            ("9.0", 9),
            ("9.0.1", 9),
            ("10", 10),
            ("14.0.1", 14),
            ("6.0.1", 6),
            ("invalid", None),
            ("", None),
            (None, None),
            # 不在 1-99 范围
            ("0", None),
        ],
    )
    def test_parse_major(self, ver, expected):
        assert parse_android_major(ver) == expected


class TestDeriveCapability:
    """8 组典型机型 + 边界 case。"""

    @pytest.mark.parametrize(
        "mfr,ver,expected",
        [
            # MIUI 10/11 era — 实时
            ("Xiaomi", "9", "realtime"),
            ("Xiaomi", "10", "realtime"),
            # MIUI 12+ era — 事后上传
            ("Xiaomi", "12", "post_upload"),
            ("Xiaomi", "14", "post_upload"),
            # EMUI 9 国行 — 实时
            ("HUAWEI", "9", "realtime"),
            # ColorOS 12 — 事后
            ("OPPO", "12", "post_upload"),
            # Pixel/AOSP 14 — 不可用
            ("Google", "14", "incompatible"),
            # 三星海外 — 不可用
            ("Samsung", "12", "incompatible"),
            # 早期 Android 6/7 — 全实时
            ("Xiaomi", "6", "realtime"),
            ("HUAWEI", "7", "realtime"),
            # AOSP 早期也实时
            ("Google", "6", "realtime"),
            ("Google", "7", "realtime"),
            # 边界：未知 mfr + Android 9 → aosp_international + 8+ → incompatible
            ("UnknownBrand", "9", "incompatible"),
            # 边界：Android 版本无法解析 → post_upload (保守)
            ("Xiaomi", None, "post_upload"),
            ("Xiaomi", "invalid", "post_upload"),
            # 边界：mfr 缺失 + Android 14 → aosp_international 14 → incompatible
            (None, "14", "incompatible"),
            # 边界：未来版本 (Android 16) → 用 15 兜底
            ("Xiaomi", "16", "post_upload"),
            # 边界：太老 Android 5 → post_upload
            ("Xiaomi", "5", "post_upload"),
        ],
    )
    def test_capability(self, mfr, ver, expected):
        assert derive_capability(mfr, ver) == expected


class TestDeriveRomLabel:
    def test_full_label(self):
        label = derive_rom_label("Xiaomi", "Mi 9", "10.0")
        assert "MIUI" in label
        assert "Xiaomi" in label
        assert "Mi 9" in label
        assert "10.0" in label

    def test_partial_label_missing_model(self):
        label = derive_rom_label("Xiaomi", None, "10")
        assert "MIUI" in label
        assert "Android 10" in label

    def test_partial_label_only_mfr(self):
        label = derive_rom_label("Xiaomi", None, None)
        assert label == "MIUI"

    def test_unknown_mfr(self):
        label = derive_rom_label("UnknownBrand", "X1", "12")
        assert "AOSP" in label
