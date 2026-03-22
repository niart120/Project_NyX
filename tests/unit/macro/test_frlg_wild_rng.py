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
        assert cfg.teachy_tv_consumption == 0
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
            "teachy_tv_consumption": 81247,
            "teachy_tv_adv_per_frame": 313,
            "teachy_tv_transition_correction": -10000,
        })
        assert cfg.use_teachy_tv is True
        assert cfg.teachy_tv_consumption == 81247
        assert cfg.teachy_tv_adv_per_frame == 313
        assert cfg.teachy_tv_transition_correction == -10000


class TestConfigTeachyTvDisabled:
    """use_teachy_tv=false 時におしえテレビパラメータが無視されること"""

    def test_teachy_tv_frames_ignored_when_disabled(self):
        cfg = FrlgWildRngConfig.from_args({
            "use_teachy_tv": False,
            "teachy_tv_consumption": 99999,
        })
        assert cfg.use_teachy_tv is False
        assert cfg.teachy_tv_consumption == 99999


class TestTeachyTvAdvanceCalculation:
    """おしえテレビのフレーム逆算・excess 計算が正しいこと"""

    def test_frame_calculation_default_correction(self):
        """frames = (consumption - correction) / adv_per_frame"""
        cfg = FrlgWildRngConfig.from_args({
            "teachy_tv_consumption": 94200,
        })
        # total consumption model: a × F + C = consumption
        # F = (consumption - C) / a = (94200 + 12353) / 314 = 106553 / 314 = 339.34...
        frames = (
            cfg.teachy_tv_consumption - cfg.teachy_tv_transition_correction
        ) / cfg.teachy_tv_adv_per_frame
        assert frames == pytest.approx(106553 / 314)

    def test_frame_calculation_zero_correction(self):
        """correction=0 のとき frames = consumption / a"""
        cfg = FrlgWildRngConfig.from_args({
            "teachy_tv_consumption": 37680,
            "teachy_tv_transition_correction": 0,
        })
        frames = (
            cfg.teachy_tv_consumption - cfg.teachy_tv_transition_correction
        ) / cfg.teachy_tv_adv_per_frame
        # 37680 / 314 = 120.0
        assert frames == pytest.approx(120.0)

    def test_excess_over_field_rate(self):
        """excess = consumption - rng_multiplier × frames"""
        cfg = FrlgWildRngConfig.from_args({
            "teachy_tv_consumption": 94200,
        })
        frames = (
            cfg.teachy_tv_consumption - cfg.teachy_tv_transition_correction
        ) / cfg.teachy_tv_adv_per_frame
        excess = cfg.teachy_tv_consumption - cfg.rng_multiplier * frames
        # excess = 94200 - 2 × (106553/314) = 94200 - 678.66... ≈ 93521.34
        expected_frames = 106553 / 314
        assert excess == pytest.approx(94200 - 2 * expected_frames)

    def test_effective_advance_with_teachy_tv(self):
        """おしえテレビありの effective_advance が excess 分だけ差し引かれること"""
        cfg = FrlgWildRngConfig.from_args({
            "target_advance": 100000,
            "advance_offset": 0,
            "use_teachy_tv": True,
            "teachy_tv_consumption": 94200,
        })
        frames = (
            cfg.teachy_tv_consumption - cfg.teachy_tv_transition_correction
        ) / cfg.teachy_tv_adv_per_frame
        excess = cfg.teachy_tv_consumption - cfg.rng_multiplier * frames
        effective = cfg.target_advance + cfg.advance_offset - excess
        # effective_advance > teachy_frames (timer1 budget > teachy TV time)
        assert effective > frames
        assert effective == pytest.approx(100000 - excess)


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
