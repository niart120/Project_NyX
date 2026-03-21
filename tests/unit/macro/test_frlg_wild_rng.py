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
        assert cfg.frame1 == 2036
        assert cfg.target_advance == 2049
        assert cfg.fps == 60.0
        assert cfg.frame1_offset == pytest.approx(7.0)
        assert cfg.advance_offset == -148
        assert cfg.rng_multiplier == 2
        assert cfg.use_teachy_tv is False
        assert cfg.teachy_tv_frames == 0
        assert cfg.teachy_tv_adv_per_frame == 314
        assert cfg.teachy_tv_transition_correction == -12353


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
            "teachy_tv_adv_per_frame": 313,
            "teachy_tv_transition_correction": -10000,
        })
        assert cfg.use_teachy_tv is True
        assert cfg.teachy_tv_frames == 500
        assert cfg.teachy_tv_adv_per_frame == 313
        assert cfg.teachy_tv_transition_correction == -10000


class TestConfigTeachyTvDisabled:
    """use_teachy_tv=false 時におしえテレビパラメータが無視されること"""

    def test_teachy_tv_frames_ignored_when_disabled(self):
        cfg = FrlgWildRngConfig.from_args({
            "use_teachy_tv": False,
            "teachy_tv_frames": 999,
        })
        assert cfg.use_teachy_tv is False
        assert cfg.teachy_tv_frames == 999


class TestTeachyTvAdvanceCalculation:
    """おしえテレビの消費量算出が正しいこと"""

    def test_teachy_excess_default_correction(self):
        """(adv_per_frame - rng_multiplier) * frames + transition_correction"""
        cfg = FrlgWildRngConfig.from_args({
            "teachy_tv_frames": 300,
        })
        excess = (
            (cfg.teachy_tv_adv_per_frame - cfg.rng_multiplier) * cfg.teachy_tv_frames
            + cfg.teachy_tv_transition_correction
        )
        # (314 - 2) * 300 + (-12353) = 93600 - 12353 = 81247
        assert excess == 81247

    def test_teachy_excess_zero_correction(self):
        """correction=0 のとき excess = (a-r)*F"""
        cfg = FrlgWildRngConfig.from_args({
            "teachy_tv_frames": 120,
            "teachy_tv_transition_correction": 0,
        })
        excess = (
            (cfg.teachy_tv_adv_per_frame - cfg.rng_multiplier) * cfg.teachy_tv_frames
            + cfg.teachy_tv_transition_correction
        )
        # (314 - 2) * 120 + 0 = 37440
        assert excess == 37440

    def test_effective_advance_with_teachy_tv(self):
        """おしえテレビありの effective_advance が超過分だけ差し引かれること"""
        cfg = FrlgWildRngConfig.from_args({
            "target_advance": 100000,
            "advance_offset": 0,
            "use_teachy_tv": True,
            "teachy_tv_frames": 300,
        })
        excess = (
            (cfg.teachy_tv_adv_per_frame - cfg.rng_multiplier) * cfg.teachy_tv_frames
            + cfg.teachy_tv_transition_correction
        )
        effective = cfg.target_advance + cfg.advance_offset - excess
        # 100000 + 0 - 81247 = 18753
        assert effective == 100000 - 81247


# ============================================================
# タイマー待機時間算出テスト
# ============================================================


class TestTimerWaitCalculation:
    """(frame1 + frame1_offset) / fps の算出が正しいこと"""

    def test_default_frame1_wait(self):
        cfg = FrlgWildRngConfig.from_args({})
        wait = (cfg.frame1 + cfg.frame1_offset) / cfg.fps
        assert wait == pytest.approx((2036 + 7.0) / 60.0)

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
        assert wait == pytest.approx((2049 + (-148)) / (60.0 * 2))

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
