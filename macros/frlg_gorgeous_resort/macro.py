"""FRLG ゴージャスリゾート アキホおねだりマクロ

ゲームのソフトリセット → 起動 → 初期Seed決定待機 → つづきからはじめる →
アキホに話しかけてポケモン決定フレームを合わせる → 要求ポケモンを見せる →
報酬アイテムを受け取る → レポート → ループ。
Switch (720p) 専用。

仕様: spec/macro/frlg_gorgeous_resort/spec.md
"""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from nyxpy.framework.core.constants import Button, LStick
from nyxpy.framework.core.imgproc import OCRProcessor
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command

from .config import FrlgGorgeousResortConfig
from .recognizer import (
    is_message_window_visible,
    matches_any_target,
    recognize_item,
    recognize_requested_pokemon,
)
from .species_data import (
    NAME_TO_NATIONAL,
    NATIONAL_TO_INTERNAL,
)

# ============================================================
# 所要時間見積もり定数 (seconds)
# ============================================================

_OCR_WARMUP_SECONDS: float = 3.0
_OVERHEAD_RESTART: float = 4.35
_OVERHEAD_POST: float = 30.0

# ============================================================
# タイマーヘルパー
# ============================================================


def _start_timer() -> float:
    return time.perf_counter()


def _consume_timer(
    cmd: Command, start_time: float, total_frames: float, fps: float
) -> None:
    target_seconds = total_frames / fps
    elapsed = time.perf_counter() - start_time
    remaining = target_seconds - elapsed
    if remaining > 0:
        cmd.wait(remaining)
    elif remaining < -0.5:
        cmd.log(
            f"タイマー超過: {-remaining:.3f}秒",
            level="WARNING",
        )


# ============================================================
# メインマクロクラス
# ============================================================


class FrlgGorgeousResortMacro(MacroBase):
    """FRLG ゴージャスリゾート アキホおねだりマクロ (Switch 720p)"""

    description = "FRLG ゴージャスリゾート アキホおねだりマクロ (Switch 720p)"
    tags = ["pokemon", "frlg", "rng", "item"]

    # --------------------------------------------------------
    # ライフサイクル
    # --------------------------------------------------------

    def initialize(self, cmd: Command, args: dict) -> None:
        self._cfg = FrlgGorgeousResortConfig.from_args(args)
        cfg = self._cfg

        # advance → 実待機秒数: (target_advance + advance_offset) / (fps × rng_multiplier)
        self._advance_wait_fps = cfg.fps * cfg.rng_multiplier
        self._effective_advance = cfg.target_advance + cfg.advance_offset

        # デバッグ画像保存先を確保
        self._img_dir = Path("static/frlg_gorgeous_resort") / "img"
        self._img_dir.mkdir(parents=True, exist_ok=True)
        cmd.log(f"デバッグ画像保存先: {self._img_dir}", level="DEBUG")

        # カウンタ初期化
        self._item_counters: dict[str, int] = defaultdict(int)
        self._loop_count = 0

        # pokedex 初期化
        self._pokedex_internal: set[int] | None = None
        if cfg.pokedex:
            self._pokedex_internal = {
                NATIONAL_TO_INTERNAL[n]
                for n in cfg.pokedex
                if n in NATIONAL_TO_INTERNAL
            }
            for name in cfg.target_pokemon:
                nat = NAME_TO_NATIONAL.get(name)
                if nat is None:
                    cmd.log(
                        f"target_pokemon '{name}' は不明なポケモン名です",
                        level="WARNING",
                    )
                elif nat not in cfg.pokedex:
                    cmd.log(
                        f"target_pokemon '{name}' (No.{nat}) は図鑑未登録です",
                        level="WARNING",
                    )
            cmd.log(
                f"図鑑登録数: {len(cfg.pokedex)}種"
                f" → 内部コード {len(self._pokedex_internal)}種",
                level="INFO",
            )

        # OCR ウォームアップ
        cmd.log("OCR ウォームアップ開始", level="INFO")
        ocr = OCRProcessor.get_instance("ja")
        try:
            ocr.get_best_text(
                np.full((64, 256, 3), 255, dtype=np.uint8)
            )
        except Exception:
            pass
        cmd.log("OCR ウォームアップ完了", level="INFO")

        # ETA 見積りと開始通知
        t_frame1 = (cfg.frame1 + cfg.frame1_offset) / cfg.fps
        t_advance = self._effective_advance / self._advance_wait_fps
        t_loop = _OVERHEAD_RESTART + t_frame1 + t_advance + _OVERHEAD_POST
        total_seconds = _OCR_WARMUP_SECONDS + (t_loop * cfg.target_count)
        eta = datetime.now() + timedelta(seconds=total_seconds)
        eta_str = eta.strftime("%Y-%m-%d %H:%M")

        cmd.log(
            f"OCRウォームアップ見積: {_OCR_WARMUP_SECONDS:.1f}s, "
            f"1ループ見積: {t_loop:.1f}s"
            f" × {cfg.target_count}回"
            f" = {total_seconds / 60:.0f}分"
            f" (ETA: {eta_str})",
            level="INFO",
        )
        cmd.notify(
            f"アキホおねだりマクロを開始"
            f" ({cfg.target_item} ×{cfg.target_count})。"
            f" ETA: {eta_str}",
        )

        cmd.log(
            f"FrlgGorgeousResortMacro 初期化完了: "
            f"frame1={cfg.frame1}, target_advance={cfg.target_advance}, "
            f"advance_offset={cfg.advance_offset}, "
            f"rng_multiplier={cfg.rng_multiplier}, "
            f"target_item={cfg.target_item}, "
            f"target_count={cfg.target_count}",
            level="INFO",
        )

    def run(self, cmd: Command) -> None:
        cfg = self._cfg
        i = 0

        while True:
            i += 1
            self._loop_count = i
            cmd.log(f"--- ループ {i} ---", level="INFO")

            # Step 1: ゲーム再起動
            self._restart_game(cmd)

            # Step 2: frame1 タイマー消化
            _consume_timer(
                cmd,
                self._t1,
                cfg.frame1 + cfg.frame1_offset,
                cfg.fps,
            )

            # Step 3: OP送り → つづきから → 回想スキップ → アキホに話しかける
            t2 = _start_timer()
            self._navigate_to_akiho(cmd)

            # Step 4: advance タイマー消化
            _consume_timer(cmd, t2, self._effective_advance, self._advance_wait_fps)

            # Step 5: 1回目の会話を終了し、改めてアキホに話しかける
            self._end_first_conversation(cmd)

            # Step 6: ポケモン確認（OCR）
            recognized = recognize_requested_pokemon(cmd, img_dir=self._img_dir)
            if cfg.target_pokemon:
                if recognized is None or not matches_any_target(
                    recognized, cfg.target_pokemon
                ):
                    cmd.log(
                        f"{i}回目：要求={recognized or '認識失敗'}"
                        f"（期待={cfg.target_pokemon}）リセット",
                        level="INFO",
                    )
                    continue
            cmd.log(f"{i}回目：要求={recognized} — OK", level="DEBUG")

            # Step 7: ポケモン受け渡し → アイテム受領
            self._deliver_pokemon_and_receive_item(cmd)

            # Step 8: アイテム認識 → カウント更新
            item = recognize_item(cmd, img_dir=self._img_dir)
            if item == "BAG_FULL":
                cmd.log("バッグが上限に達したため停止", level="INFO")
                cmd.notify(
                    "手持ちのアイテムが上限に達したため停止",
                    img=cmd.capture(),
                )
                break

            if item is not None:
                self._item_counters[item] += 1
                cmd.log(
                    f"{i}回目：{item} {self._item_counters[item]}個",
                    level="INFO",
                )
            else:
                cmd.log(f"{i}回目：アイテム認識失敗", level="WARNING")

            # Step 9: レポート書き → 退出 → 再入場
            self._save_and_reenter(cmd)

            # Step 10: 目標達成チェック
            if (
                cfg.target_item
                and self._item_counters.get(cfg.target_item, 0)
                >= cfg.target_count
            ):
                cmd.log(
                    f"目標数に到達: {cfg.target_item}"
                    f" {cfg.target_count}個",
                    level="INFO",
                )
                cmd.notify(
                    f"目標数に到達: {cfg.target_item}"
                    f" {cfg.target_count}個",
                    img=cmd.capture(),
                )
                break

    def finalize(self, cmd: Command) -> None:
        cmd.release()
        cmd.log(
            f"マクロ終了 (ループ {self._loop_count}回, "
            f"アイテム: {dict(self._item_counters)})",
            level="INFO",
        )

    # --------------------------------------------------------
    # Step 1: ゲーム再起動
    # --------------------------------------------------------

    def _restart_game(self, cmd: Command) -> None:
        """HOME メニュー経由でゲームを終了→再起動する。"""
        cmd.press(Button.HOME, dur=0.15, wait=1.00)
        cmd.press(Button.X, dur=0.20, wait=0.60)
        cmd.press(Button.A, dur=0.20, wait=1.20)
        cmd.press(Button.A, dur=0.20, wait=0.80)
        self._t1 = _start_timer()
        cmd.press(Button.A, dur=0.20)

    # --------------------------------------------------------
    # Step 3: OP 送り → つづきから → 回想スキップ → アキホに話しかける
    # --------------------------------------------------------

    def _navigate_to_akiho(self, cmd: Command) -> None:
        """OP スキップからアキホへの話しかけまでの操作。"""
        cmd.press(Button.A, dur=3.50, wait=1.00)   # OP を A で飛ばす
        cmd.press(Button.A, dur=0.20, wait=0.30)   # つづきからはじめる
        cmd.press(Button.B, dur=1.00, wait=1.80)   # 回想を B で飛ばす
        # アキホに話しかける（1回目：ポケモン決定処理をトリガー）
        cmd.press(Button.A, dur=0.10, wait=0.70)   # 話しかけ
        cmd.press(Button.B, dur=0.10, wait=0.70)   # テキスト送り
        cmd.press(Button.B, dur=0.10, wait=0.50)   # テキスト送り

    # --------------------------------------------------------
    # Step 5: 1回目の会話を終了 → 改めて話しかける
    # --------------------------------------------------------

    def _end_first_conversation(self, cmd: Command) -> None:
        """ポケモン決定後、現在の会話を終了して改めて話しかける。"""
        cmd.press(Button.B, dur=0.10, wait=0.60)
        cmd.press(Button.B, dur=0.10, wait=0.60)
        cmd.press(Button.B, dur=0.10, wait=0.30)
        # 改めてアキホに話しかける
        cmd.press(Button.A, dur=0.10, wait=0.90)

    # --------------------------------------------------------
    # Step 7: ポケモン受け渡し → アイテム受領
    # --------------------------------------------------------

    def _deliver_pokemon_and_receive_item(self, cmd: Command) -> None:
        """アキホとの会話を進め、ポケモンを見せてアイテムを受け取る。"""
        # アキホとの会話を進める
        for _ in range(7):
            cmd.press(Button.B, dur=0.10, wait=0.70)

        # セバスチャン登場・アイテム受取
        cmd.press(Button.B, dur=0.10, wait=0.70)
        cmd.press(Button.B, dur=0.10, wait=0.80)
        cmd.press(Button.B, dur=0.10, wait=0.50)
        cmd.press(Button.B, dur=0.10, wait=2.50)   # アイテム渡しアニメーション
        cmd.press(Button.B, dur=0.10, wait=0.40)
        cmd.press(Button.B, dur=0.10, wait=2.00)   # アイテム取得テキスト表示

    # --------------------------------------------------------
    # Step 9: レポート書き → 退出 → 再入場
    # --------------------------------------------------------

    def _save_and_reenter(self, cmd: Command) -> None:
        """レポート書いて、外に出て、再入場する。"""
        # 会話を終える
        cmd.press(Button.B, dur=0.10, wait=0.30)

        # 外に出る
        cmd.press(LStick.UP, dur=1.50, wait=2.20)

        # アキホの家に再入場
        cmd.press(LStick.DOWN, dur=3.30, wait=0.10)

        # レポートを書く
        cmd.press(Button.PLUS, dur=0.10, wait=0.30)
        cmd.press(LStick.UP, dur=0.10, wait=0.10)
        cmd.press(LStick.UP, dur=0.10, wait=0.10)
        cmd.press(LStick.UP, dur=0.10, wait=0.10)
        cmd.press(Button.A, dur=0.10, wait=1.00)   # 「レポートをかく」
        cmd.press(Button.A, dur=0.10, wait=1.00)   # 確認
        cmd.press(LStick.UP, dur=0.10, wait=0.10)  # 「はい」を選択
        cmd.press(Button.A, dur=0.10, wait=0.50)   # レポート書き込み実行

        # レポート完了待ち
        while is_message_window_visible(cmd):
            cmd.press(Button.B, dur=0.10, wait=0.30)
