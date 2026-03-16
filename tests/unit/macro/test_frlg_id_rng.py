"""
FRLG ID調整マクロ テスト

frame_sweep / keyboard_layout / tid_recognizer / メインマクロクラスの
ユニットテストを提供する。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ============================================================
# frame_sweep テスト
# ============================================================

from frlg_id_rng.frame_sweep import (
    dual_frame_sweep,
    frame_sweep,
    single_value_iterator,
)


class TestFrameSweep:
    """frame_sweep ジェネレータのテスト"""

    def test_basic_sweep(self):
        """min から max まで 1 ずつ列挙される"""
        result = list(frame_sweep(10, 13))
        assert result == [10, 11, 12, 13]

    def test_single_value(self):
        """min == max の場合、値が1つだけ返る"""
        result = list(frame_sweep(5, 5))
        assert result == [5]

    def test_step_3(self):
        """step=3 で動作する"""
        result = list(frame_sweep(0, 6, step=3))
        assert result == [0, 3, 6]

    def test_dual_sweep(self):
        """2軸スイープが Frame1 外側 × Frame2 内側で列挙される"""
        result = list(dual_frame_sweep(10, 12, 20, 22))
        # Frame1=10: (10,20),(10,21),(10,22)
        # Frame1=11: (11,20),(11,21),(11,22)
        # Frame1=12: (12,20),(12,21),(12,22)
        assert (10, 20) == result[0]
        assert (10, 21) == result[1]
        assert (10, 22) == result[2]
        assert (11, 20) == result[3]
        assert len(result) == 9

    def test_single_value_iterator(self):
        """固定値イテレータが無限に同じ値を返す"""
        it = single_value_iterator(42.0)
        for _ in range(5):
            assert next(it) == 42.0


# ============================================================
# keyboard_layout テスト
# ============================================================

from frlg_id_rng.keyboard_layout import (
    JPN_KEYBOARD,
    ENG_KEYBOARD,
    FRA_KEYBOARD,
    NOE_KEYBOARD,
    REGION_KEYBOARDS,
    find_char_in_keyboard,
)


class TestKeyboardLayout:
    """キーボードレイアウトのテスト"""

    def test_jpn_find_hiragana(self):
        """JPN: ひらがなモードで 'あ' が見つかる"""
        result = find_char_in_keyboard(JPN_KEYBOARD, "あ")
        assert result is not None
        mode, x, y = result
        assert mode == 0  # ひらがなモード
        assert x == 0
        assert y == 0

    def test_jpn_find_katakana(self):
        """JPN: カタカナモードで 'ア' が見つかる"""
        result = find_char_in_keyboard(JPN_KEYBOARD, "ア")
        assert result is not None
        mode, _, _ = result
        assert mode == 1  # カタカナモード

    def test_jpn_find_alnum(self):
        """JPN: 英数字モードで 'A' が見つかる"""
        result = find_char_in_keyboard(JPN_KEYBOARD, "A")
        assert result is not None
        mode, x, y = result
        assert mode == 2  # 英数字モード
        assert x == 0
        assert y == 0

    def test_jpn_dakuten_map(self):
        """JPN: 濁点マップに 'が' → 'か' が含まれる"""
        assert JPN_KEYBOARD.dakuten_map is not None
        assert JPN_KEYBOARD.dakuten_map["が"] == "か"

    def test_jpn_handakuten_map(self):
        """JPN: 半濁点マップに 'ぱ' → 'は' が含まれる"""
        assert JPN_KEYBOARD.handakuten_map is not None
        assert JPN_KEYBOARD.handakuten_map["ぱ"] == "は"

    def test_eng_find_upper(self):
        """ENG: 大文字 'A' が見つかる"""
        result = find_char_in_keyboard(ENG_KEYBOARD, "A")
        assert result is not None
        mode, x, y = result
        assert mode == 0
        assert x == 0
        assert y == 0

    def test_eng_find_digit(self):
        """ENG: 数字モードで '5' が見つかる"""
        result = find_char_in_keyboard(ENG_KEYBOARD, "5")
        assert result is not None
        mode, _, _ = result
        assert mode == 2  # 数字記号モード

    def test_region_keyboards_all_regions(self):
        """全リージョンのキーボードが定義されている"""
        expected = {"JPN", "ENG", "ESP", "ITA", "FRA", "NOE"}
        assert set(REGION_KEYBOARDS.keys()) == expected

    def test_unknown_char_returns_none(self):
        """存在しない文字は None を返す"""
        result = find_char_in_keyboard(ENG_KEYBOARD, "漢")
        assert result is None


# ============================================================
# region_timing テスト
# ============================================================

from frlg_id_rng.region_timing import REGION_TIMINGS, RegionTiming


class TestRegionTiming:
    """リージョン別タイミングデータのテスト"""

    def test_all_regions_defined(self):
        """全6リージョンが定義されている"""
        expected = {"JPN", "ENG", "FRA", "ITA", "ESP", "NOE"}
        assert set(REGION_TIMINGS.keys()) == expected

    @pytest.mark.parametrize(
        "region,offset",
        [
            ("JPN", 143),
            ("ENG", 198),
            ("FRA", 154),
            ("ITA", 185),
            ("ESP", 151),
            ("NOE", 157),
        ],
    )
    def test_frame3_offsets(self, region: str, offset: float):
        """Frame3 補正値が仕様どおり"""
        assert REGION_TIMINGS[region].frame3_offset == offset

    def test_jpn_game_start_wait(self):
        """JPN のゲーム開始待機は 5.0s"""
        assert REGION_TIMINGS["JPN"].game_start_wait == 5.0

    @pytest.mark.parametrize("region", ["ENG", "FRA", "ITA", "ESP", "NOE"])
    def test_non_jpn_game_start_wait(self, region: str):
        """JPN 以外のゲーム開始待機は 6.5s"""
        assert REGION_TIMINGS[region].game_start_wait == 6.5

    def test_timing_is_frozen(self):
        """RegionTiming は frozen dataclass"""
        timing = REGION_TIMINGS["JPN"]
        with pytest.raises(AttributeError):
            timing.frame3_offset = 999  # type: ignore[misc]


# ============================================================
# FrlgIdRngMacro テスト
# ============================================================

# macros/frlg_id_rng/ パッケージからインポート
from frlg_id_rng import FrlgIdRngMacro


def _make_cmd_mock() -> MagicMock:
    """テスト用の Command モックを生成する。"""
    cmd = MagicMock()
    cmd.press = MagicMock()
    cmd.wait = MagicMock()
    cmd.capture = MagicMock(return_value=None)
    cmd.save_img = MagicMock()
    cmd.notify = MagicMock()
    cmd.log = MagicMock()
    cmd.release = MagicMock()
    return cmd


class TestFrlgIdRngMacroInit:
    """マクロ初期化のテスト"""

    def test_default_init(self):
        """デフォルト引数で初期化できる"""
        macro = FrlgIdRngMacro()
        cmd = _make_cmd_mock()
        macro.initialize(cmd, {})
        assert macro._region == "JPN"
        assert macro._tid == 0

    def test_custom_init(self):
        """カスタム引数で初期化できる"""
        macro = FrlgIdRngMacro()
        cmd = _make_cmd_mock()
        macro.initialize(cmd, {"region": "ENG", "tid": 12345, "gender": "おんなのこ"})
        assert macro._region == "ENG"
        assert macro._tid == 12345
        assert macro._gender == "おんなのこ"

    def test_invalid_region(self):
        """無効なリージョンで ValueError が送出される"""
        macro = FrlgIdRngMacro()
        cmd = _make_cmd_mock()
        with pytest.raises(ValueError, match="未対応のリージョン"):
            macro.initialize(cmd, {"region": "INVALID"})

    def test_invalid_tid(self):
        """範囲外 TID で ValueError が送出される"""
        macro = FrlgIdRngMacro()
        cmd = _make_cmd_mock()
        with pytest.raises(ValueError, match="tid は 0–65535"):
            macro.initialize(cmd, {"tid": 70000})

    def test_frame3_offset_applied(self):
        """Frame3 にリージョン別オフセットが適用される"""
        macro = FrlgIdRngMacro()
        cmd = _make_cmd_mock()
        macro.initialize(cmd, {"region": "JPN", "frame3": 6609.0})
        assert macro._frame3 == 6609.0 - 143


class TestFrlgIdRngMacroTolerance:
    """許容範囲判定のテスト"""

    def _make_macro(self, tid: int, tolerance: int) -> FrlgIdRngMacro:
        macro = FrlgIdRngMacro()
        cmd = _make_cmd_mock()
        macro.initialize(
            cmd,
            {
                "tid": tid,
                "id_tolerance_range": tolerance,
                "frame_increment_mode": True,
            },
        )
        return macro

    def test_exact_match(self):
        macro = self._make_macro(100, 10)
        assert macro._is_within_tolerance(100) is True

    def test_within_range(self):
        macro = self._make_macro(100, 10)
        assert macro._is_within_tolerance(105) is True
        assert macro._is_within_tolerance(90) is True

    def test_outside_range(self):
        macro = self._make_macro(100, 10)
        assert macro._is_within_tolerance(111) is False
        assert macro._is_within_tolerance(89) is False

    def test_wrap_around_lower(self):
        """TID=10, tolerance=20 → lower が負 → 65536 を足して循環判定"""
        macro = self._make_macro(10, 20)
        assert macro._is_within_tolerance(65530) is True
        assert macro._is_within_tolerance(0) is True
        assert macro._is_within_tolerance(30) is True

    def test_wrap_around_upper(self):
        """TID=65530, tolerance=20 → upper が 65535 超 → 循環判定"""
        macro = self._make_macro(65530, 20)
        assert macro._is_within_tolerance(65535) is True
        assert macro._is_within_tolerance(10) is True
        assert macro._is_within_tolerance(14) is True


class TestFrlgIdRngMacroFinalize:
    """finalize のテスト"""

    def test_finalize_releases(self):
        macro = FrlgIdRngMacro()
        cmd = _make_cmd_mock()
        macro.initialize(cmd, {})
        macro.finalize(cmd)
        cmd.release.assert_called_once()
