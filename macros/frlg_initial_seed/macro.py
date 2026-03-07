"""
FRLG 初期Seed特定マクロ

ゲームのソフトリセット → 捕獲 → OCR で実数値を取得し
16bit 初期Seed を逆算して CSV に記録するマクロ。
Switch (720p) 専用。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

from nyxpy.framework.core.constants import Button, LStick
from nyxpy.framework.core.imgproc import OCRProcessor
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command

from .config import FrlgInitialSeedConfig
from .csv_helper import (
    append_csv_row,
    append_detail_csv_row,
    build_csv_path,
    build_detail_csv_path,
)
from .recognizer import (
    ROI_STATS,
    get_stat_digits,
    recognize_stats,
    save_roi_image,
)
from .seed_solver import solve_initial_seed

# ステータス ROI に対応するファイル名サフィックス
_STAT_FILE_NAMES: tuple[str, ...] = ("hp", "atk", "def", "spa", "spd", "spe")


# ============================================================
# 型エイリアス
# ============================================================

# 1 trial の結果: (seed 文字列, advance or None, 認識実数値 or None)
TrialResult = tuple[str, int | None, tuple[int, ...] | None]


# ============================================================
# 所要時間見積もり
# ============================================================

# 1 trial あたりのタイマー外固定操作時間 (秒)
# restart(2.55) + encounter(14.20) + capture(11.00)
# + dismiss(10.00) + stats(5.30) + OCR(~1.0)
_T_OPS: float = 44.05


def _estimate_total_seconds(cfg: FrlgInitialSeedConfig) -> float:
    """設定値から想定所要時間 (秒) を算出する。"""
    total = 0.0
    for f1 in range(cfg.min_frame, cfg.max_frame + 1):
        timer_sec = (f1 + cfg.frame1_offset + cfg.frame2 + cfg.frame2_offset) / cfg.fps
        total += cfg.trials * (timer_sec + _T_OPS)
    return total


# ============================================================
# タイマーヘルパー
# ============================================================


def _start_timer() -> float:
    """高精度タイマーの開始時刻を返す。"""
    return time.perf_counter()


def _consume_timer(
    cmd: Command, start_time: float, total_frames: float, fps: float
) -> None:
    """開始時刻からの経過時間を差し引き、残りフレーム分だけ待機する。"""
    target_seconds = total_frames / fps
    elapsed = time.perf_counter() - start_time
    remaining = target_seconds - elapsed
    if remaining > 0:
        cmd.wait(remaining)
    elif remaining < -0.5:
        cmd.log(
            f"タイマー超過: {-remaining:.3f}秒 (操作が指定フレーム数を超過)",
            level="WARNING",
        )


# ============================================================
# メインマクロクラス
# ============================================================


class FrlgInitialSeedMacro(MacroBase):
    """FRLG 初期Seed特定マクロ (Switch 720p)"""

    description = "FRLG 初期Seed特定マクロ (Switch 720p)"
    tags = ["pokemon", "frlg", "rng", "seed"]

    _MAX_RETRIES: int = 3
    """1 trial あたりの認識リトライ上限"""

    # --------------------------------------------------------
    # ライフサイクル
    # --------------------------------------------------------

    def initialize(self, cmd: Command, args: dict) -> None:
        self._cfg = FrlgInitialSeedConfig.from_args(args)
        cfg = self._cfg

        cmd.log(
            f"FrlgInitialSeedMacro 初期化完了: "
            f"min_frame={cfg.min_frame}, max_frame={cfg.max_frame}, "
            f"trials={cfg.trials}, frame2={cfg.frame2}, "
            f"min_advance={cfg.min_advance}, max_advance={cfg.max_advance}, "
            f"fps={cfg.fps}",
            level="INFO",
        )

        # デバッグ画像保存先を確保
        self._img_dir = Path(cfg.output_dir) / "img"
        self._img_dir.mkdir(parents=True, exist_ok=True)
        cmd.log(f"デバッグ画像保存先: {self._img_dir}", level="DEBUG")

        # CSV 追記パス
        self._csv_path = build_csv_path(cfg)
        self._detail_csv_path = build_detail_csv_path(cfg)
        cmd.log(
            f"CSV 出力先: {self._csv_path} — Frame {cfg.min_frame + cfg.frame1_offset} から開始",
            level="INFO",
        )
        cmd.log(f"詳細CSV 出力先: {self._detail_csv_path}", level="INFO")

        # OCR ウォームアップ (ステータス認識は en を使用)
        cmd.log("OCR ウォームアップ開始", level="INFO")
        ocr = OCRProcessor.get_instance("en")
        try:
            ocr.get_best_text(np.zeros((64, 200, 3), dtype=np.uint8))
        except Exception:
            pass
        cmd.log("OCR ウォームアップ完了", level="INFO")

        # 想定所要時間・ETA
        est_sec = _estimate_total_seconds(cfg)
        n_frames = cfg.max_frame - cfg.min_frame + 1
        total_trials = n_frames * cfg.trials
        h, rem = divmod(int(est_sec), 3600)
        m, s = divmod(rem, 60)
        eta = datetime.now() + timedelta(seconds=est_sec)
        cmd.log(
            f"想定所要時間: {h}時間{m}分{s}秒 "
            f"({n_frames}F × {cfg.trials}試行 = {total_trials}回), "
            f"ETA: {eta.strftime('%Y-%m-%d %H:%M')}",
            sep="\n",
            level="INFO",
        )

    def run(self, cmd: Command) -> None:
        cfg = self._cfg

        # 開始通知
        self._notify_start(cmd)

        for frame1 in range(cfg.min_frame, cfg.max_frame + 1):
            frame_label = frame1 + cfg.frame1_offset

            for trial in range(cfg.trials):
                cmd.log(
                    f"--- Frame {frame_label} ({trial + 1}/{cfg.trials}) ---",
                    level="INFO",
                )

                seed_result, advance, observed_stats = self._run_trial_with_retry(
                    cmd, frame1,
                )

                # 共通メタデータ
                meta = {
                    "frame": str(frame_label),
                    "seed": seed_result,
                    "region": cfg.language,
                    "version": cfg.rom,
                    "edition": cfg.edition,
                    "sound_mode": cfg.sound_mode,
                    "button_mode": cfg.button_mode,
                    "keyinput": cfg.keyinput,
                    "hardware": cfg.hardware,
                    "fps": str(cfg.fps),
                }

                # 詳細ログ (全行)
                detail_row = {
                    **meta,
                    "advance": str(advance) if advance is not None else "",
                    "pokemon": cfg.pokemon,
                    "level": str(cfg.level),
                    "note": "",
                }
                if observed_stats is not None:
                    stat_keys = ("hp", "atk", "def", "spa", "spd", "spe")
                    for k, v in zip(stat_keys, observed_stats):
                        detail_row[k] = str(v)
                else:
                    for k in ("hp", "atk", "def", "spa", "spd", "spe"):
                        detail_row[k] = ""
                append_detail_csv_row(self._detail_csv_path, detail_row)

                # 共有用 (Seed 特定成功行のみ)
                if seed_result not in ("MULT", "False"):
                    append_csv_row(self._csv_path, {**meta, "note": ""})

                adv_str = str(advance) if advance is not None else "-"
                cmd.log(
                    f"{frame_label}F ({trial + 1}/{cfg.trials})"
                    f"：{seed_result} (adv={adv_str})",
                    level="INFO",
                )

        # 完了通知
        self._notify_completion(cmd)

    def finalize(self, cmd: Command) -> None:
        cmd.release()
        cmd.log("FrlgInitialSeedMacro 終了", level="INFO")

    # --------------------------------------------------------
    # trial ループ
    # --------------------------------------------------------

    def _run_trial_with_retry(
        self, cmd: Command, frame1: int
    ) -> TrialResult:
        """1 trial を実行し、認識失敗時は最大 _MAX_RETRIES 回まで再試行する。

        リトライ時も frame2 は設定値のまま変更しない。
        リトライ上限を超えた場合は ("False", None) として記録する。
        """
        cfg = self._cfg

        for attempt in range(1, self._MAX_RETRIES + 1):
            result = self._run_single_trial(cmd, frame1, cfg.frame2)
            if result is not None:
                return result
            cmd.log(
                f"認識失敗 ({attempt}/{self._MAX_RETRIES}) — リトライ",
                level="WARNING",
            )

        cmd.log("リトライ上限到達 — False として記録", level="WARNING")
        return ("False", None, None)

    # --------------------------------------------------------
    # 1回分の試行 (ゲーム再起動 〜 Seed 逆算)
    # --------------------------------------------------------

    def _run_single_trial(
        self, cmd: Command, frame1: int, frame2: int
    ) -> TrialResult | None:
        """1 回分の試行を実行する。

        Returns:
            (Seed 文字列, advance) または認識失敗時は None。
        """
        cfg = self._cfg

        # === Phase 1: ゲーム再起動 → タイマー制御 → エンカウント ===
        cmd.log("Phase1: ゲーム再起動", level="DEBUG")
        self._restart_game(cmd)

        cmd.log("Phase1: frame1 タイマー消化", level="DEBUG")
        _consume_timer(cmd, self._t1, frame1 + cfg.frame1_offset, cfg.fps)

        t2 = _start_timer()
        cmd.log("Phase1: OP送り → つづきから → 回想スキップ", level="DEBUG")
        self._navigate_to_encounter(cmd)

        cmd.log("Phase1: frame2 タイマー消化", level="DEBUG")
        _consume_timer(cmd, t2, frame2 + cfg.frame2_offset, cfg.fps)

        cmd.log("Phase1: エンカウント発生", level="DEBUG")
        self._trigger_encounter(cmd)

        # === Phase 2: 捕獲 → B 連打 → 実数値画面表示 ===
        cmd.log("Phase2: 捕獲操作", level="DEBUG")
        self._capture_pokemon(cmd)

        cmd.log("Phase2: 捕獲後ダイアログ B 連打", level="DEBUG")
        self._dismiss_post_capture(cmd)

        cmd.log("Phase2: 実数値画面を開く", level="DEBUG")
        self._open_stats_screen(cmd)

        # === Phase 3: OCR 認識 → Seed 逆算 ===
        cmd.log("Phase3: 実数値 OCR → Seed 逆算", level="DEBUG")
        return self._recognize_and_solve(cmd)

    # --------------------------------------------------------
    # Phase 1: ゲーム操作
    # --------------------------------------------------------

    def _restart_game(self, cmd: Command) -> None:
        """ゲームを終了→再起動し、frame1 タイマーを開始する。"""
        cmd.press(Button.HOME, dur=0.15, wait=0.50)
        cmd.press(Button.X, dur=0.20, wait=0.30)
        cmd.press(Button.A, dur=0.20, wait=0.50)
        cmd.press(Button.A, dur=0.20, wait=0.50)
        self._t1 = _start_timer()
        cmd.press(Button.A, dur=0.20)  # ゲーム起動

    def _navigate_to_encounter(self, cmd: Command) -> None:
        """スプラッシュ画面送り → つづきからはじめる → 回想スキップ。

        frame2 タイマーの計測区間内で実行される操作。
        所要時間はタイマーにより自然に吸収される。
        """
        cmd.press(Button.A, dur=2.50, wait=1.00)   # スプラッシュ画面 を A で飛ばす
        cmd.press(Button.A, dur=0.20, wait=1.50)   # つづきからはじめる
        cmd.press(Button.B, dur=1.00, wait=0.50)   # 回想を B で飛ばす

    def _trigger_encounter(self, cmd: Command) -> None:
        """ルギアに話しかけてエンカウントを発生させる。"""
        cmd.press(Button.A, dur=0.10, wait=11.00)   # 話しかける → エンカウント
        cmd.press(Button.A, dur=0.10, wait=3.00)   # メッセージ送り(ルギアが あらわれた！)

    # --------------------------------------------------------
    # Phase 2: 捕獲 → ステータス表示
    # --------------------------------------------------------

    def _capture_pokemon(self, cmd: Command) -> None:
        """マスターボールで捕獲する。

        操作手順: → A → → → A(マスターボール選択) A(つかう) [捕獲完了待機]
        """
        cmd.press(LStick.RIGHT, dur=0.10, wait=0.30)   # 「バッグ」を選択
        cmd.press(Button.A, dur=0.10, wait=1.20)     # バッグを開く
        cmd.press(LStick.RIGHT, dur=0.10, wait=0.30)  # ポケット移動
        cmd.press(LStick.RIGHT, dur=0.10, wait=0.30)  # ポケット移動
        cmd.press(Button.A, dur=0.10, wait=0.30)    # マスターボールを選択
        cmd.press(Button.A, dur=0.10, wait=8.00)    # 「つかう」→ 捕獲アニメーション

    def _dismiss_post_capture(self, cmd: Command) -> None:
        """捕獲後のダイアログを B ボタン連打で処理する。

        図鑑登録・ニックネーム確認・戦闘終了など一連のダイアログを
        すべて B で送る。約 10 秒間。
        """
        for _ in range(50):  # 10 秒間 B を連打
            cmd.press(Button.B, dur=0.10, wait=0.10)

    def _open_stats_screen(self, cmd: Command) -> None:
        """メニューから実数値画面を直接開く。

        性格画面を経由せず、ステータス画面で右入力して
        実数値ページを直接表示する。
        """
        cmd.press(Button.PLUS, dur=0.10, wait=0.30) # メニューを開く
        cmd.press(LStick.DOWN, dur=0.10, wait=0.10)    # カーソルを移動
        cmd.press(Button.A, dur=0.10, wait=1.20)    # ポケモンを選択
        cmd.press(LStick.UP, dur=0.10, wait=0.10)    # カーソルを移動
        cmd.press(LStick.UP, dur=0.10, wait=0.10)    # カーソルを移動
        cmd.press(Button.A, dur=0.10, wait=0.30)    # ルギアを選択
        cmd.press(Button.A, dur=0.10, wait=0.30)    # 「つよさをみる」
        cmd.press(Button.A, dur=0.10, wait=1.00)    # ステータス画面表示
        cmd.press(LStick.RIGHT, dur=0.10, wait=1.00)  # 実数値ページへ遷移

    # --------------------------------------------------------
    # Phase 3: OCR 認識 → Seed 逆算
    # --------------------------------------------------------

    def _recognize_and_solve(self, cmd: Command) -> TrialResult | None:
        """実数値を OCR 認識し、Seed 逆算を実行する。

        性格画面の OCR は行わず、実数値のみで Seed を特定する。
        認識失敗時は None を返す。
        """
        cfg = self._cfg

        # --- 実数値画面キャプチャ → ROI 保存 → 認識 ---
        stat_image = cmd.capture()
        if stat_image is None:
            cmd.log("キャプチャ失敗（実数値）", level="WARNING")
            return None

        for roi, name in zip(ROI_STATS, _STAT_FILE_NAMES):
            save_roi_image(stat_image, roi, self._img_dir / f"stat_{name}.png")

        stat_raw = get_stat_digits(stat_image)
        cmd.log(
            "OCR生文字列(ステータス): "
            f"HP={stat_raw[0]!r}, Atk={stat_raw[1]!r}, Def={stat_raw[2]!r}, "
            f"SpA={stat_raw[3]!r}, SpD={stat_raw[4]!r}, Spe={stat_raw[5]!r}",
            level="DEBUG",
        )

        stats = recognize_stats(stat_image, cfg.base_stats, cfg.level)
        if stats is None:
            cmd.log("ステータス認識失敗", level="WARNING")
            return None

        cmd.log(
            f"ステータス認識: HP={stats[0]}, Atk={stats[1]}, Def={stats[2]}, "
            f"SpA={stats[3]}, SpD={stats[4]}, Spe={stats[5]}",
            level="INFO",
        )

        # Seed 逆算（実数値のみで照合）
        cmd.log("Seed 逆算開始", level="DEBUG")
        seed, advance = solve_initial_seed(
            observed_stats=stats,
            base_stats=cfg.base_stats,
            level=cfg.level,
            min_advance=cfg.min_advance,
            max_advance=cfg.max_advance,
        )
        cmd.log(f"Seed 逆算完了: seed={seed}, advance={advance}", level="DEBUG")
        return (seed, advance, stats)

    # --------------------------------------------------------
    # 通知
    # --------------------------------------------------------

    def _notify_start(self, cmd: Command) -> None:
        """開始通知を送信する。"""
        cfg = self._cfg
        fl = cfg.min_frame + cfg.frame1_offset
        msg = (
            f"[FRLG初期Seed集め自動化] "
            f"Frame {fl}〜{cfg.max_frame + cfg.frame1_offset} "
            f"(trials={cfg.trials}) の測定を開始します。"
        )
        cmd.log(msg, level="INFO")
        cmd.notify(msg)

    def _notify_completion(self, cmd: Command) -> None:
        """完了通知を送信する。"""
        cfg = self._cfg
        msg = (
            f"[FRLG初期Seed集め自動化] "
            f"初期Seedを{cfg.max_frame}Fまで取得したので、プログラムを終了します。"
        )
        cmd.log(msg, level="INFO")
        image = cmd.capture()
        if image is not None:
            cmd.notify(msg, image)
        else:
            cmd.notify(msg)
