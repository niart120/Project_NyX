"""FRLG 野生乱数操作マクロ

ゲームのソフトリセット → 起動 → 初期 Seed 決定待機 → つづきからはじめる →
回想スキップ →（おしえテレビ: オプション）→ メニューから「あまいかおり」を実行する。
1 回分の乱数調整操作を自動化する（ループしない）。
Switch (720p) 専用。

仕様: spec/macro/frlg_wild_rng/spec.md
"""

from __future__ import annotations

from macros.shared.frlg_opening import skip_opening_and_continue
from macros.shared.game_restart import restart_game
from macros.shared.timer import consume_timer, start_timer
from nyxpy.framework.core.constants import Button, LStick
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command

from .config import FrlgWildRngConfig

# ============================================================
# 所要時間見積もり定数 (seconds)
# ============================================================

_OVERHEAD_RESTART: float = 4.35
_OVERHEAD_POST: float = 15.0


# ============================================================
# メインマクロクラス
# ============================================================


class FrlgWildRngMacro(MacroBase):
    """FRLG 野生乱数操作マクロ (Switch 720p)"""

    description = "FRLG 野生乱数操作マクロ (Switch 720p)"
    tags = ["pokemon", "frlg", "rng", "wild"]

    # --------------------------------------------------------
    # ライフサイクル
    # --------------------------------------------------------

    def initialize(self, cmd: Command, args: dict) -> None:
        self._cfg = FrlgWildRngConfig.from_args(args)
        cfg = self._cfg

        self._advance_wait_fps = cfg.fps * cfg.rng_multiplier
        self._effective_advance = cfg.target_advance + cfg.advance_offset

        # おしえテレビによる消費分を差し引く
        if cfg.use_teachy_tv:
            teachy_excess = cfg.teachy_tv_consumption
            self._teachy_tv_frames = (
                cfg.teachy_tv_consumption
                - cfg.teachy_tv_transition_correction
            ) / (cfg.teachy_tv_adv_per_frame - cfg.rng_multiplier)
            self._effective_advance -= teachy_excess
            cmd.log(
                f"おしえテレビ: "
                f"消費 {teachy_excess} adv, "
                f"換算フレーム {self._teachy_tv_frames:.1f}F "
                f"(correction {cfg.teachy_tv_transition_correction})",
                level="INFO",
            )

        # 見積り
        t_frame1 = (cfg.frame1 + cfg.frame1_offset) / cfg.fps
        t_advance = self._effective_advance / self._advance_wait_fps
        t_total = _OVERHEAD_RESTART + t_frame1 + t_advance + _OVERHEAD_POST
        cmd.log(f"見積り所要時間: {t_total:.1f}s", level="INFO")

    def run(self, cmd: Command) -> None:
        cfg = self._cfg

        # Step 1: ゲーム再起動
        t0 = restart_game(cmd)

        # Step 2: frame1 タイマー消化（初期 Seed 決定）
        consume_timer(cmd, t0, cfg.frame1 + cfg.frame1_offset, cfg.fps)

        # Step 3: OP スキップ → つづきからはじめる → 回想スキップ
        t1 = skip_opening_and_continue(cmd)

        # Step 4: おしえテレビ（オプション）
        if cfg.use_teachy_tv:
            timer_teachy = start_timer()
            cmd.press(Button.Y, dur=0.10, wait=1.00)  # おしえテレビ起動
            consume_timer(cmd, timer_teachy, self._teachy_tv_frames, cfg.fps)
            cmd.press(Button.B, dur=0.10, wait=1.00)  # おしえテレビ終了

        # Step 5: メニュー操作 → あまいかおり選択
        cmd.press(Button.X, dur=0.10, wait=0.50)       # メニューを開く
        cmd.press(LStick.DOWN, dur=0.10, wait=0.30)    # "ポケモン" にカーソル
        cmd.press(Button.A, dur=0.10, wait=1.00)       # ポケモンメニューを開く
        cmd.press(LStick.UP, dur=0.10, wait=0.20)      # カーソル上移動
        cmd.press(LStick.UP, dur=0.10, wait=0.20)      # 最下段にカーソル
        cmd.press(Button.A, dur=0.10, wait=0.30)       # コンテキストメニューを開く
        cmd.press(LStick.DOWN, dur=0.10, wait=0.20)    # "あまいかおり" にカーソル

        # Step 6: timer1 消化 → あまいかおり実行
        consume_timer(cmd, t1, self._effective_advance, self._advance_wait_fps)
        cmd.press(Button.A, dur=0.10)  # あまいかおり実行

        # Step 7: マクロ終了
        cmd.log("あまいかおり実行完了 — エンカウント待ち", level="INFO")

    def finalize(self, cmd: Command) -> None:
        cmd.release()
        cmd.log("FrlgWildRngMacro 終了", level="INFO")
