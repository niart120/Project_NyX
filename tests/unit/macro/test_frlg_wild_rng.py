"""FRLG 野生乱数操作マクロ — ユニットテスト

config / 共通ヘルパー (game_restart, frlg_opening) のテストを提供する。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_macros_dir = str(Path(__file__).resolve().parent.parent.parent.parent / "macros")
if _macros_dir not in sys.path:
    sys.path.insert(0, _macros_dir)


# ============================================================
# config テスト
# ============================================================

from frlg_wild_rng.config import FrlgWildRngConfig


class TestConfigFromArgsDefaults:
    """FrlgWildRngConfig.from_args({}) がデフォルト値を返すこと"""

    def test_defaults(self):
        cfg = FrlgWildRngConfig.from_args({})
        assert cfg.frame1 == 2347
        assert cfg.target_advance == 610
        assert cfg.fps == 60.0
        assert cfg.frame1_offset == 0
        assert cfg.advance_offset == 322
        assert cfg.rng_multiplier == 2
        assert cfg.use_teachy_tv is False
        assert cfg.teachy_tv_frames == 0


class TestConfigFromArgsOverride:
    """各パラメータのオーバーライドが正しく反映されること"""

    def test_override_basic(self):
        cfg = FrlgWildRngConfig.from_args({
            "frame1": 3000,
            "target_advance": 800,
            "fps": 59.7275,
        })
        assert cfg.frame1 == 3000
        assert cfg.target_advance == 800
        assert cfg.fps == pytest.approx(59.7275)

    def test_override_corrections(self):
        cfg = FrlgWildRngConfig.from_args({
            "frame1_offset": 5,
            "advance_offset": 400,
            "rng_multiplier": 1,
        })
        assert cfg.frame1_offset == 5
        assert cfg.advance_offset == 400
        assert cfg.rng_multiplier == 1

    def test_override_teachy_tv(self):
        cfg = FrlgWildRngConfig.from_args({
            "use_teachy_tv": True,
            "teachy_tv_frames": 500,
        })
        assert cfg.use_teachy_tv is True
        assert cfg.teachy_tv_frames == 500


class TestConfigTeachyTvDisabled:
    """use_teachy_tv=false 時に teachy_tv_frames が無視されること"""

    def test_teachy_tv_frames_ignored_when_disabled(self):
        cfg = FrlgWildRngConfig.from_args({
            "use_teachy_tv": False,
            "teachy_tv_frames": 999,
        })
        # 設定値自体は保持されるが、マクロ実行時に use_teachy_tv=false なら使われない
        assert cfg.use_teachy_tv is False
        assert cfg.teachy_tv_frames == 999


# ============================================================
# タイマー待機時間算出テスト
# ============================================================


class TestTimerWaitCalculation:
    """(frame1 + frame1_offset) / fps の算出が正しいこと"""

    def test_default_frame1_wait(self):
        cfg = FrlgWildRngConfig.from_args({})
        wait = (cfg.frame1 + cfg.frame1_offset) / cfg.fps
        assert wait == pytest.approx(2347 / 60.0)

    def test_with_offset(self):
        cfg = FrlgWildRngConfig.from_args({"frame1": 2400, "frame1_offset": 10})
        wait = (cfg.frame1 + cfg.frame1_offset) / cfg.fps
        assert wait == pytest.approx(2410 / 60.0)


class TestAdvanceWaitCalculation:
    """(target_advance + advance_offset) / (fps × rng_multiplier) の算出が正しいこと"""

    def test_default_advance_wait(self):
        cfg = FrlgWildRngConfig.from_args({})
        effective_advance = cfg.target_advance + cfg.advance_offset
        advance_wait_fps = cfg.fps * cfg.rng_multiplier
        wait = effective_advance / advance_wait_fps
        assert wait == pytest.approx((610 + 322) / (60.0 * 2))

    def test_custom_advance_wait(self):
        cfg = FrlgWildRngConfig.from_args({
            "target_advance": 1000,
            "advance_offset": 400,
            "rng_multiplier": 1,
            "fps": 59.7275,
        })
        effective_advance = cfg.target_advance + cfg.advance_offset
        advance_wait_fps = cfg.fps * cfg.rng_multiplier
        wait = effective_advance / advance_wait_fps
        assert wait == pytest.approx(1400 / 59.7275)


# ============================================================
# 共通ヘルパーテスト
# ============================================================


def _make_mock_cmd() -> MagicMock:
    """テスト用の Command モックを生成する。"""
    cmd = MagicMock()
    cmd.press = MagicMock()
    return cmd


class TestRestartGameReturnsTimer:
    """restart_game() が float を返し start_timer() 相当の時刻であること"""

    def test_returns_float(self):
        from shared.game_restart import restart_game

        cmd = _make_mock_cmd()
        result = restart_game(cmd)
        assert isinstance(result, float)
        assert result > 0

    def test_calls_press_five_times(self):
        from shared.game_restart import restart_game

        cmd = _make_mock_cmd()
        restart_game(cmd)
        assert cmd.press.call_count == 5


class TestSkipOpeningReturnsTimer:
    """skip_opening_and_continue() が float を返し start_timer() 相当の時刻であること"""

    def test_returns_float(self):
        from shared.frlg_opening import skip_opening_and_continue

        cmd = _make_mock_cmd()
        result = skip_opening_and_continue(cmd)
        assert isinstance(result, float)
        assert result > 0

    def test_calls_press_three_times(self):
        from shared.frlg_opening import skip_opening_and_continue

        cmd = _make_mock_cmd()
        skip_opening_and_continue(cmd)
        assert cmd.press.call_count == 3
